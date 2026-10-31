from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SourceAttribution(Base):
    """Source reference and content verification status."""
    __tablename__ = "source_attributions"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(50), nullable=False)  # official_textbook, syllabus_guidelines, reference
    publisher = Column(String(100), nullable=False)  # SCERT Telangana, CISCE, NCERT
    publication_year = Column(Integer, nullable=True)  # e.g., 2024
    edition = Column(String(100), nullable=True)  # "2024-25 Revised Edition"
    title = Column(String(255), nullable=False)  # "Class 10 Mathematics"
    page_reference = Column(String(100), nullable=True)  # "pp. 14-22"
    license_or_permission_status = Column(String(100), default="public_curriculum_framework", nullable=False)
    verification_status = Column(String(30), default="verified", nullable=False)  # verified, draft, unverified
    verified_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    lessons = relationship("Lesson", back_populates="source_attribution")
    worked_examples = relationship("WorkedExample", back_populates="source_attribution")
    practice_questions = relationship("PracticeQuestion", back_populates="source_attribution")

    def __repr__(self):
        return f"<SourceAttribution(title='{self.title}', publisher='{self.publisher}')>"


class Lesson(Base):
    """Lesson content and explanations broken into concept sections."""
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    source_attribution_id = Column(Integer, ForeignKey("source_attributions.id", ondelete="SET NULL"), nullable=True)
    syllabus_version_id = Column(Integer, ForeignKey("syllabus_versions.id", ondelete="SET NULL"), nullable=True)
    section_type = Column(String(50), default="explanation", nullable=False)  # explanation, key_concepts, recap, summary
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    language = Column(String(10), default="en", nullable=False)  # en, te, hi
    reading_time_minutes = Column(Integer, default=5, nullable=False)
    order_index = Column(Integer, default=1, nullable=False)
    verification_status = Column(String(30), default="verified", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_lessons_topic_order", "topic_id", "order_index"),
    )

    # Relationships
    topic = relationship("Topic", back_populates="lessons")
    source_attribution = relationship("SourceAttribution", back_populates="lessons")
    syllabus_version = relationship("SyllabusVersion", back_populates="lessons")

    def __repr__(self):
        return f"<Lesson(title='{self.title}', section_type='{self.section_type}')>"


class WorkedExample(Base):
    """Step-by-step worked example solving a problem."""
    __tablename__ = "worked_examples"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    source_attribution_id = Column(Integer, ForeignKey("source_attributions.id", ondelete="SET NULL"), nullable=True)
    example_number = Column(Integer, default=1, nullable=False)
    problem_statement = Column(Text, nullable=False)
    step_by_step_solution = Column(Text, nullable=False)
    verification_step = Column(Text, nullable=True)
    key_takeaway = Column(Text, nullable=True)
    language = Column(String(10), default="en", nullable=False)
    verification_status = Column(String(30), default="verified", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    topic = relationship("Topic", back_populates="worked_examples")
    source_attribution = relationship("SourceAttribution", back_populates="worked_examples")

    def __repr__(self):
        return f"<WorkedExample(topic_id={self.topic_id}, example_number={self.example_number})>"


class PracticeQuestion(Base):
    """Practice question with hints and worked explanation."""
    __tablename__ = "practice_questions"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    source_attribution_id = Column(Integer, ForeignKey("source_attributions.id", ondelete="SET NULL"), nullable=True)
    question_code = Column(String(100), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), default="multiple_choice", nullable=False)  # multiple_choice, numerical, short_answer
    difficulty_level = Column(String(20), default="medium", nullable=False)  # easy, medium, hard
    marks = Column(Integer, default=1, nullable=False)
    hint = Column(Text, nullable=True)
    worked_explanation = Column(Text, nullable=False)
    correct_answer = Column(Text, nullable=False)
    language = Column(String(10), default="en", nullable=False)
    verification_status = Column(String(30), default="verified", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("topic_id", "question_code", name="uq_topic_question_code"),
    )

    # Relationships
    topic = relationship("Topic", back_populates="practice_questions")
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.option_index")
    source_attribution = relationship("SourceAttribution", back_populates="practice_questions")

    def __repr__(self):
        return f"<PracticeQuestion(code='{self.question_code}', type='{self.question_type}')>"


class QuestionOption(Base):
    """Multiple choice option for a practice question."""
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("practice_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    option_index = Column(Integer, nullable=False)  # 0, 1, 2, 3
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    feedback = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("question_id", "option_index", name="uq_question_option_index"),
    )

    # Relationships
    question = relationship("PracticeQuestion", back_populates="options")

    def __repr__(self):
        return f"<QuestionOption(question_id={self.question_id}, index={self.option_index}, correct={self.is_correct})>"


class PrerequisiteRelationship(Base):
    """Prerequisite mapping between concepts/topics for the adaptive learning map."""
    __tablename__ = "prerequisite_relationships"

    id = Column(Integer, primary_key=True, index=True)
    target_topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    prerequisite_topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(30), default="required", nullable=False)  # required, recommended, remedial
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("target_topic_id", "prerequisite_topic_id", name="uq_prerequisite_pair"),
    )

    # Relationships
    target_topic = relationship("Topic", foreign_keys=[target_topic_id], back_populates="prerequisites")
    prerequisite_topic = relationship("Topic", foreign_keys=[prerequisite_topic_id], back_populates="dependent_topics")

    def __repr__(self):
        return f"<PrerequisiteRelationship(target={self.target_topic_id}, req={self.prerequisite_topic_id})>"
