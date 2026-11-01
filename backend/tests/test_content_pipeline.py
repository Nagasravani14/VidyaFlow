"""
Tests for VidyaFlow Content Generation Pipeline, Mind Map Generator, and Read API.

Covers:
1. Idempotency of ensure_chapter_concepts.
2. MindMapSchema validations (accepts valid, rejects <4 or >8 branches, <2 or >6 children, >60 chars, empty).
3. Question pool generation (target reached, respects existing questions, never stores fallback as AI).
4. Mind map generator retries on validation failure and stores successfully.
5. Mind map generator sets grounded=False and review_status="unreviewed" when no passages exist.
6. GET /api/v1/chapters/{id}/mindmap (404 when missing/rejected, returns mindmap when present).
7. POST /api/v1/chapters/{id}/quiz:
   - 422 on invalid size (e.g. 5, 12, 25).
   - Public question format (no correct_answer or distractor_misconceptions).
   - Questions ordered L1 -> L5.
   - Respects review_status (never serves rejected questions).
   - Returns warning when pool is smaller than requested size.
"""

import copy
import json
import pytest
from pydantic import ValidationError

from app.models.curriculum import Board, Chapter, ClassGrade, Subject
from app.models.quiz import ChapterMindMap, Concept, Question, QuestionAttempt
from app.schemas.mindmap import MindMapSchema
from app.services.concept_mapper import ensure_chapter_concepts
from app.services.mindmap_generator import generate_chapter_mindmap
from app.services.pool_generator import generate_chapter_pool
from app.services.quiz_blueprints import Blueprint
from app.services.quiz_engine import QuizEngine


# --- Test Helpers & Fakes ---

class FakeRetriever:
    def __init__(self, passages=None):
        self.passages = passages if passages is not None else []

    def retrieve(self, chapter_or_bp):
        return self.passages

    def retrieve_for_chapter(self, chapter):
        return self.passages


class ScriptedQuizLLM:
    """Fake Quiz LLM that returns valid pre-scripted question items matching blueprint types."""

    def __init__(self, *items):
        self.items = list(items)
        self.calls = 0

    def generate_item(self, bp, passages, avoid_stems, feedback=None):
        self.calls += 1
        if self.items:
            item = self.items.pop(0)
            if isinstance(item, Exception):
                raise item
            return copy.deepcopy(item)

        # Vary templates by call number and level so question_hash duplicate check passes
        call_id = self.calls
        q_type = getattr(bp, "question_type", "mcq")

        if q_type == "numerical":
            ans_num = 5 + call_id
            return {
                "type": "numerical",
                "objective": f"Evaluate value for {bp.concept_name}",
                "stem": f"Calculate the exact numerical sum of {ans_num} and 10.",
                "answer": str(ans_num + 10),
                "tolerance": 0,
                "hint": "Perform straightforward integer addition.",
                "explanation": f"{ans_num} + 10 equals {ans_num + 10}.",
                "verify": [["eval", f"{ans_num} + 10", str(ans_num + 10)]],
            }

        # MCQs with distinctly varied phrasing templates
        templates = [
            ("Solve for x: x + {c} = {tot}.", "x + {c} = {tot}"),
            ("What is the solution of the linear equation 2x - {c} = {tot}?", "2x - {c} = {tot}"),
            ("Determine the value of variable k in 4k + {c} = {tot}.", "4k + {c} = {tot}"),
            ("Find the unknown variable p given that 3p = {tot} - {c}.", "3p = {tot} - {c}"),
            ("Identify the root of 5z + {c} = {tot}.", "5z + {c} = {tot}"),
        ]
        tmpl_stem, _ = templates[(call_id - 1) % len(templates)]
        ans_num = 10 + call_id
        tot_val = 20 + call_id
        stem = tmpl_stem.format(c=call_id, tot=tot_val)

        return {
            "type": "mcq",
            "objective": f"Solve equation for {bp.concept_name}",
            "stem": stem,
            "correct": str(ans_num),
            "distractors": [
                {"text": str(ans_num + 3), "misconception": "added instead of subtracted"},
                {"text": str(ans_num - 3), "misconception": "subtracted extra amount"},
                {"text": str(ans_num * 2), "misconception": "multiplied instead of divided"},
            ],
            "hint": "Isolate the variable on one side.",
            "explanation": f"Solving gives the value {ans_num}.",
            "verify": [["eval", f"{ans_num} + 0", str(ans_num)]],
        }


