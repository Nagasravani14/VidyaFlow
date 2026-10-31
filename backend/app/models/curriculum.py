from datetime import datetime, timezone
from typing import List, Optional
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
from sqlalchemy.orm import relationship, Mapped
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Board(Base):
    """Education board (e.g., Telangana State Board / SCERT, ICSE)."""
    __tablename__ = "boards"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    full_name = Column(String(255), nullable=True)
    country = Column(String(50), default="India", nullable=False)
    state_or_region = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    syllabus_versions = relationship("SyllabusVersion", back_populates="board", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="board", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Board(code='{self.code}', name='{self.name}')>"


class SyllabusVersion(Base):
    """Academic year or syllabus revision versioning."""
    __tablename__ = "syllabus_versions"

    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    version_code = Column(String(50), nullable=False)  # e.g., "2024-2025"
    academic_year = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("board_id", "version_code", name="uq_board_syllabus_version"),
    )

    # Relationships
    board = relationship("Board", back_populates="syllabus_versions")
    subjects = relationship("Subject", back_populates="syllabus_version")
    lessons = relationship("Lesson", back_populates="syllabus_version")

    def __repr__(self):
        return f"<SyllabusVersion(board_id={self.board_id}, version_code='{self.version_code}')>"


class ClassGrade(Base):
    """Academic class level (Classes 6 to 10)."""
    __tablename__ = "class_grades"

    id = Column(Integer, primary_key=True, index=True)
    grade_number = Column(Integer, unique=True, nullable=False, index=True)  # 6, 7, 8, 9, 10
    code = Column(String(20), unique=True, nullable=False)  # "CLASS_6", etc.
    name = Column(String(50), nullable=False)  # "Class 6", etc.
    stage = Column(String(50), default="Secondary", nullable=False)  # "Middle School", "Secondary"

    # Relationships
    subjects = relationship("Subject", back_populates="class_grade", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ClassGrade(grade_number={self.grade_number})>"


class Subject(Base):
    """Subject within a board and class (e.g., Mathematics, Physical Science)."""
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    board_id = Column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("class_grades.id", ondelete="CASCADE"), nullable=False, index=True)
    syllabus_version_id = Column(Integer, ForeignKey("syllabus_versions.id", ondelete="SET NULL"), nullable=True)
    code = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "TS_CLASS_10_MATH"
    name = Column(String(100), nullable=False)  # "Mathematics"
    category = Column(String(50), default="STEM", nullable=False)  # STEM, Humanities, Languages
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("board_id", "class_id", "name", name="uq_board_class_subject_name"),
        Index("ix_subjects_board_class", "board_id", "class_id"),
    )

    # Relationships
    board = relationship("Board", back_populates="subjects")
    class_grade = relationship("ClassGrade", back_populates="subjects")
    syllabus_version = relationship("SyllabusVersion", back_populates="subjects")
    chapters = relationship("Chapter", back_populates="subject", cascade="all, delete-orphan", order_by="Chapter.chapter_number")

    def __repr__(self):
        return f"<Subject(code='{self.code}', name='{self.name}')>"


class Chapter(Base):
    """Chapter within a subject (e.g., Real Numbers, Linear Equations)."""
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False)
    code = Column(String(100), nullable=False, index=True)  # e.g., "TS_10_MATH_CH01"
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    estimated_minutes = Column(Integer, default=90, nullable=False)
    order_index = Column(Integer, default=1, nullable=False)
    verification_status = Column(String(30), default="verified", nullable=False)  # "verified", "draft", "unverified"
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("subject_id", "chapter_number", name="uq_subject_chapter_number"),
        UniqueConstraint("subject_id", "code", name="uq_subject_chapter_code"),
        Index("ix_chapters_subject_order", "subject_id", "order_index"),
    )

    # Relationships
    subject = relationship("Subject", back_populates="chapters")
    topics = relationship("Topic", back_populates="chapter", cascade="all, delete-orphan", order_by="Topic.order_index")
    learning_objectives = relationship("LearningObjective", back_populates="chapter", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chapter(code='{self.code}', title='{self.title}')>"


class Topic(Base):
    """Topic or subtopic within a chapter."""
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True)
    topic_code = Column(String(100), nullable=False, index=True)  # e.g., "TS_10_MATH_CH01_T01"
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=1, nullable=False)
    estimated_minutes = Column(Integer, default=30, nullable=False)
    verification_status = Column(String(30), default="verified", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("chapter_id", "topic_code", name="uq_chapter_topic_code"),
        Index("ix_topics_chapter_order", "chapter_id", "order_index"),
    )

    # Relationships
    chapter = relationship("Chapter", back_populates="topics")
    subtopics = relationship("Topic", back_populates="parent_topic", cascade="all, delete-orphan")
    parent_topic = relationship("Topic", back_populates="subtopics", remote_side=[id])

    learning_objectives = relationship("LearningObjective", back_populates="topic", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="topic", cascade="all, delete-orphan", order_by="Lesson.order_index")
    worked_examples = relationship("WorkedExample", back_populates="topic", cascade="all, delete-orphan")
    practice_questions = relationship("PracticeQuestion", back_populates="topic", cascade="all, delete-orphan")

    # Prerequisite relationships
    prerequisites = relationship(
        "PrerequisiteRelationship",
        foreign_keys="PrerequisiteRelationship.target_topic_id",
        back_populates="target_topic",
        cascade="all, delete-orphan",
    )
    dependent_topics = relationship(
        "PrerequisiteRelationship",
        foreign_keys="PrerequisiteRelationship.prerequisite_topic_id",
        back_populates="prerequisite_topic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Topic(code='{self.topic_code}', title='{self.title}')>"


class LearningObjective(Base):
    """Specific measurable learning objective for a chapter or topic."""
    __tablename__ = "learning_objectives"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True)
    code = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    bloom_taxonomy_level = Column(String(30), default="understand", nullable=False)  # remember, understand, apply, analyze, evaluate, create
    order_index = Column(Integer, default=1, nullable=False)

    # Relationships
    chapter = relationship("Chapter", back_populates="learning_objectives")
    topic = relationship("Topic", back_populates="learning_objectives")

    def __repr__(self):
        return f"<LearningObjective(code='{self.code}', bloom='{self.bloom_taxonomy_level}')>"
