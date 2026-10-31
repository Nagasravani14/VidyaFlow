"""
API router tests for AI Tutor, question generator, and practice assessment.
"""
from unittest.mock import MagicMock, patch
import pytest
from app.services.gemini_service import TutorExplanation, CitationRef, AIGeneratedQuestion, AnswerEvaluation


def test_tutor_status_endpoint(client):
    response = client.get("/api/v1/tutor/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_available" in data
    assert "model" in data


def test_tutor_chat_endpoint_mocked(client):
    mock_explanation = TutorExplanation(
        explanation="In the Indian System, 10 lakhs equals 1 million in the International System.",
        key_points=["1 Lakh = 100 Thousand", "10 Lakhs = 1 Million"],
        hints=["Count the zeros in both notations"],
        is_textbook_grounded=True,
        grounding_notes="SCERT Class 6 Math Section 1.2",
        citations=[
            CitationRef(
                source_title="SCERT Class 6 Math",
                page_number=2,
                heading="1.2 Place Value",
                excerpt="10,00,000 is 1 million.",
            )
        ],
    )

    with patch("app.api.v1.tutor.GeminiService.ask_tutor", return_value=mock_explanation):
        payload = {
            "message": "What is 10 lakhs in the international system?",
            "board_code": "TELANGANA_STATE_BOARD",
            "grade_number": 6,
            "subject_name": "Mathematics",
        }
        res = client.post("/api/v1/tutor/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["reply"] == mock_explanation.explanation
        assert data["is_textbook_grounded"] is True
        assert len(data["citations"]) == 1
        assert data["citations"][0]["page_number"] == 2
        assert "session_uuid" in data


def test_ai_question_generation_endpoint(client):
    mock_questions = [
        AIGeneratedQuestion(
            question_text="What is the value of Roman numeral XC?",
            question_type="multiple_choice",
            options=["80", "90", "110", "100"],
            correct_answer="90",
            worked_explanation="XC = 100 - 10 = 90.",
            difficulty_level="medium",
            source_page_reference="Page 4",
        )
    ]

    with patch("app.api.v1.ai_questions.GeminiService.generate_questions", return_value=mock_questions):
        payload = {
            "board_code": "TELANGANA_STATE_BOARD",
            "grade_number": 6,
            "subject_name": "Mathematics",
            "count": 1,
            "difficulty": "medium",
        }
        res = client.post("/api/v1/questions/generate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 1
        assert data["questions"][0]["correct_answer"] == "90"


def test_practice_submission_mcq_exact(client):
    payload = {
        "question_text": "Round off 472 to nearest hundred",
        "student_answer": "500",
        "correct_answer": "500",
        "evaluation_type": "mcq_exact",
        "max_marks": 1.0,
    }
    res = client.post("/api/v1/practice/submit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_correct"] is True
    assert data["score"] == 1.0
    assert "submission_id" in data


def test_practice_submission_rubric_ai_mocked(client):
    mock_eval = AnswerEvaluation(
        is_correct=True,
        score=4.5,
        max_marks=5.0,
        feedback="Accurate breakdown of the subtraction rule.",
        pedagogical_guidance="Also state the correct numeral representation.",
    )

    with patch("app.api.v1.practice_eval.GeminiService.evaluate_subjective_answer", return_value=mock_eval):
        payload = {
            "question_text": "Why is IC not a valid Roman numeral?",
            "student_answer": "Symbol I cannot be subtracted from C.",
            "correct_answer": "Symbol I can only be subtracted from V and X.",
            "evaluation_type": "rubric_ai",
            "max_marks": 5.0,
        }
        res = client.post("/api/v1/practice/submit", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["is_correct"] is True
        assert data["score"] == 4.5
