from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Chapter, Topic
from app.schemas import ChapterSummary, ChapterDetail

router = APIRouter()


@router.get("/chapters", response_model=List[ChapterSummary], tags=["Chapters"])
def list_chapters(
    subject_id: Optional[int] = Query(None, description="Filter chapters by Subject ID"),
    verification_status: Optional[str] = Query(None, description="Filter by status: verified, draft"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List chapters for a subject with order, estimated time, and topic counts."""
    query = db.query(Chapter)

    if subject_id is not None:
        query = query.filter(Chapter.subject_id == subject_id)
    if verification_status is not None:
        query = query.filter(Chapter.verification_status == verification_status)

    chapters = query.order_by(Chapter.order_index, Chapter.chapter_number).offset(offset).limit(limit).all()

    result = []
    for ch in chapters:
        topic_count = db.query(func.count(Topic.id)).filter(Topic.chapter_id == ch.id).scalar()
        summary = ChapterSummary.model_validate(ch)
        summary.topic_count = topic_count
        result.append(summary)

    return result


@router.get("/chapters/{chapter_id}", response_model=ChapterDetail, tags=["Chapters"])
def get_chapter(chapter_id: int, db: Session = Depends(get_db)):
    """Retrieve detailed chapter info, including all topics and learning objectives."""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter with id {chapter_id} not found",
        )
    return chapter
