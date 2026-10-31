import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatSession, ChatMessage, Chapter
from app.services.retrieval_service import TextbookRetrievalService
from app.services.gemini_service import (
    GeminiService,
    GeminiAuthError,
    GeminiQuotaError,
    GeminiError,
    CitationRef,
)

router = APIRouter(prefix="/tutor", tags=["AI Learning Coach"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_uuid: Optional[str] = None
    board_code: str = "TELANGANA_STATE_BOARD"
    grade_number: int = Field(default=10, ge=6, le=10)
    subject_name: str = "Mathematics"
    chapter_id: Optional[int] = None
    topic_id: Optional[int] = None
    language: str = "English"


class ChatResponse(BaseModel):
    session_uuid: str
    reply: str
    key_points: List[str] = Field(default_factory=list)
    hints: List[str] = Field(default_factory=list)
    is_textbook_grounded: bool
    grounding_notes: str = ""
    citations: List[CitationRef] = Field(default_factory=list)
    model_name: str


class SessionMessageRead(BaseModel):
    id: int
    role: str
    content: str
    is_grounded: bool
    citations: Optional[List[Dict[str, Any]]] = None
    created_at: str


class SessionHistoryResponse(BaseModel):
    session_uuid: str
    board_code: str
    grade_number: int
    subject_name: str
    language: str
    messages: List[SessionMessageRead]


@router.get("/status")
def get_tutor_status():
    """Returns the operational and authentication status of the Gemini AI tutor."""
    gemini = GeminiService()
    is_ready, status_msg = gemini.is_available()
    return {
        "is_available": is_ready,
        "model": gemini.model,
        "message": status_msg,
    }


@router.post("/chat", response_model=ChatResponse)
def chat_with_tutor(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Submits a student question to the textbook-grounded AI tutor.
    Retrieves official curriculum passages and generates pedagogical explanations with citations.
    """
    # 1. Resolve or create ChatSession
    session_obj = None
    if req.session_uuid:
        session_obj = db.query(ChatSession).filter_by(session_uuid=req.session_uuid).first()

    if not session_obj:
        session_obj = ChatSession(
            session_uuid=req.session_uuid or str(uuid.uuid4()),
            board_code=req.board_code,
            grade_number=req.grade_number,
            subject_name=req.subject_name,
            chapter_id=req.chapter_id,
            topic_id=req.topic_id,
            language=req.language,
        )
        db.add(session_obj)
        db.flush()

    # 2. Record User Message
    user_msg = ChatMessage(
        session_id=session_obj.id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    db.flush()

    # 3. Retrieve Grounded Textbook Passages
    retriever = TextbookRetrievalService(db)
    retrieval_res = retriever.retrieve_passages(
        query=req.message,
        board_code=req.board_code,
        grade_number=req.grade_number,
        subject_name=req.subject_name,
        chapter_id=req.chapter_id,
        top_k=4,
    )

    passages_payload = [
        {
            "source_title": p.source_title,
            "page_number": p.page_number,
            "heading": p.heading,
            "content": p.content,
        }
        for p in retrieval_res.passages
    ]

    # Fetch recent conversation history
    recent_msgs = (
        db.query(ChatMessage)
        .filter_by(session_id=session_obj.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(6)
        .all()
    )
    history_payload = [{"role": m.role, "content": m.content} for m in reversed(recent_msgs)]

    # 4. Generate Response with Gemini
    gemini = GeminiService()
    try:
        tutor_result = gemini.ask_tutor(
            query=req.message,
            retrieved_passages=passages_payload,
            grade=req.grade_number,
            subject=req.subject_name,
            language=req.language,
            history=history_payload,
        )
    except GeminiAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Gemini API authentication failed: {e.message}",
        )
    except GeminiQuotaError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Gemini API rate limit or quota exceeded: {e.message}",
        )
    except GeminiError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI model error: {e.message}",
        )

    # 5. Record Assistant Message in DB
    citation_dicts = [c.model_dump() for c in tutor_result.citations]
    assistant_msg = ChatMessage(
        session_id=session_obj.id,
        role="assistant",
        content=tutor_result.explanation,
        is_grounded=tutor_result.is_textbook_grounded,
        citations=citation_dicts,
        model_name=gemini.model,
    )
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        session_uuid=session_obj.session_uuid,
        reply=tutor_result.explanation,
        key_points=tutor_result.key_points,
        hints=tutor_result.hints,
        is_textbook_grounded=tutor_result.is_textbook_grounded,
        grounding_notes=tutor_result.grounding_notes,
        citations=tutor_result.citations,
        model_name=gemini.model,
    )


@router.get("/sessions/{session_uuid}", response_model=SessionHistoryResponse)
def get_session_history(session_uuid: str, db: Session = Depends(get_db)):
    """Retrieves full conversation history and textbook citations for a session."""
    session_obj = db.query(ChatSession).filter_by(session_uuid=session_uuid).first()
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found",
        )

    messages = [
        SessionMessageRead(
            id=m.id,
            role=m.role,
            content=m.content,
            is_grounded=m.is_grounded,
            citations=m.citations,
            created_at=m.created_at.isoformat(),
        )
        for m in session_obj.messages
    ]

    return SessionHistoryResponse(
        session_uuid=session_obj.session_uuid,
        board_code=session_obj.board_code,
        grade_number=session_obj.grade_number,
        subject_name=session_obj.subject_name,
        language=session_obj.language,
        messages=messages,
    )
