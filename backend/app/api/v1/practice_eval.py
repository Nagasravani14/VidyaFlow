from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PracticeQuestion, PracticeSubmission
from app.services.gemini_service import GeminiService

router = APIRouter(prefix="/practice", tags=["Practice Assessment & Evaluation"])


class PracticeSubmissionRequest(BaseModel):
    question_id: Optional[int] = None
    question_text: str = Field(..., min_length=3)
    student_answer: str = Field(..., min_length=1)
    correct_answer: Optional[str] = None
    worked_explanation: Optional[str] = None
    max_marks: float = 1.0
    evaluation_type: str = "mcq_exact"  # "mcq_exact" or "rubric_ai"


class PracticeSubmissionResponse(BaseModel):
    submission_id: int
    is_correct: bool
    score: float
    max_marks: float
    feedback: str
    worked_explanation: Optional[str] = None
    pedagogical_guidance: Optional[str] = None
    evaluation_type: str
    submitted_at: str


class SubmissionHistoryItem(BaseModel):
    id: int
    question_id: Optional[int]
    question_text: str
    student_answer: str
    is_correct: Optional[bool]
    score: float
    max_marks: float
    feedback: Optional[str]
    evaluation_type: str
    submitted_at: str


@router.post("/submit", response_model=PracticeSubmissionResponse)
def submit_practice_answer(req: PracticeSubmissionRequest, db: Session = Depends(get_db)):
    """
    Submits a student's answer for evaluation and persistent record.
    Evaluates MCQs deterministically and subjective answers via rubric-grounded AI evaluation.
    """
    # 1. Resolve question details from DB if question_id provided
    correct_ans = req.correct_answer or ""
    worked_expl = req.worked_explanation or ""

    if req.question_id:
        q_obj = db.query(PracticeQuestion).filter_by(id=req.question_id).first()
        if q_obj:
            correct_ans = q_obj.correct_answer
            worked_expl = q_obj.worked_explanation

    is_correct = False
    score = 0.0
    feedback = ""
    guidance = ""

    # 2. Evaluation logic
    if req.evaluation_type == "mcq_exact":
        # Direct deterministic evaluation
        ans_clean = req.student_answer.strip().lower()
        target_clean = correct_ans.strip().lower()

        # Handle index-based option matching or exact text matching
        if ans_clean == target_clean:
            is_correct = True
            score = req.max_marks
            feedback = "Correct! Well done."
        else:
            is_correct = False
            score = 0.0
            feedback = f"Not quite. The correct answer is: {correct_ans}."
        guidance = "Review the step-by-step worked explanation below."

    else:
        # Rubric-based evaluation via Gemini
        gemini = GeminiService()
        eval_result = gemini.evaluate_subjective_answer(
            question_text=req.question_text,
            student_answer=req.student_answer,
            worked_explanation=worked_expl,
            correct_answer=correct_ans,
            marks=req.max_marks,
        )
        is_correct = eval_result.is_correct
        score = eval_result.score
        feedback = f"{eval_result.feedback} (Note: AI evaluation is advisory)."
        guidance = eval_result.pedagogical_guidance

    # 3. Persist submission
    sub = PracticeSubmission(
        question_id=req.question_id,
        question_text=req.question_text,
        student_answer=req.student_answer,
        is_correct=is_correct,
        score=score,
        max_marks=req.max_marks,
        feedback=feedback,
        worked_explanation=worked_expl,
        evaluation_type=req.evaluation_type,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return PracticeSubmissionResponse(
        submission_id=sub.id,
        is_correct=is_correct,
        score=score,
        max_marks=req.max_marks,
        feedback=feedback,
        worked_explanation=worked_expl,
        pedagogical_guidance=guidance,
        evaluation_type=req.evaluation_type,
        submitted_at=sub.submitted_at.isoformat(),
    )


@router.get("/submissions", response_model=List[SubmissionHistoryItem])
def list_submissions(limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_db)):
    """Retrieves recent practice submission attempts and performance history."""
    subs = db.query(PracticeSubmission).order_by(PracticeSubmission.submitted_at.desc()).limit(limit).all()
    return [
        SubmissionHistoryItem(
            id=s.id,
            question_id=s.question_id,
            question_text=s.question_text,
            student_answer=s.student_answer,
            is_correct=s.is_correct,
            score=s.score,
            max_marks=s.max_marks,
            feedback=s.feedback,
            evaluation_type=s.evaluation_type,
            submitted_at=s.submitted_at.isoformat(),
        )
        for s in subs
    ]
