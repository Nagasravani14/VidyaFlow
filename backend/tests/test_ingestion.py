"""
Integration tests for PDF ingestion pipeline and passage retrieval.
"""
import os
import pytest
from app.models import TextbookDocument, TextbookPassage, Board, ClassGrade, Subject, Chapter
from app.ingestion.extractor import TextbookExtractor
from app.services.retrieval_service import TextbookRetrievalService


@pytest.fixture
def sample_pdf_path():
    path = os.path.join("storage", "downloads", "ts_scert_class6_math_ch1.pdf")
    if not os.path.exists(path):
        from scripts.generate_sample_scert_pdf import generate_scert_class6_math_ch1
        generate_scert_class6_math_ch1(path)
    return path


def test_pdf_extractor_page_count_and_headings(sample_pdf_path, db_session):
    extractor = TextbookExtractor(db_session)
    result = extractor.extract_pdf(sample_pdf_path, "Telangana SCERT Class 6 Math")
    assert result.total_pages == 4
    assert result.overall_quality == "verified"

    # Verify headings detected
    headings = [p.detected_heading for p in result.extracted_pages if p.detected_heading]
    assert len(headings) >= 2
    assert any("KNOWING OUR NUMBERS" in h for h in headings)


def test_textbook_ingest_into_database(sample_pdf_path, db_session):
    extractor = TextbookExtractor(db_session)
    result = extractor.extract_pdf(sample_pdf_path, "Telangana SCERT Class 6 Math")

    doc = extractor.ingest_into_database(
        extraction=result,
        source_url="https://scert.telangana.gov.in/test.pdf",
        file_hash="test_hash_12345",
        board_code="TELANGANA_STATE_BOARD",
        grade_number=6,
        subject_name="Mathematics",
        chapter_id=None,
    )
    assert doc.id is not None
    assert doc.total_pages == 4

    # Verify passages in database
    passages = db_session.query(TextbookPassage).filter_by(document_id=doc.id).all()
    assert len(passages) == 4
    assert all(p.verification_status == "verified" for p in passages)


def test_textbook_retrieval_ranking(sample_pdf_path, db_session):
    extractor = TextbookExtractor(db_session)
    result = extractor.extract_pdf(sample_pdf_path, "Telangana SCERT Class 6 Math")
    extractor.ingest_into_database(
        extraction=result,
        source_url="https://scert.telangana.gov.in/test.pdf",
        file_hash="test_hash_12345",
        board_code="TELANGANA_STATE_BOARD",
        grade_number=6,
        subject_name="Mathematics",
        chapter_id=None,
    )

    retrieval = TextbookRetrievalService(db_session)
    retrieval_res = retrieval.retrieve_passages(
        query="What are the basic Roman numerals symbols?",
        board_code="TELANGANA_STATE_BOARD",
        grade_number=6,
        top_k=2,
    )
    assert retrieval_res.total_found > 0
    assert retrieval_res.is_sufficient is True
    # The top passage should be page 4 containing Roman numerals
    top_p = retrieval_res.passages[0]
    assert top_p.page_number == 4
    assert "Roman Numerals" in top_p.content
