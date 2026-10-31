import os
import tempfile
import pytest
from app.importer.validator import validate_curriculum_payload
from app.importer.pipeline import CurriculumImporter
from app.models import Board, Subject, Chapter, Topic


def test_validator_rejects_missing_board():
    invalid_data = {
        "classes": [{"grade_number": 10, "subjects": []}]
    }
    is_valid, errors = validate_curriculum_payload(invalid_data)
    assert is_valid is False
    assert any("board" in err.lower() for err in errors)


def test_validator_rejects_invalid_grade_range():
    invalid_data = {
        "board": {"code": "TEST", "name": "Test Board"},
        "classes": [{"grade_number": 12, "subjects": []}]  # Grade 12 is out of 6-10 scope
    }
    is_valid, errors = validate_curriculum_payload(invalid_data)
    assert is_valid is False
    assert any("between 6 and 10" in err for err in errors)


def test_validator_detects_duplicate_chapters():
    invalid_data = {
        "board": {"code": "TEST", "name": "Test Board"},
        "classes": [
            {
                "grade_number": 10,
                "subjects": [
                    {
                        "code": "TEST_M",
                        "name": "Math",
                        "chapters": [
                            {"chapter_number": 1, "code": "CH1", "title": "Real Numbers"},
                            {"chapter_number": 1, "code": "CH1_DUP", "title": "Duplicate Ch 1"},
                        ],
                    }
                ],
            }
        ],
    }
    is_valid, errors = validate_curriculum_payload(invalid_data)
    assert is_valid is False
    assert any("duplicate chapter_number" in err.lower() for err in errors)


def test_importer_idempotency_and_safe_reimport(db_session):
    data = {
        "board": {"code": "SAFE_REIMPORT", "name": "Safe Reimport Board"},
        "syllabus_version": "2024-2025",
        "classes": [
            {
                "grade_number": 9,
                "subjects": [
                    {
                        "code": "SAFE_9_M",
                        "name": "Mathematics",
                        "chapters": [
                            {
                                "chapter_number": 1,
                                "code": "SAFE_9_M_CH01",
                                "title": "Real Numbers",
                                "estimated_minutes": 90,
                                "topics": [
                                    {
                                        "topic_code": "SAFE_9_M_T01",
                                        "title": "Irrational Numbers",
                                        "estimated_minutes": 30,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    importer = CurriculumImporter(db_session)

    # First import
    report1 = importer.import_from_dict(data)
    assert report1.success is True
    assert report1.chapters_created == 1
    assert report1.topics_created == 1

    board = db_session.query(Board).filter_by(code="SAFE_REIMPORT").first()
    assert board is not None

    ch_count_first = db_session.query(Chapter).count()
    assert ch_count_first == 1

    # Second import (same payload)
    report2 = importer.import_from_dict(data)
    assert report2.success is True
    assert report2.chapters_created == 0
    assert report2.chapters_updated == 1
    assert report2.topics_created == 0
    assert report2.topics_updated == 1

    # Total chapters must remain exactly 1, no duplicate rows created
    ch_count_second = db_session.query(Chapter).count()
    assert ch_count_second == 1


def test_csv_import_pipeline(db_session):
    csv_content = """board_code,board_name,grade_number,subject_code,subject_name,chapter_number,chapter_code,chapter_title,topic_code,topic_title,estimated_minutes
CSV_BOARD,CSV Board,8,CSV_8_M,Mathematics,1,CSV_CH01,Rational Numbers,CSV_T01,Properties,90
CSV_BOARD,CSV Board,8,CSV_8_M,Mathematics,2,CSV_CH02,Linear Equations,CSV_T02,One Variable,100
"""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        importer = CurriculumImporter(db_session)
        report = importer.import_from_csv(temp_path)
        assert report.success is True
        assert report.chapters_created == 2
        assert report.topics_created == 2

        board = db_session.query(Board).filter_by(code="CSV_BOARD").first()
        assert board is not None
        assert len(board.subjects) == 1
        assert len(board.subjects[0].chapters) == 2
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
