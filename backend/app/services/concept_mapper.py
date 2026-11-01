"""
Concept-Chapter mapping service.

Ensures every Chapter across all subjects, classes (6-10), and boards (Telangana, ICSE)
has exactly one corresponding Concept for adaptive quizzes.
"""

from typing import Dict, List, Optional
import logging
from sqlalchemy.orm import Session

from app.models.curriculum import Chapter, Subject, ClassGrade, Board
from app.models.quiz import Concept

logger = logging.getLogger(__name__)


def normalize_board_code(board_str: str) -> str:
    """Normalize board identifiers into canonical 'TS' or 'ICSE'."""
    b = (board_str or "").strip().upper()
    if "TS" in b or "TELANGANA" in b or "SCERT" in b:
        return "TS"
    if "ICSE" in b or "CISCE" in b:
        return "ICSE"
    return b or "TS"


def ensure_chapter_concepts(db: Session) -> Dict[str, int]:
    """
    Idempotent function that maps every curriculum Chapter to exactly one Concept.
    Concept name = chapter title; copies class, subject, and board from the chapter.

    Returns summary: {"created": int, "linked_existing": int, "already_mapped": int, "total_chapters": int}
    """
    chapters = (
        db.query(Chapter)
        .join(Subject, Chapter.subject_id == Subject.id)
        .join(ClassGrade, Subject.class_id == ClassGrade.id)
        .join(Board, Subject.board_id == Board.id)
        .all()
    )

    created_count = 0
    linked_count = 0
    already_mapped_count = 0

    for chapter in chapters:
        # 1. Check if concept already linked to this chapter_id
        existing = db.query(Concept).filter(Concept.chapter_id == chapter.id).first()
        if existing:
            already_mapped_count += 1
            continue

        class_num = chapter.subject.class_grade.grade_number
        subject_name = chapter.subject.name
        board_code = normalize_board_code(chapter.subject.board.code)
        concept_name = chapter.title.strip()

        # 2. Check if a concept already exists matching (board, class_num, subject, name) without chapter_id
        name_match = (
            db.query(Concept)
            .filter(
                Concept.board == board_code,
                Concept.class_num == class_num,
                Concept.subject == subject_name,
                Concept.name == concept_name,
            )
            .first()
        )

        if name_match and name_match.chapter_id is None:
            name_match.chapter_id = chapter.id
            name_match.chapter = chapter.title
            if not name_match.description and chapter.description:
                name_match.description = chapter.description
            linked_count += 1
            continue

        # 3. Create new concept for this chapter
        new_concept = Concept(
            chapter_id=chapter.id,
            name=concept_name,
            class_num=class_num,
            subject=subject_name,
            board=board_code,
            chapter=chapter.title,
            description=chapter.description or f"Concepts and practice questions for {chapter.title} ({subject_name}, Class {class_num}).",
        )
        db.add(new_concept)
        created_count += 1

    db.commit()
    logger.info(
        "ensure_chapter_concepts complete: created=%d, linked=%d, already_mapped=%d, total=%d",
        created_count,
        linked_count,
        already_mapped_count,
        len(chapters),
    )
    return {
        "created": created_count,
        "linked_existing": linked_count,
        "already_mapped": already_mapped_count,
        "total_chapters": len(chapters),
    }
