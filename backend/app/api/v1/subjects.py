from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Subject, Chapter, ClassGrade, Board
from app.schemas import SubjectSummary, SubjectDetail

router = APIRouter()


@router.get("/subjects", response_model=List[SubjectSummary], tags=["Subjects"])
def list_subjects(
    board_id: Optional[int] = Query(None, description="Filter by Board ID"),
    board_code: Optional[str] = Query(None, description="Filter by Board Code (e.g., 'TELANGANA_STATE_BOARD')"),
    class_grade: Optional[int] = Query(None, ge=6, le=10, description="Filter by Class grade number (6-10)"),
    category: Optional[str] = Query(None, description="Filter by category: STEM, Humanities, Languages"),
    db: Session = Depends(get_db),
):
    """List curriculum subjects with optional filtering by board and class."""
    query = db.query(Subject).join(ClassGrade, Subject.class_id == ClassGrade.id)

    if board_id is not None:
        query = query.filter(Subject.board_id == board_id)
    if board_code is not None:
        query = query.join(Board, Subject.board_id == Board.id).filter(Board.code == board_code)
    if class_grade is not None:
        query = query.filter(ClassGrade.grade_number == class_grade)
    if category is not None:
        query = query.filter(Subject.category == category)

    subjects = query.order_by(ClassGrade.grade_number, Subject.name).all()

    # Enrich with chapter count and grade number
    result = []
    for s in subjects:
        ch_count = db.query(func.count(Chapter.id)).filter(Chapter.subject_id == s.id).scalar()
        summary = SubjectSummary.model_validate(s)
        summary.chapter_count = ch_count
        summary.class_grade_number = s.class_grade.grade_number if s.class_grade else None
        result.append(summary)

    return result


@router.get("/subjects/{subject_id}", response_model=SubjectDetail, tags=["Subjects"])
def get_subject_detail(subject_id: int, db: Session = Depends(get_db)):
    """Retrieve detailed subject information including all chapters."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with id {subject_id} not found",
        )

    ch_count = len(subject.chapters)
    detail = SubjectDetail.model_validate(subject)
    detail.chapter_count = ch_count
    detail.class_grade_number = subject.class_grade.grade_number if subject.class_grade else None
    return detail
