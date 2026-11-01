"""
API Router for Chapter Mind Maps and Chapter Quizzes.

GET  /api/v1/chapters/{chapter_id}/mindmap
POST /api/v1/chapters/{chapter_id}/quiz
"""

import random
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.curriculum import Chapter
from app.models.quiz import ChapterMindMap, Concept, Question, QuestionAttempt
from app.services.concept_mapper import ensure_chapter_concepts
from app.services.quiz_engine import public_question

router = APIRouter(prefix="/chapters", tags=["Chapter Quiz & Mind Map"])


class ChapterQuizRequest(BaseModel):
    size: int = Field(..., description="Quiz size: must be 10, 15, or 20")
    student_id: str = Field(..., min_length=1, description="Student identifier")

    @field_validator("size")
    def validate_size(cls, v: int) -> int:
        if v not in (10, 15, 20):
            raise ValueError("Quiz size must be 10, 15, or 20")
        return v


class ChapterQuizResponse(BaseModel):
    chapter_id: int
    chapter_title: str
    quiz_id: str
    questions: List[Dict[str, Any]]
    size: int
    warning: Optional[str] = None


@router.get(
    "/{chapter_id}/mindmap",
    summary="Get interactive concept mind map for a chapter",
    response_model=Dict[str, Any],
)
def get_chapter_mindmap(
    chapter_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns the stored mindmap_json for chapter_id (matching MindMapSchema).
    Returns 404 if not yet generated or rejected.
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_id} not found",
        )

    mindmap = (
        db.query(ChapterMindMap)
        .filter(
            ChapterMindMap.chapter_id == chapter_id,
            ChapterMindMap.review_status != "rejected",
        )
        .first()
    )

    if not mindmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mind map for chapter {chapter_id} has not been generated yet",
        )

    return mindmap.mindmap_json


@router.post(
    "/{chapter_id}/quiz",
    summary="Generate or fetch an ordered adaptive quiz for a chapter",
    response_model=ChapterQuizResponse,
)
def get_chapter_quiz(
    chapter_id: int,
    req: ChapterQuizRequest,
    db: Session = Depends(get_db),
):
    """
    Selects `size` (10, 15, or 20) questions from the chapter's pool:
    - Ordered strictly from L1 to L5
    - Only non-rejected questions
    - Avoids recently answered questions for student_id
    - Returns browser-safe public_question payload (no answers or misconceptions)
    - Returns warning if pool is smaller than requested size
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_id} not found",
        )

    # Find concept
    concept = db.query(Concept).filter(Concept.chapter_id == chapter.id).first()
    if not concept:
        ensure_chapter_concepts(db)
        concept = db.query(Concept).filter(Concept.chapter_id == chapter.id).first()

    if not concept:
        return ChapterQuizResponse(
            chapter_id=chapter.id,
            chapter_title=chapter.title,
            quiz_id=f"quiz_{uuid.uuid4().hex[:12]}",
            questions=[],
            size=0,
            warning="No questions available for this chapter",
        )

    # Recent question attempts for student_id
    recent_attempts = (
        db.query(QuestionAttempt.question_id)
        .filter(QuestionAttempt.student_id == req.student_id)
        .order_by(QuestionAttempt.id.desc())
        .limit(50)
        .all()
    )
    recent_ids = {r[0] for r in recent_attempts}

    # Fetch non-rejected questions for this concept
    all_qs = (
        db.query(Question)
        .filter(Question.concept_id == concept.id, Question.review_status != "rejected")
        .all()
    )

    # Group by level 1..5
    by_level: Dict[int, List[Question]] = {lvl: [] for lvl in (1, 2, 3, 4, 5)}
    for q in all_qs:
        lvl = q.level if q.level in by_level else 1
        by_level[lvl].append(q)

    # For each level, partition into non-recent and recent, shuffle both
    rng = random.Random()
    sorted_level_pools: Dict[int, List[Question]] = {}
    for lvl in (1, 2, 3, 4, 5):
        qs = by_level[lvl]
        unseen = [q for q in qs if q.id not in recent_ids]
        seen = [q for q in qs if q.id in recent_ids]
        rng.shuffle(unseen)
        rng.shuffle(seen)
        sorted_level_pools[lvl] = unseen + seen

    # Target per level: size // 5 (2 for 10, 3 for 15, 4 for 20)
    target_each = req.size // 5
    picked: List[Question] = []
    picked_ids = set()

    # Pass 1: Take up to target_each from each level
    for lvl in (1, 2, 3, 4, 5):
        take = sorted_level_pools[lvl][:target_each]
        for q in take:
            picked.append(q)
            picked_ids.add(q.id)

    # Pass 2: If deficit remains, borrow from adjacent levels, preferring lower over higher
    deficit = req.size - len(picked)
    if deficit > 0:
        for lvl in (1, 2, 3, 4, 5):
            leftover = [q for q in sorted_level_pools[lvl] if q.id not in picked_ids]
            while leftover and deficit > 0:
                q = leftover.pop(0)
                picked.append(q)
                picked_ids.add(q.id)
                deficit -= 1
            if deficit <= 0:
                break

    # Strictly order picked questions L1 -> L5
    picked.sort(key=lambda q: (q.level or 1, q.id))

    warning = None
    if len(picked) < req.size:
        warning = f"Pool smaller than requested size ({len(picked)} available out of {req.size} requested)"

    quiz_id = f"quiz_{uuid.uuid4().hex[:12]}"
    public_questions = [public_question(q) for q in picked]

    return ChapterQuizResponse(
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        quiz_id=quiz_id,
        questions=public_questions,
        size=len(public_questions),
        warning=warning,
    )
