from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Chapter, Topic, Lesson, LearningObjective, Subject, ClassGrade
from app.schemas.common import PaginatedResponse

router = APIRouter()


class SearchResultItem(BaseModel):
    result_type: str  # "chapter", "topic", "lesson", "learning_objective"
    id: int
    title: str
    snippet: Optional[str] = None
    board_id: Optional[int] = None
    class_grade_number: Optional[int] = None
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    chapter_id: Optional[int] = None
    chapter_title: Optional[str] = None
    topic_id: Optional[int] = None
    verification_status: Optional[str] = "verified"


@router.get("/search", response_model=PaginatedResponse[SearchResultItem], tags=["Search"])
def search_curriculum(
    query: str = Query(..., min_length=2, description="Search term for curriculum content"),
    board_id: Optional[int] = Query(None, description="Filter by Board ID"),
    class_grade: Optional[int] = Query(None, ge=6, le=10, description="Filter by Class grade (6-10)"),
    subject_id: Optional[int] = Query(None, description="Filter by Subject ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Search across chapters, topics, lessons, and learning objectives.
    Returns matched results with breadcrumbs (board, class, subject, chapter).
    """
    search_term = f"%{query.strip()}%"
    results: List[SearchResultItem] = []

    # 1. Search Chapters
    ch_query = (
        db.query(Chapter)
        .join(Subject, Chapter.subject_id == Subject.id)
        .join(ClassGrade, Subject.class_id == ClassGrade.id)
        .filter(or_(Chapter.title.ilike(search_term), Chapter.description.ilike(search_term)))
    )
    if board_id:
        ch_query = ch_query.filter(Subject.board_id == board_id)
    if class_grade:
        ch_query = ch_query.filter(ClassGrade.grade_number == class_grade)
    if subject_id:
        ch_query = ch_query.filter(Chapter.subject_id == subject_id)

    for ch in ch_query.all():
        results.append(
            SearchResultItem(
                result_type="chapter",
                id=ch.id,
                title=f"Chapter {ch.chapter_number}: {ch.title}",
                snippet=ch.description[:180] if ch.description else None,
                board_id=ch.subject.board_id,
                class_grade_number=ch.subject.class_grade.grade_number,
                subject_id=ch.subject_id,
                subject_name=ch.subject.name,
                chapter_id=ch.id,
                chapter_title=ch.title,
                verification_status=ch.verification_status,
            )
        )

    # 2. Search Topics
    top_query = (
        db.query(Topic)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .join(Subject, Chapter.subject_id == Subject.id)
        .join(ClassGrade, Subject.class_id == ClassGrade.id)
        .filter(or_(Topic.title.ilike(search_term), Topic.description.ilike(search_term)))
    )
    if board_id:
        top_query = top_query.filter(Subject.board_id == board_id)
    if class_grade:
        top_query = top_query.filter(ClassGrade.grade_number == class_grade)
    if subject_id:
        top_query = top_query.filter(Chapter.subject_id == subject_id)

    for t in top_query.all():
        results.append(
            SearchResultItem(
                result_type="topic",
                id=t.id,
                title=t.title,
                snippet=t.description[:180] if t.description else None,
                board_id=t.chapter.subject.board_id,
                class_grade_number=t.chapter.subject.class_grade.grade_number,
                subject_id=t.chapter.subject_id,
                subject_name=t.chapter.subject.name,
                chapter_id=t.chapter_id,
                chapter_title=t.chapter.title,
                topic_id=t.id,
                verification_status=t.verification_status,
            )
        )

    # 3. Search Lessons
    les_query = (
        db.query(Lesson)
        .join(Topic, Lesson.topic_id == Topic.id)
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .join(Subject, Chapter.subject_id == Subject.id)
        .join(ClassGrade, Subject.class_id == ClassGrade.id)
        .filter(or_(Lesson.title.ilike(search_term), Lesson.content.ilike(search_term), Lesson.summary.ilike(search_term)))
    )
    if board_id:
        les_query = les_query.filter(Subject.board_id == board_id)
    if class_grade:
        les_query = les_query.filter(ClassGrade.grade_number == class_grade)
    if subject_id:
        les_query = les_query.filter(Chapter.subject_id == subject_id)

    for l in les_query.all():
        results.append(
            SearchResultItem(
                result_type="lesson",
                id=l.id,
                title=f"Lesson: {l.title} ({l.section_type})",
                snippet=l.summary or (l.content[:180] if l.content else None),
                board_id=l.topic.chapter.subject.board_id,
                class_grade_number=l.topic.chapter.subject.class_grade.grade_number,
                subject_id=l.topic.chapter.subject_id,
                subject_name=l.topic.chapter.subject.name,
                chapter_id=l.topic.chapter_id,
                chapter_title=l.topic.chapter.title,
                topic_id=l.topic_id,
                verification_status=l.verification_status,
            )
        )

    total = len(results)
    paginated_items = results[offset : offset + limit]

    return PaginatedResponse(
        items=paginated_items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )
