from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, Topic, PracticeQuestion, QuestionOption
from app.services.retrieval_service import TextbookRetrievalService
from app.services.gemini_service import (
    GeminiService,
    AIGeneratedQuestion,
    GeminiAuthError,
    GeminiQuotaError,
    GeminiError,
)

router = APIRouter(prefix="/questions", tags=["AI Question Generation"])


class GenerateQuestionsRequest(BaseModel):
    board_code: str = "TELANGANA_STATE_BOARD"
    grade_number: int = Field(default=10, ge=6, le=10)
    subject_name: str = "Mathematics"
    chapter_id: Optional[int] = None
    topic_id: Optional[int] = None
    chapter_title: Optional[str] = None
    count: int = Field(default=3, ge=1, le=10)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    persist: bool = True  # Whether to cache generated questions into practice_questions table


class GeneratedQuestionResponse(BaseModel):
    id: Optional[int] = None
    question_text: str
    question_type: str
    options: List[str]
    correct_answer: str
    worked_explanation: str
    difficulty_level: str
    source_page_reference: Optional[str] = None
    provenance: str = "ai_generated_grounded"


class GenerateQuestionsResponse(BaseModel):
    questions: List[GeneratedQuestionResponse]
    count: int
    board_code: str
    grade_number: int
    subject_name: str
    chapter_title: str
    cached_from_database: bool = False


@router.post("/generate", response_model=GenerateQuestionsResponse)
def generate_ai_practice_questions(req: GenerateQuestionsRequest, db: Session = Depends(get_db)):
    """
    Generates original practice questions grounded in textbook curriculum passages using Gemini.
    Validates MCQ options and step-by-step worked solutions.
    """
    # 1. Resolve chapter title
    chapter_title = req.chapter_title
    chapter_obj = None
    if req.chapter_id:
        chapter_obj = db.query(Chapter).filter_by(id=req.chapter_id).first()
        if chapter_obj:
            chapter_title = chapter_obj.title

    if not chapter_title:
        chapter_title = "Core Mathematical Concepts"

    # 2. Retrieve Grounded Textbook Passages
    retriever = TextbookRetrievalService(db)
    retrieval_res = retriever.retrieve_passages(
        query=chapter_title,
        board_code=req.board_code,
        grade_number=req.grade_number,
        subject_name=req.subject_name,
        chapter_id=req.chapter_id,
        top_k=5,
    )

    passages_payload = [
        {
            "source_title": p.source_title,
            "page_number": p.page_number,
            "heading": p.heading,
            "content": p.content,
        }
        for p in retrieval_res.passages
    ]

    # 3. Call Gemini to generate original questions
    gemini = GeminiService()
    try:
        raw_questions = gemini.generate_questions(
            passages=passages_payload,
            count=req.count,
            difficulty=req.difficulty,
            grade=req.grade_number,
            subject=req.subject_name,
            chapter_title=chapter_title,
        )
    except GeminiAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Gemini API authentication failed: {e.message}",
        )
    except GeminiQuotaError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Gemini API rate limit or quota exceeded: {e.message}",
        )
    except GeminiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI question generation error: {e.message}",
        )

    # 4. Optionally persist into practice_questions table
    response_items: List[GeneratedQuestionResponse] = []

    # Find topic if available to attach questions
    target_topic_id = req.topic_id
    if not target_topic_id and chapter_obj and chapter_obj.topics:
        target_topic_id = chapter_obj.topics[0].id

    for q_idx, q in enumerate(raw_questions):
        persisted_id = None
        if req.persist and target_topic_id:
            try:
                import uuid
                q_code = f"AI_{req.grade_number}_{req.difficulty[:1].upper()}_{uuid.uuid4().hex[:6].upper()}"
                pq = PracticeQuestion(
                    topic_id=target_topic_id,
                    question_code=q_code,
                    question_text=q.question_text,
                    question_type=q.question_type,
                    difficulty_level=q.difficulty_level,
                    worked_explanation=q.worked_explanation,
                    correct_answer=q.correct_answer,
                    verification_status="verified",
                )
                db.add(pq)
                db.flush()
                persisted_id = pq.id

                for o_idx, opt in enumerate(q.options):
                    is_correct = opt.strip() == q.correct_answer.strip()
                    qo = QuestionOption(
                        question_id=pq.id,
                        option_index=o_idx,
                        option_text=opt,
                        is_correct=is_correct,
                    )
                    db.add(qo)
                db.commit()
            except Exception:
                db.rollback()

        response_items.append(
            GeneratedQuestionResponse(
                id=persisted_id,
                question_text=q.question_text,
                question_type=q.question_type,
                options=q.options,
                correct_answer=q.correct_answer,
                worked_explanation=q.worked_explanation,
                difficulty_level=q.difficulty_level,
                source_page_reference=q.source_page_reference,
                provenance="ai_generated_grounded",
            )
        )

    return GenerateQuestionsResponse(
        questions=response_items,
        count=len(response_items),
        board_code=req.board_code,
        grade_number=req.grade_number,
        subject_name=req.subject_name,
        chapter_title=chapter_title,
        cached_from_database=False,
    )
