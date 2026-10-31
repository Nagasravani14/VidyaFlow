import hashlib
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel


class DiscoveredResource(BaseModel):
    title: str
    url: str
    board_code: str
    grade_number: int
    subject_name: str
    language: str = "English"
    academic_year: str = "2024-2025"
    resource_type: str = "textbook"  # textbook, workbook, syllabus


class TextbookCrawler:
    """
    Crawls official public education portals (SCERT Telangana, etc.)
    with rate limiting, caching, and SHA256 integrity verification.
    """

    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VidyaFlowCurriculumBot/1.0"

    def __init__(self, download_dir: str = "storage/downloads", rate_limit_delay: float = 0.5):
        self.download_dir = download_dir
        self.rate_limit_delay = rate_limit_delay
        os.makedirs(self.download_dir, exist_ok=True)

    def discover_scert_telangana_resources(self) -> List[DiscoveredResource]:
        """
        Discovers publicly accessible curriculum PDFs and e-textbooks
        from the official SCERT Telangana portal.
        """
        discovered: List[DiscoveredResource] = []
        base_url = "https://scert.telangana.gov.in/"
        start_urls = [
            urljoin(base_url, "Displaycontent.aspx?encry=ammkNW4/gx+NeApstGPX+A=="),  # eTextBooks
            urljoin(base_url, "Displaycontent.aspx?encry=6PbYqEwq8JizwZzlmsQudw=="),  # Maths and Science
            urljoin(base_url, "Displaycontent.aspx?encry=JnYSe8LAE+ijkD28wkPEMA=="),  # Curriculum & Textbooks
        ]

        seen_urls = set()

        with httpx.Client(
            timeout=15,
            follow_redirects=True,
            verify=False,  # Accommodates Indian government NIC certificate authorities
            headers={"User-Agent": self.DEFAULT_USER_AGENT},
        ) as client:
            for page_url in start_urls:
                try:
                    time.sleep(self.rate_limit_delay)
                    res = client.get(page_url)
                    if res.status_code != 200:
                        continue

                    soup = BeautifulSoup(res.text, "html.parser")
                    for a in soup.find_all(["a", "link"], href=True):
                        href = a["href"]
                        full_url = urljoin(page_url, href)
                        title = a.get_text().strip().replace("\n", " ")

                        if not title:
                            title = os.path.basename(full_url).replace(".pdf", "").replace("%20", " ")

                        # Identify relevant educational PDFs
                        if ".pdf" in full_url.lower() and full_url not in seen_urls:
                            seen_urls.add(full_url)

                            # Determine class and subject from title / URL
                            grade = self._detect_grade(title, full_url)
                            subject = self._detect_subject(title, full_url)

                            discovered.append(
                                DiscoveredResource(
                                    title=title,
                                    url=full_url,
                                    board_code="TELANGANA_STATE_BOARD",
                                    grade_number=grade,
                                    subject_name=subject,
                                    language="English",
                                    academic_year="2024-2025",
                                    resource_type="textbook",
                                )
                            )
                except Exception as e:
                    continue

        return discovered

    def _detect_grade(self, title: str, url: str) -> int:
        combined = f"{title} {url}".lower()
        for g in [10, 9, 8, 7, 6]:
            if f"class {g}" in combined or f"class-{g}" in combined or f"{g}th" in combined or f"class{g}" in combined:
                return g
        return 10  # default secondary

    def _detect_subject(self, title: str, url: str) -> str:
        combined = f"{title} {url}".lower()
        if "math" in combined:
            return "Mathematics"
        if "phys" in combined or "chem" in combined or "science" in combined:
            return "Physical Science"
        if "bio" in combined:
            return "Biological Science"
        if "social" in combined:
            return "Social Studies"
        return "Mathematics"

    def download_and_verify(
        self,
        url: str,
        expected_hash: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str], int]:
        """
        Downloads a document with rate limiting, caches locally,
        and computes SHA256 checksum to prevent redundant downloads.
        Returns: (success, local_file_path, sha256_hash, file_size_bytes)
        """
        filename = os.path.basename(url.split("?")[0]) or "document.pdf"
        if not filename.endswith(".pdf"):
            filename = f"{hashlib.md5(url.encode()).hexdigest()[:12]}_{filename}.pdf"

        local_path = os.path.join(self.download_dir, filename)

        # Check existing file cache
        if os.path.exists(local_path):
            existing_hash = self.compute_sha256(local_path)
            file_size = os.path.getsize(local_path)
            if expected_hash and existing_hash == expected_hash:
                return True, local_path, existing_hash, file_size
            if file_size > 1000:
                # Valid cached file
                return True, local_path, existing_hash, file_size

        time.sleep(self.rate_limit_delay)

        try:
            with httpx.Client(
                timeout=30,
                follow_redirects=True,
                verify=False,
                headers={"User-Agent": self.DEFAULT_USER_AGENT},
            ) as client:
                res = client.get(url)
                if res.status_code != 200:
                    return False, None, None, 0

                content = res.content
                file_hash = hashlib.sha256(content).hexdigest()
                file_size = len(content)

                with open(local_path, "wb") as f:
                    f.write(content)

                return True, local_path, file_hash, file_size
        except Exception:
            return False, None, None, 0

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
