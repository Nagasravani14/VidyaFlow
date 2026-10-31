"""
Unit and integration tests for VidyaFlow RAG Endpoints:
- Student Mode: /api/quiz/generate, /api/quiz/evaluate
- Teacher Mode: /api/teacher/worksheet
- AI Chatbot: /api/chat/ask
- Parent Mode: /api/dashboard/stats
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.services.vector_store import ChromaVectorStore, normalize_board


@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as client:
        yield client


def test_normalize_board():
    assert normalize_board("TS") == "TS"
    assert normalize_board("Telangana State Board") == "TS"
    assert normalize_board("TELANGANA_STATE_BOARD") == "TS"
    assert normalize_board("ICSE") == "ICSE"
    assert normalize_board("cisce") == "ICSE"


def test_vector_store_curriculum_retrieval():
    store = ChromaVectorStore.get_instance()
    assert store.get_count() > 0

    # Query for ICSE Class 9 Physics Light
    results = store.query_curriculum(
        query="What is the critical angle and Snell's law?",
        board="ICSE",
        class_num=9,
        subject="Physics",
        chapter="Light",
        n_results=3,
    )
    assert len(results) > 0
    assert any("refraction" in r["text"].lower() or "light" in r["text"].lower() for r in results)


def test_student_quiz_generate_endpoint(api_client):
    payload = {
        "board": "ICSE",
        "class_num": 9,
        "subject": "Physics",
        "chapter": "Light",
        "count": 3,
    }
    response = api_client.post("/api/quiz/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3

    first_q = data[0]
    assert "id" in first_q
    assert "question" in first_q
    assert "options" in first_q
    assert len(first_q["options"]) >= 4
    assert "correct_option_index" in first_q
    assert "correct_option" in first_q
    assert "solution" in first_q


def test_student_quiz_evaluate_endpoint_correct(api_client):
    payload = {
        "question_id": "q1",
        "selected_option": "Bends away from normal",
        "correct_option": "Bends away from normal",
    }
    response = api_client.post("/api/quiz/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["correct"] is True
    assert data["score_delta"] == 1
    assert "explanation" in data


def test_student_quiz_evaluate_endpoint_incorrect(api_client):
    payload = {
        "question_id": "q2",
        "selected_option": "Bends towards normal",
        "correct_option": "Bends away from normal",
    }
    response = api_client.post("/api/quiz/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["correct"] is False
    assert data["score_delta"] == 0
    assert "explanation" in data


def test_teacher_worksheet_endpoint(api_client):
    payload = {
        "board": "TS",
        "class_num": 8,
        "subject": "Mathematics",
        "chapter": "Algebra",
        "difficulty": "Medium",
        "counts": {
            "mcq": 3,
            "short_answer": 2,
            "long_answer": 1,
        },
    }
    response = api_client.post("/api/teacher/worksheet", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "title" in data
    assert "sections" in data
    assert "answer_key" in data

    sections = data["sections"]
    assert "section_a_mcq" in sections
    assert "section_b_short_answer" in sections
    assert "section_c_long_answer" in sections

    assert len(sections["section_a_mcq"]) == 3
    assert len(sections["section_b_short_answer"]) == 2
    assert len(sections["section_c_long_answer"]) == 1

    answer_key = data["answer_key"]
    assert "section_a_mcq" in answer_key
    assert "section_b_short_answer" in answer_key
    assert "section_c_long_answer" in answer_key


def test_chatbot_ask_endpoint(api_client):
    payload = {
        "question": "What is photosynthesis and what are its main requirements?",
        "board": "ICSE",
        "class_num": 7,
        "subject": "Biology",
    }
    response = api_client.post("/api/chat/ask", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 20
    assert "sources" in data
    assert isinstance(data["sources"], list)
    assert len(data["sources"]) > 0


def test_dashboard_stats_endpoint(api_client):
    response = api_client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()

    assert "student_profile" in data
    assert "study_overview" in data
    assert "weak_chapters" in data
    assert "strong_chapters" in data
    assert "completed_assignments" in data
    assert "recent_quiz_history" in data

    assert data["study_overview"]["total_study_time_hours"] > 0
    assert len(data["weak_chapters"]) > 0
    assert len(data["completed_assignments"]) > 0


def test_lesson_overview_endpoint(api_client):
    payload = {
        "board": "TS",
        "class_num": 10,
        "subject": "Physical Science",
        "chapter": "Refraction of Light at Curved Surfaces",
    }
    response = api_client.post("/api/lesson/overview", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "concept_cards" in data
    assert len(data["concept_cards"]) >= 1
    assert "prescribed_next_step" in data
    assert "recommended_learning_path" in data

    first_card = data["concept_cards"][0]
    assert "id" in first_card
    assert "title" in first_card
    assert "summary" in first_card
    assert "key_points" in first_card
    assert "formulas_or_definitions" in first_card


def test_lesson_flashcards_endpoint(api_client):
    payload = {
        "board": "ICSE",
        "class_num": 9,
        "subject": "Physics",
        "chapter": "Light",
    }
    response = api_client.post("/api/lesson/flashcards", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 6
    first_fc = data[0]
    assert "id" in first_fc
    assert "concept_tag" in first_fc
    assert "front" in first_fc
    assert "back" in first_fc


def test_teacher_assignment_endpoint(api_client):
    payload = {
        "board": "TS",
        "class_num": 8,
        "subject": "Mathematics",
        "chapter": "Algebraic Expressions and Identities",
        "difficulty": "Medium",
    }
    response = api_client.post("/api/teacher/assignment", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "assignment_id" in data
    assert "title" in data
    assert data["total_marks"] == 25
    assert len(data["section_a"]) == 5
    assert len(data["section_b"]) == 5
    assert len(data["section_c"]) == 2
    assert len(data["section_a_mcqs"]) == 5
    assert len(data["section_b_short_answers"]) == 5
    assert len(data["section_c_hots"]) == 2
    assert "teacher_answer_key" in data
    assert "grading_rubric" in data


def test_adaptive_quiz_endpoint(api_client):
    payload = {
        "board": "ICSE",
        "class_num": 9,
        "subject": "Physics",
        "chapter": "Light",
        "concept": "Refraction of Light at Plane Surfaces",
        "difficulty": "medium",
        "num_questions": 5,
        "prerequisite_list": ["Rectilinear propagation of light", "Laws of reflection"],
        "focus_skills": ["understanding", "application", "analysis"],
    }
    response = api_client.post("/api/quiz/adaptive/generate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "concept_id" in data
    assert "difficulty_level" in data
    assert "total_questions" in data
    assert "questions" in data
    assert len(data["questions"]) == 5

    first_q = data["questions"][0]
    assert "question_id" in first_q
    assert "question_type" in first_q
    assert first_q["question_type"] in ["mcq", "fill_blank", "conceptual_short"]
    assert "cognitive_level" in first_q
    assert first_q["cognitive_level"] in ["recall", "understanding", "application", "analysis"]
    assert "difficulty" in first_q
    assert "question_text" in first_q
    assert "options" in first_q
    assert len(first_q["options"]) >= 4
    assert "correct_answer" in first_q
    assert "hint" in first_q
    assert "explanation" in first_q
    assert "prerequisite_concept_tested" in first_q
    assert "root_gap_remediation" in first_q
