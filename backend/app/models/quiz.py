"""
Student practice / adaptive quiz data model.

IMPORTANT - separation rule
---------------------------
Everything in this module is *student practice* data. Teacher-assigned work
(worksheets, assignments) must live in its own tables and must never be
written to ``questions``. The ``assessment_purpose`` CHECK below makes that a
database-level guarantee: only ``practice | diagnostic | revision`` can be stored.

``student_id`` is deliberately a plain indexed string with no foreign key.
There is no students table yet; real authentication will later supply the same
value (see ``app/api/deps_student.py``) without a schema change.

Stored question shapes (``options`` / ``correct_answer`` JSON)
--------------------------------------------------------------
mcq / logical_reasoning / assertion_reasoning
    options        = [{"key": "A", "text": "..."}, ...]   (4 entries)
    correct_answer = "B"                                   (a single option KEY)
multi_select
    options        = [{"key": "A", "text": "..."}, ...]
    correct_answer = ["A", "C"]                            (sorted option KEYS)
true_false
    options        = null
    correct_answer = true | false
fill_blank
    options        = null
    correct_answer = ["accepted answer", "alt spelling"]
numerical
    options        = null
    correct_answer = {"value": "7", "tolerance": 0}
short_answer / application
    options        = null
    correct_answer = {"keywords": [["any", "of"], ["these"]], "model_answer": "..."}
step_by_step
    options        = {"steps": [{"prompt": "...", "hint": "..."}]}   (safe to send to the browser)
    correct_answer = ["step 1 answer", "step 2 answer", ...]          (server only)

Answer keys (``correct_answer``, ``distractor_misconceptions``) are NEVER sent
to the browser before the answer is submitted.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ---- allowed values (kept here so migration, models and validators agree) ----
ASSESSMENT_PURPOSES = ("practice", "diagnostic", "revision")
QUIZ_MODES = ASSESSMENT_PURPOSES
QUESTION_SOURCES = ("ai", "curated")
QUESTION_TYPES = (
    "mcq",
    "multi_select",
    "true_false",
    "fill_blank",
    "numerical",
    "short_answer",
    "application",
    "logical_reasoning",
    "assertion_reasoning",
    "step_by_step",
)
BLOOM_LEVELS = ("remember", "understand", "apply", "analyze", "evaluate")
DIFFICULTIES = ("easy", "medium", "hard")
MASTERY_STATUSES = (
    "locked",
    "not_started",
    "learning",
    "weak",
    "needs_revision",
    "mastered",
)
QUIZ_STATUSES = ("in_progress", "finished")

# Level -> Bloom level (L1 remember ... L5 evaluate). One level per question.
LEVEL_TO_BLOOM = {1: "remember", 2: "understand", 3: "apply", 4: "analyze", 5: "evaluate"}


def _in(column: str, values) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, index=True)
    class_num = Column(Integer, nullable=False)  # "class" is a Python keyword
    subject = Column(String(100), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    # Retrieval hints for Chroma metadata filtering {"board","class","subject","chapter"}
    board = Column(String(20), default="TS", nullable=False)
    chapter = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("class_num", "subject", "name", name="uq_concept_class_subject_name"),
        CheckConstraint("class_num BETWEEN 1 AND 12", name="ck_concept_class_range"),
    )

    prerequisite_edges = relationship(
        "ConceptPrerequisite",
        foreign_keys="ConceptPrerequisite.concept_id",
        back_populates="concept",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Concept(id={self.id}, class={self.class_num}, name='{self.name}')>"


class ConceptPrerequisite(Base):
    """Edge: ``concept_id`` requires ``prerequisite_concept_id``."""

    __tablename__ = "concept_prerequisites"

    id = Column(Integer, primary_key=True)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    prerequisite_concept_id = Column(
        Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("concept_id", "prerequisite_concept_id", name="uq_concept_prereq_pair"),
        CheckConstraint("concept_id <> prerequisite_concept_id", name="ck_concept_prereq_not_self"),
    )

    concept = relationship("Concept", foreign_keys=[concept_id], back_populates="prerequisite_edges")
    prerequisite = relationship("Concept", foreign_keys=[prerequisite_concept_id])


class Question(Base):
    """A single practice question. Teacher assignments are NOT stored here."""

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    learning_objective = Column(Text, nullable=True)
    level = Column(Integer, nullable=False)  # 1..5
    bloom_level = Column(String(20), nullable=False)
    question_type = Column(String(30), nullable=False)
    difficulty = Column(String(10), nullable=False)
    stem = Column(Text, nullable=False)
    options = Column(JSON, nullable=True)
    correct_answer = Column(JSON, nullable=False)  # server-side only
    explanation = Column(Text, nullable=False)
    hint = Column(Text, nullable=True)
    assessment_purpose = Column(String(20), default="practice", nullable=False)
    distractor_misconceptions = Column(JSON, nullable=True)  # {"A": "added instead of subtracted"}
    language = Column(String(10), default="en", nullable=False)
    source = Column(String(10), nullable=False)  # ai | curated
    content_hash = Column(String(64), nullable=False)  # sha256 of type + digit-masked stem
    embedding = Column(JSON, nullable=True)  # list[float]; filled by the quiz engine
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("concept_id", "content_hash", name="uq_question_concept_hash"),
        CheckConstraint("level BETWEEN 1 AND 5", name="ck_question_level_range"),
        CheckConstraint(_in("bloom_level", BLOOM_LEVELS), name="ck_question_bloom"),
        CheckConstraint(_in("question_type", QUESTION_TYPES), name="ck_question_type"),
        CheckConstraint(_in("difficulty", DIFFICULTIES), name="ck_question_difficulty"),
        # Teacher-assignment content can never be stored as a practice question.
        CheckConstraint(_in("assessment_purpose", ASSESSMENT_PURPOSES), name="ck_question_purpose"),
        CheckConstraint(_in("source", QUESTION_SOURCES), name="ck_question_source"),
        Index("ix_questions_concept_level", "concept_id", "level"),
    )

    concept = relationship("Concept")

    def __repr__(self):
        return f"<Question(id={self.id}, concept={self.concept_id}, L{self.level}, {self.question_type})>"


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(64), nullable=False, index=True)
    mode = Column(String(20), default="practice", nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    current_level = Column(Integer, default=1, nullable=False)
    # Extra (beyond the spec) - needed by the endpoints:
    target_level = Column(Integer, nullable=True)  # "Practice this level" aims back at the struggling level
    status = Column(String(20), default="in_progress", nullable=False)
    current_question_id = Column(Integer, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    score = Column(Float, nullable=True)  # fraction correct 0..1, set on finish

    __table_args__ = (
        CheckConstraint(_in("mode", QUIZ_MODES), name="ck_quiz_attempt_mode"),
        CheckConstraint(_in("status", QUIZ_STATUSES), name="ck_quiz_attempt_status"),
        CheckConstraint("current_level BETWEEN 1 AND 5", name="ck_quiz_attempt_level"),
        Index("ix_quiz_attempts_student_started", "student_id", "started_at"),
    )

    concept = relationship("Concept")
    question_attempts = relationship(
        "QuestionAttempt", back_populates="quiz_attempt", cascade="all, delete-orphan"
    )


class QuestionAttempt(Base):
    """One submission for one question. attempt_no 1 = first try, 2 = retry after the hint."""

    __tablename__ = "question_attempts"

    id = Column(Integer, primary_key=True, index=True)
    quiz_attempt_id = Column(
        Integer, ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id = Column(String(64), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(Integer, nullable=False)
    answer = Column(JSON, nullable=True)
    is_correct = Column(Boolean, nullable=False)
    hints_used = Column(Integer, default=0, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    attempt_no = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 5", name="ck_question_attempt_level"),
        CheckConstraint("attempt_no >= 1", name="ck_question_attempt_no"),
        Index("ix_question_attempts_student_question", "student_id", "question_id"),
    )

    quiz_attempt = relationship("QuizAttempt", back_populates="question_attempts")
    question = relationship("Question")


class StudentConceptLevel(Base):
    __tablename__ = "student_concept_level"

    id = Column(Integer, primary_key=True)
    student_id = Column(String(64), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    comfortable_level = Column(Integer, default=1, nullable=False)
    max_level_reached = Column(Integer, default=1, nullable=False)
    struggling_level = Column(Integer, nullable=True)
    struggling_since = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Policy state (extra, see level_policy.py). Kept as columns so the dashboard
    # and the pure policy function read exactly what is stored.
    failed_counts = Column(JSON, default=dict, nullable=False)  # {"4": 1}: failed questions per level since last pass
    correct_streak = Column(Integer, default=0, nullable=False)  # correct answers at comfortable level since last failure
    low_level_failures = Column(Integer, default=0, nullable=False)  # failures at L1/L2
    possible_prerequisite_gap = Column(Boolean, default=False, nullable=False)
    prerequisite_gap_concept_id = Column(
        Integer, ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("student_id", "concept_id", name="uq_student_concept_level"),
        CheckConstraint("comfortable_level BETWEEN 1 AND 5", name="ck_scl_comfortable"),
        CheckConstraint("max_level_reached BETWEEN 1 AND 5", name="ck_scl_max"),
        CheckConstraint(
            "struggling_level IS NULL OR struggling_level BETWEEN 1 AND 5", name="ck_scl_struggling"
        ),
        Index("ix_scl_student", "student_id"),
    )

    concept = relationship("Concept", foreign_keys=[concept_id])
    prerequisite_gap_concept = relationship("Concept", foreign_keys=[prerequisite_gap_concept_id])


class StudentConceptMastery(Base):
    __tablename__ = "student_concept_mastery"

    id = Column(Integer, primary_key=True)
    student_id = Column(String(64), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    mastery_score = Column(Float, default=0.0, nullable=False)  # 0..1
    evidence_count = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="not_started", nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "concept_id", name="uq_student_concept_mastery"),
        CheckConstraint("mastery_score BETWEEN 0 AND 1", name="ck_mastery_range"),
        CheckConstraint(_in("status", MASTERY_STATUSES), name="ck_mastery_status"),
        Index("ix_scm_student", "student_id"),
    )

    concept = relationship("Concept")
