import pytest
from sqlalchemy.exc import IntegrityError
from app.models import (
    Board,
    ClassGrade,
    Subject,
    Chapter,
    Topic,
    LearningObjective,
    Lesson,
    PracticeQuestion,
    QuestionOption,
)


def test_create_board_and_constraints(db_session):
    board = Board(code="TS_TEST", name="Telangana Test Board", country="India")
    db_session.add(board)
    db_session.commit()

    assert board.id is not None
    assert board.name == "Telangana Test Board"

    # Duplicate board code should fail
    dup = Board(code="TS_TEST", name="Duplicate Board")
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_class_grades_pre_seeded(db_session):
    grades = db_session.query(ClassGrade).all()
    grade_numbers = [g.grade_number for g in grades]
    assert sorted(grade_numbers) == [6, 7, 8, 9, 10]


def test_subject_and_chapter_hierarchy(db_session):
    board = Board(code="TS_HIER", name="Telangana Hierarchy")
    db_session.add(board)
    db_session.commit()

    class_10 = db_session.query(ClassGrade).filter_by(grade_number=10).first()

    subj = Subject(
        board_id=board.id,
        class_id=class_10.id,
        code="TS_10_TEST_M",
        name="Mathematics",
        category="STEM",
    )
    db_session.add(subj)
    db_session.commit()

    ch1 = Chapter(
        subject_id=subj.id,
        chapter_number=1,
        code="TS_10_M_CH01",
        title="Real Numbers",
        estimated_minutes=90,
    )
    db_session.add(ch1)
    db_session.commit()

    assert ch1.id is not None
    assert len(subj.chapters) == 1

    # Duplicate chapter number in same subject should fail
    dup_ch = Chapter(
        subject_id=subj.id,
        chapter_number=1,
        code="TS_10_M_CH01_DUP",
        title="Real Numbers Duplicate",
    )
    db_session.add(dup_ch)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_topic_and_practice_questions(db_session):
    board = Board(code="TS_Q", name="Question Test Board")
    db_session.add(board)
    db_session.commit()
    class_8 = db_session.query(ClassGrade).filter_by(grade_number=8).first()

    subj = Subject(board_id=board.id, class_id=class_8.id, code="TS_8_Q_SUBJ", name="Math")
    db_session.add(subj)
    db_session.commit()

    ch = Chapter(subject_id=subj.id, chapter_number=1, code="TS_8_CH1", title="Linear Equations")
    db_session.add(ch)
    db_session.commit()

    topic = Topic(chapter_id=ch.id, topic_code="TS_8_T1", title="Solving Equations")
    db_session.add(topic)
    db_session.commit()

    q = PracticeQuestion(
        topic_id=topic.id,
        question_code="Q_TEST_01",
        question_text="Solve: 2x = 10",
        question_type="multiple_choice",
        difficulty_level="easy",
        worked_explanation="x = 10/2 = 5",
        correct_answer="0",
    )
    db_session.add(q)
    db_session.commit()

    opt1 = QuestionOption(question_id=q.id, option_index=0, option_text="x = 5", is_correct=True)
    opt2 = QuestionOption(question_id=q.id, option_index=1, option_text="x = 4", is_correct=False)
    db_session.add_all([opt1, opt2])
    db_session.commit()

    assert len(topic.practice_questions) == 1
    assert len(q.options) == 2
    assert q.options[0].is_correct is True
