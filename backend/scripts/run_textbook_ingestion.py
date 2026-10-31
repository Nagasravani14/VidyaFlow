"""
Ingestion script for official/sample textbooks.
Extracts pages, detects headings, assesses text quality, and saves documents & passages to DB.
"""
import hashlib
import os
from app.database import SessionLocal
from app.models import Board, ClassGrade, Subject, Chapter, TextbookDocument, TextbookPassage
from app.ingestion.extractor import TextbookExtractor


def get_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def ingest_sample_textbook():
    pdf_path = os.path.join("storage", "downloads", "ts_scert_class6_math_ch1.pdf")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")

    file_hash = get_file_sha256(pdf_path)
    title = "Telangana SCERT Class 6 Mathematics — Chapter 1: Knowing Our Numbers"
    source_url = "https://scert.telangana.gov.in/pdf/publication/maths_class6_ch1.pdf"

    db = SessionLocal()
    try:
        # Find chapter ID in seeded curriculum
        chapter = (
            db.query(Chapter)
            .join(Subject)
            .join(ClassGrade)
            .join(Board)
            .filter(
                Board.code == "TELANGANA_STATE_BOARD",
                ClassGrade.grade_number == 6,
                Subject.name.ilike("%math%"),
                Chapter.title.ilike("%knowing%"),
            )
            .first()
        )

        chapter_id = chapter.id if chapter else None
        print(f"Matched Chapter ID in database: {chapter_id} ({chapter.title if chapter else 'None'})")

        extractor = TextbookExtractor(db)
        print("Extracting pages from PDF...")
        result = extractor.extract_pdf(pdf_path, title)
        print(f"Extracted {result.total_pages} pages. Overall quality: {result.overall_quality}")

        for p in result.extracted_pages:
            print(f"  Page {p.page_number}: {p.character_count} chars | Heading: '{p.detected_heading}' | Quality: {p.quality_score:.2f}")

        doc = extractor.ingest_into_database(
            extraction=result,
            source_url=source_url,
            file_hash=file_hash,
            board_code="TELANGANA_STATE_BOARD",
            grade_number=6,
            subject_name="Mathematics",
            chapter_id=chapter_id,
        )

        print(f"\nSuccessfully ingested into database! Document ID: {doc.id}")
        passage_count = db.query(TextbookPassage).filter_by(document_id=doc.id).count()
        print(f"Total passages indexed: {passage_count}")

    finally:
        db.close()


if __name__ == "__main__":
    ingest_sample_textbook()
