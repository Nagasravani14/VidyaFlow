"""
Unit tests for Gemini Service, structured outputs, and error handling.
Uses mocks to verify offline reliability without consuming API quota during CI.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.gemini_service import (
    GeminiService,
    GeminiAuthError,
    GeminiQuotaError,
    TutorExplanation,
    AIGeneratedQuestion,
    AnswerEvaluation,
    CitationRef,
)


def test_gemini_service_initialization():
    service = GeminiService(api_key="test_key_123", model="gemini-3.5-flash")
    assert service.api_key == "test_key_123"
    assert service.model == "gemini-3.5-flash"


def test_gemini_service_missing_api_key_raises_auth_error():
    service = GeminiService(api_key="")
    with pytest.raises(GeminiAuthError):
        service.ask_tutor(
            query="What is a number?",
            retrieved_passages=[],
            grade=6,
            subject="Mathematics",
        )


def test_tutor_explanation_pydantic_schema():
    citation = CitationRef(
        source_title="SCERT Class 6 Mathematics",
        page_number=4,
        heading="1.5 Roman Numerals",
        excerpt="Symbol I can only be subtracted from V and X.",
    )
    tutor_data = TutorExplanation(
        explanation="You cannot write 99 as IC because symbol I cannot be subtracted from C.",
        key_points=["Symbol I can be subtracted only from V and X", "99 is XCIX"],
        hints=["Break 99 into 90 + 9"],
        is_textbook_grounded=True,
        grounding_notes="Grounded in SCERT Chapter 1 Section 1.5",
        citations=[citation],
    )
    assert tutor_data.is_textbook_grounded is True
    assert len(tutor_data.citations) == 1
    assert tutor_data.citations[0].page_number == 4


def test_ai_generated_question_schema_validation():
    q = AIGeneratedQuestion(
        question_text="What is 10 lakhs in the International System?",
        question_type="multiple_choice",
        options=["100 Thousand", "1 Million", "10 Million", "1 Billion"],
        correct_answer="1 Million",
        worked_explanation="10 Lakh = 10,00,000 = 1,000,000 = 1 Million.",
        difficulty_level="medium",
        source_page_reference="Page 2",
    )
    assert q.correct_answer in q.options
    assert q.difficulty_level == "medium"


def test_answer_evaluation_schema():
    eval_res = AnswerEvaluation(
        is_correct=True,
        score=5.0,
        max_marks=5.0,
        feedback="Flawless explanation of Roman numeral subtraction rules.",
        pedagogical_guidance="Proceed to higher numeral operations.",
    )
    assert eval_res.is_correct is True
    assert eval_res.score == 5.0
