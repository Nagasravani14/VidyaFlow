from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Topic, PracticeQuestion, Lesson
from app.schemas import TopicDetail, PracticeQuestionRead, LessonRead

router = APIRouter()


@router.get("/topics/{topic_id}", response_model=TopicDetail, tags=["Topics"])
def get_topic_detail(topic_id: int, db: Session = Depends(get_db)):
    """Retrieve full topic details, including lessons, worked examples, learning objectives, and prerequisites."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic with id {topic_id} not found",
        )
    return topic


@router.get("/topics/{topic_id}/lessons", response_model=List[LessonRead], tags=["Topics"])
def get_topic_lessons(
    topic_id: int,
    language: Optional[str] = Query(None, description="Language code: en, te, hi"),
    db: Session = Depends(get_db),
):
    """Retrieve all lessons/explanations for a specific topic."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic with id {topic_id} not found",
        )

    query = db.query(Lesson).filter(Lesson.topic_id == topic_id)
    if language:
        query = query.filter(Lesson.language == language)

    return query.order_by(Lesson.order_index).all()


@router.get("/topics/{topic_id}/questions", response_model=List[PracticeQuestionRead], tags=["Questions"])
def get_topic_practice_questions(
    topic_id: int,
    difficulty: Optional[str] = Query(None, description="Filter by difficulty: easy, medium, hard"),
    language: Optional[str] = Query(None, description="Filter by language: en, te, hi"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve practice questions for a topic, with multiple choice options, hints, and worked explanations."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic with id {topic_id} not found",
        )

    query = db.query(PracticeQuestion).filter(PracticeQuestion.topic_id == topic_id)
    if difficulty:
        query = query.filter(PracticeQuestion.difficulty_level == difficulty)
    if language:
        query = query.filter(PracticeQuestion.language == language)

    return query.offset(offset).limit(limit).all()