class FakeGeminiResponse:
    def __init__(self, text: str):
        self.text = text


class ScriptedGeminiService:
    """Fake GeminiService for mind map generation."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0
        self.model = "gemini-3.5-flash"

    def _generate_content(self, contents, config=None):
        self.calls += 1
        if not self.responses:
            raise RuntimeError("No scripted response remaining")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return FakeGeminiResponse(resp if isinstance(resp, str) else json.dumps(resp))


def _seed_curriculum_chapter(db) -> Chapter:
    """Helper to seed a test Board, ClassGrade, Subject and Chapter."""
    board = db.query(Board).filter(Board.code == "TS").first()
    if not board:
        board = Board(name="Telangana State Board", code="TS")
        db.add(board)
        db.flush()

    grade = db.query(ClassGrade).filter(ClassGrade.grade_number == 8).first()
    if not grade:
        grade = ClassGrade(grade_number=8, name="Class 8")
        db.add(grade)
        db.flush()

    subject = (
        db.query(Subject)
        .filter(Subject.board_id == board.id, Subject.class_id == grade.id, Subject.name == "Mathematics")
        .first()
    )
    if not subject:
        subject = Subject(
            code="MATH_8_TS",
            name="Mathematics",
            category="STEM",
            board_id=board.id,
            class_id=grade.id,
        )
        db.add(subject)
        db.flush()

    chapter = db.query(Chapter).filter(Chapter.subject_id == subject.id, Chapter.chapter_number == 1).first()
    if not chapter:
        chapter = Chapter(
            subject_id=subject.id,
            chapter_number=1,
            code="MATH_8_CH1",
            title="Linear Equations in One Variable",
            description="Solving linear equations with variables on one or both sides.",
            estimated_minutes=45,
            order_index=1,
            verification_status="verified",
        )
        db.add(chapter)
        db.flush()

    db.commit()
    db.refresh(chapter)
    return chapter


# --- Test 1: ensure_chapter_concepts Idempotency ---

def test_ensure_chapter_concepts_is_idempotent(db_session):
    _seed_curriculum_chapter(db_session)

    res1 = ensure_chapter_concepts(db_session)
    assert res1["created"] >= 1

    res2 = ensure_chapter_concepts(db_session)
    assert res2["created"] == 0
    assert res2["linked_existing"] == 0
    assert res2["already_mapped"] == res1["created"] + res1["already_mapped"]


# --- Test 2: MindMapSchema Validation Constraints ---

def test_mindmap_schema_validation():
    valid_payload = {
        "title": "Linear Equations in One Variable",
        "branches": [
            {
                "label": f"Branch {i}",
                "children": [
                    {"label": f"Subtopic {i}.1", "note": "Definition"},
                    {"label": f"Subtopic {i}.2", "note": "Formula"},
                ],
            }
            for i in range(1, 5)  # 4 branches
        ],
    }

    # 1. Valid schema should parse without error
    schema = MindMapSchema(**valid_payload)
    assert len(schema.branches) == 4
    assert schema.title == "Linear Equations in One Variable"

    # 2. Rejection of < 4 branches
    few_branches = dict(valid_payload, branches=valid_payload["branches"][:3])
    with pytest.raises(ValidationError):
        MindMapSchema(**few_branches)

    # 3. Rejection of > 8 branches
    many_branches = dict(valid_payload, branches=[
        {"label": f"B{i}", "children": [{"label": "C1"}, {"label": "C2"}]}
        for i in range(9)
    ])
    with pytest.raises(ValidationError):
        MindMapSchema(**many_branches)

    # 4. Rejection of < 2 children per branch
    few_children = copy.deepcopy(valid_payload)
    few_children["branches"][0]["children"] = [{"label": "Solo Child", "note": None}]
    with pytest.raises(ValidationError):
        MindMapSchema(**few_children)

    # 5. Rejection of > 6 children per branch
    many_children = copy.deepcopy(valid_payload)
    many_children["branches"][0]["children"] = [{"label": f"Child {c}"} for c in range(7)]
    with pytest.raises(ValidationError):
        MindMapSchema(**many_children)

    # 6. Rejection of label > 60 chars
    long_label = copy.deepcopy(valid_payload)
    long_label["branches"][0]["label"] = "A" * 61
    with pytest.raises(ValidationError):
        MindMapSchema(**long_label)

    # 7. Rejection of empty label
    empty_label = copy.deepcopy(valid_payload)
    empty_label["branches"][0]["label"] = "   "
    with pytest.raises(ValidationError):
        MindMapSchema(**empty_label)


# --- Test 3: Question Pool Generation & Fallback Rules ---

def test_generate_chapter_pool(db_session):
    chapter = _seed_curriculum_chapter(db_session)
    ensure_chapter_concepts(db_session)

    # Setup Scripted Quiz LLM and Engine
    scripted_llm = ScriptedQuizLLM()
    engine = QuizEngine(db_session, llm=scripted_llm, retriever=FakeRetriever(["Linear equations text."]))

    # Target: 5 total questions (1 at each level 1..5)
    target = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1}
    res = generate_chapter_pool(db_session, chapter, target_per_level=target, engine=engine)

    assert res["total_questions"] == 5
    assert res["newly_generated_llm_calls"] == 5

    # Check stored questions: all must be source="ai" and review_status="unreviewed"
    stored = (
        db_session.query(Question)
        .join(Concept, Question.concept_id == Concept.id)
        .filter(Concept.chapter_id == chapter.id)
        .all()
    )
    assert len(stored) == 5
    for q in stored:
        assert q.source == "ai"
        assert q.review_status == "unreviewed"

    # Resumability check: run again, should do 0 LLM calls because targets are satisfied
    res2 = generate_chapter_pool(db_session, chapter, target_per_level=target, engine=engine)
    assert res2["total_questions"] == 5
    assert res2["newly_generated_llm_calls"] == 0


# --- Test 4: Mind Map Generator Retries on Validation Failure ---

def test_mindmap_generator_retries_on_failure(db_session):
    chapter = _seed_curriculum_chapter(db_session)

    invalid_resp = {
        "title": chapter.title,
        "branches": [{"label": "Only One Branch", "children": [{"label": "Child 1"}]}],
    }
    valid_resp = {
        "title": chapter.title,
        "branches": [
            {"label": f"Theme {i}", "children": [{"label": f"Concept {i}.1"}, {"label": f"Concept {i}.2"}]}
            for i in range(1, 5)
        ],
    }

    gemini_mock = ScriptedGeminiService(invalid_resp, valid_resp)
    res = generate_chapter_mindmap(
        db_session,
        chapter,
        gemini_service=gemini_mock,
        max_retries=3,
        retriever=FakeRetriever(["Passage 1"]),
    )

    assert res["mindmap"] is not None
    assert res["llm_calls"] == 2
    assert res["grounded"] is True
    assert len(res["validation_errors"]) == 1

    stored = db_session.query(ChapterMindMap).filter(ChapterMindMap.chapter_id == chapter.id).first()
    assert stored is not None
    assert stored.review_status == "unreviewed"
    assert len(stored.mindmap_json["branches"]) == 4


# --- Test 5: Mind Map Generator Without Passages (grounded=False) ---

def test_mindmap_generator_ungrounded(db_session):
    chapter = _seed_curriculum_chapter(db_session)

    valid_resp = {
        "title": chapter.title,
        "branches": [
            {"label": f"Topic {i}", "children": [{"label": f"Item {i}.1"}, {"label": f"Item {i}.2"}]}
            for i in range(1, 5)
        ],
    }

    gemini_mock = ScriptedGeminiService(valid_resp)
    res = generate_chapter_mindmap(
        db_session,
        chapter,
        gemini_service=gemini_mock,
        max_retries=3,
        retriever=FakeRetriever([]),  # zero passages
    )

    assert res["mindmap"] is not None
    assert res["grounded"] is False

    stored = db_session.query(ChapterMindMap).filter(ChapterMindMap.chapter_id == chapter.id).first()
    assert stored.grounded is False
    assert stored.review_status == "unreviewed"


# --- Test 6: GET /api/v1/chapters/{id}/mindmap ---

def test_get_chapter_mindmap_endpoint(client, db_session):
    chapter = _seed_curriculum_chapter(db_session)

    # 1. 404 when mindmap does not exist
    r404 = client.get(f"/api/v1/chapters/{chapter.id}/mindmap")
    assert r404.status_code == 404
    assert "has not been generated yet" in r404.json()["detail"]

    # 2. Add mindmap and verify retrieval
    valid_mindmap = {
        "title": chapter.title,
        "branches": [
            {"label": f"Branch {i}", "children": [{"label": f"Child {i}.1"}, {"label": f"Child {i}.2"}]}
            for i in range(1, 5)
        ],
    }
    mm = ChapterMindMap(
        chapter_id=chapter.id,
        version=1,
        mindmap_json=valid_mindmap,
        source="ai",
        review_status="unreviewed",
        grounded=False,
        model_name="gemini-3.5-flash",
    )
    db_session.add(mm)
    db_session.commit()

    r200 = client.get(f"/api/v1/chapters/{chapter.id}/mindmap")
    assert r200.status_code == 200
    data = r200.json()
    assert data["title"] == chapter.title
    assert len(data["branches"]) == 4

    # 3. If rejected, returns 404
    mm.review_status = "rejected"
    db_session.commit()
    r_rej = client.get(f"/api/v1/chapters/{chapter.id}/mindmap")
    assert r_rej.status_code == 404


# --- Test 7: POST /api/v1/chapters/{id}/quiz ---

def test_post_chapter_quiz_endpoint(client, db_session):
    chapter = _seed_curriculum_chapter(db_session)
    ensure_chapter_concepts(db_session)
    concept = db_session.query(Concept).filter(Concept.chapter_id == chapter.id).first()

    # 1. Invalid sizes (e.g. 5, 12, 25) must return 422
    for bad_size in (5, 12, 25):
        r_bad = client.post(
            f"/api/v1/chapters/{chapter.id}/quiz",
            json={"size": bad_size, "student_id": "student_123"},
        )
        assert r_bad.status_code == 422

    # 2. Seed questions across levels L1..L5
    # Seed 2 questions at each level = 10 questions total
    created_questions = []
    for lvl in (1, 2, 3, 4, 5):
        for q_idx in (1, 2):
            q = Question(
                concept_id=concept.id,
                level=lvl,
                bloom_level="remember",
                question_type="mcq",
                difficulty="medium",
                stem=f"Level {lvl} Question {q_idx}: Solve equation?",
                options=["A", "B", "C", "D"],
                correct_answer="A",
                explanation="Detailed explanation for solving the problem.",
                content_hash=f"hash_lvl{lvl}_q{q_idx}",
                distractor_misconceptions={"B": "Wrong sign"},
                source="ai",
                review_status="unreviewed",
                assessment_purpose="practice",
            )
            db_session.add(q)
            created_questions.append(q)

    # Also add 1 rejected question at Level 1 to ensure it is never served
    rejected_q = Question(
        concept_id=concept.id,
        level=1,
        bloom_level="remember",
        question_type="mcq",
        difficulty="easy",
        stem="REJECTED QUESTION - MUST NOT BE SERVED",
        options=["X", "Y"],
        correct_answer="X",
        explanation="Rejected explanation.",
        content_hash="hash_rejected",
        source="ai",
        review_status="rejected",
        assessment_purpose="practice",
    )
    db_session.add(rejected_q)
    db_session.commit()

    # 3. Request quiz of size 10
    res = client.post(
        f"/api/v1/chapters/{chapter.id}/quiz",
        json={"size": 10, "student_id": "student_123"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["size"] == 10
    assert body["chapter_id"] == chapter.id
    assert body["warning"] is None
    questions = body["questions"]
    assert len(questions) == 10

    # Verify public question format: no correct_answer or distractor_misconceptions
    for q in questions:
        assert "correct_answer" not in q
        assert "distractor_misconceptions" not in q
        assert "stem" in q
        assert "level" in q
        assert "REJECTED" not in q["stem"]

    # Verify ordered L1 through L5
    levels = [q["level"] for q in questions]
    assert levels == sorted(levels), f"Questions not ordered: {levels}"

    # 4. Request quiz of size 15 when pool only has 10 -> warning returned
    res_15 = client.post(
        f"/api/v1/chapters/{chapter.id}/quiz",
        json={"size": 15, "student_id": "student_123"},
    )
    assert res_15.status_code == 200
    body_15 = res_15.json()
    assert body_15["warning"] is not None
    assert "Pool smaller than requested size" in body_15["warning"]
    assert len(body_15["questions"]) == 10
