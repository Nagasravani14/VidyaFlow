from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Board, ClassGrade, Subject
from app.schemas import BoardRead, ClassGradeRead

router = APIRouter()


@router.get("/boards", response_model=List[BoardRead], tags=["Boards"])
def list_boards(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
):
    """List all supported educational boards (e.g., Telangana State Board, ICSE)."""
    query = db.query(Board)
    if is_active is not None:
        query = query.filter(Board.is_active == is_active)
    return query.order_by(Board.name).all()


@router.get("/boards/{board_id}", response_model=BoardRead, tags=["Boards"])
def get_board(board_id: int, db: Session = Depends(get_db)):
    """Retrieve details of a specific board."""
    board = db.query(Board).filter(Board.id == board_id).first()
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Board with id {board_id} not found",
        )
    return board


@router.get("/classes", response_model=List[ClassGradeRead], tags=["Classes"])
def list_classes(db: Session = Depends(get_db)):
    """List all supported academic classes (Classes 6 to 10)."""
    return db.query(ClassGrade).order_by(ClassGrade.grade_number).all()


@router.get("/boards/{board_id}/classes", response_model=List[ClassGradeRead], tags=["Boards"])
def list_classes_for_board(board_id: int, db: Session = Depends(get_db)):
    """List all classes that have active subjects configured for the given board."""
    board = db.query(Board).filter(Board.id == board_id).first()
    if not board:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Board with id {board_id} not found",
        )

    # Find classes that have subjects in this board
    classes = (
        db.query(ClassGrade)
        .join(Subject, Subject.class_id == ClassGrade.id)
        .filter(Subject.board_id == board_id)
        .distinct()
        .order_by(ClassGrade.grade_number)
        .all()
    )

    # If no subjects yet, return all available classes 6-10
    if not classes:
        classes = db.query(ClassGrade).order_by(ClassGrade.grade_number).all()

    return classes
