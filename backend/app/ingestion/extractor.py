import os
import re
from typing import Dict, List, Optional
from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy.orm import Session
from app.models import TextbookDocument, TextbookPassage, Chapter


class ExtractedPage(BaseModel):
    page_number: int
    raw_text: str
    detected_heading: Optional[str] = None
    character_count: int
    quality_score: float  # 0.0 to 1.0 based on text density and readability
    needs_review: bool = False


class ExtractionResult(BaseModel):
    document_title: str
    file_path: str
    total_pages: int
    extracted_pages: List[ExtractedPage]
    total_passages: int
    overall_quality: str  # "verified", "needs_review"


class TextbookExtractor:
    """
    Page-by-page PDF extraction preserving page numbers, section boundaries,
    and extraction quality metrics.
    """

    HEADING_REGEX = re.compile(
        r"^(chapter\s+\d+|unit\s+\d+|\d+\.\d+\s+[A-Z]|[A-Z\s]{4,30}$|exercise\s+\d+|example\s+\d+)",
        re.IGNORECASE | re.MULTILINE,
    )

    def __init__(self, db: Session):
        self.db = db

    def extract_pdf(self, file_path: str, title: str) -> ExtractionResult:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found at {file_path}")

        reader = PdfReader(file_path)
        total_pages = len(reader.pages)
        pages_data: List[ExtractedPage] = []
        low_quality_count = 0

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            text = page.extract_text() or ""
            text = self._clean_text(text)

            char_count = len(text)
            # Basic quality assessment: non-empty, reasonable words
            quality = 1.0 if char_count > 100 else (char_count / 100.0)
            needs_review = char_count < 40  # Potential scanned page or image-only diagram

            if needs_review:
                low_quality_count += 1

            detected_heading = self._extract_heading(text)

            pages_data.append(
                ExtractedPage(
                    page_number=page_num,
                    raw_text=text,
                    detected_heading=detected_heading,
                    character_count=char_count,
                    quality_score=quality,
                    needs_review=needs_review,
                )
            )

        overall_quality = "needs_review" if (low_quality_count / max(1, total_pages)) > 0.3 else "verified"

        return ExtractionResult(
            document_title=title,
            file_path=file_path,
            total_pages=total_pages,
            extracted_pages=pages_data,
            total_passages=len(pages_data),
            overall_quality=overall_quality,
        )

    def ingest_into_database(
        self,
        extraction: ExtractionResult,
        source_url: str,
        file_hash: str,
        board_code: str,
        grade_number: int,
        subject_name: str,
        chapter_id: Optional[int] = None,
    ) -> TextbookDocument:
        """
        Persists extracted document and indexed passages into the relational database.
        Idempotent: updates existing document if already present with same hash.
        """
        doc = self.db.query(TextbookDocument).filter_by(file_hash=file_hash).first()
        if not doc:
            doc = TextbookDocument(
                source_url=source_url,
                file_path=extraction.file_path,
                file_hash=file_hash,
                title=extraction.document_title,
                board_code=board_code,
                grade_number=grade_number,
                subject_name=subject_name,
                total_pages=extraction.total_pages,
                file_size_bytes=os.path.getsize(extraction.file_path) if os.path.exists(extraction.file_path) else 0,
                extraction_status=extraction.overall_quality,
            )
            self.db.add(doc)
            self.db.flush()
        else:
            doc.title = extraction.document_title
            doc.total_pages = extraction.total_pages
            doc.extraction_status = extraction.overall_quality
            # Remove previous passages for clean re-ingest
            self.db.query(TextbookPassage).filter_by(document_id=doc.id).delete()
            self.db.flush()

        # Ingest passages page by page
        for p in extraction.extracted_pages:
            if not p.raw_text.strip():
                continue

            passage = TextbookPassage(
                document_id=doc.id,
                chapter_id=chapter_id,
                page_number=p.page_number,
                heading=p.detected_heading,
                content=p.raw_text,
                passage_index=p.page_number,
                language="en",
                verification_status="needs_review" if p.needs_review else "verified",
                metadata_json={"quality_score": p.quality_score, "char_count": p.character_count},
            )
            self.db.add(passage)

        self.db.commit()
        return doc

    def _clean_text(self, text: str) -> str:
        # Normalize whitespace while preserving line structure
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def _extract_heading(self, text: str) -> Optional[str]:
        for line in text.splitlines()[:5]:
            match = self.HEADING_REGEX.search(line)
            if match:
                return line[:80].strip()
        # Fallback to first non-empty line if short
        first_line = text.splitlines()[0] if text.splitlines() else None
        if first_line and len(first_line) < 60:
            return first_line.strip()
        return None
