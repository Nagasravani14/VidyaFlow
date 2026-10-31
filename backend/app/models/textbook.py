from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class TextbookDocument(Base):
    """Catalog of downloaded and indexed official textbook documents."""
    __tablename__ = "textbook_documents"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String(500), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256
    title = Column(String(255), nullable=False)
    board_code = Column(String(50), nullable=False, index=True)  # e.g., TELANGANA_STATE_BOARD, ICSE
    grade_number = Column(Integer, nullable=False, index=True)  # 6-10
    subject_name = Column(String(100), nullable=False, index=True)  # Mathematics, Physical Science, etc.
    language = Column(String(20), default="English", nullable=False)
    academic_year = Column(String(20), default="2024-2025", nullable=False)
    total_pages = Column(Integer, default=0, nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    extraction_status = Column(String(30), default="completed", nullable=False)  # completed, needs_review, failed
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    passages = relationship("TextbookPassage", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TextbookDocument(title='{self.title}', board='{self.board_code}', grade={self.grade_number})>"


class TextbookPassage(Base):
    """Extracted textbook text passages indexed with page numbers and curriculum linkage."""
    __tablename__ = "textbook_passages"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("textbook_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    page_number = Column(Integer, nullable=False, index=True)
    heading = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    passage_index = Column(Integer, default=0, nullable=False)
    language = Column(String(20), default="en", nullable=False)
    verification_status = Column(String(30), default="verified", nullable=False)  # verified, needs_review
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_passages_doc_page", "document_id", "page_number"),
    )

    # Relationships
    document = relationship("TextbookDocument", back_populates="passages")
    chapter = relationship("Chapter")
    topic = relationship("Topic")

    def __repr__(self):
        return f"<TextbookPassage(doc_id={self.document_id}, page={self.page_number}, heading='{self.heading}')>"
