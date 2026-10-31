from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ChatSession(Base):
    """Grounded AI tutor conversation session."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()), nullable=False, index=True)
    board_code = Column(String(50), default="TELANGANA_STATE_BOARD", nullable=False)
    grade_number = Column(Integer, default=10, nullable=False)
    subject_name = Column(String(100), default="Mathematics", nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    language = Column(String(20), default="English", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    chapter = relationship("Chapter")
    topic = relationship("Topic")

    def __repr__(self):
        return f"<ChatSession(uuid='{self.session_uuid}', grade={self.grade_number}, subject='{self.subject_name}')>"


class ChatMessage(Base):
    """Individual user or AI message with citations and source groundings."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    is_grounded = Column(Boolean, default=True, nullable=False)
    citations = Column(JSON, nullable=True)  # List of { source, page_number, heading, excerpt }
    model_name = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(role='{self.role}', session_id={self.session_id})>"


class PracticeSubmission(Base):
    """Submitted practice response and evaluation record."""
    __tablename__ = "practice_submissions"

    id = Column(Integer, primary_key=True, index=True)
    # Owner of the submission. Nullable only so rows created before this column existed survive.
    student_id = Column(String(64), nullable=True, index=True)
    question_id = Column(Integer, ForeignKey("practice_questions.id", ondelete="SET NULL"), nullable=True, index=True)
    question_text = Column(Text, nullable=False)
    student_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, default=0.0, nullable=False)
    max_marks = Column(Float, default=1.0, nullable=False)
    feedback = Column(Text, nullable=True)
    worked_explanation = Column(Text, nullable=True)
    evaluation_type = Column(String(30), default="mcq_exact", nullable=False)  # "mcq_exact", "rubric_ai"
    submitted_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    question = relationship("PracticeQuestion")

    def __repr__(self):
        return f"<PracticeSubmission(question_id={self.question_id}, correct={self.is_correct})>"
