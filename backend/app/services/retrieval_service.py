import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models import TextbookDocument, TextbookPassage, Chapter, Subject, ClassGrade


class RetrievedPassage(BaseModel):
    passage_id: int
    source_title: str
    file_path: str
    page_number: int
    heading: Optional[str] = None
    content: str
    relevance_score: float
    chapter_title: Optional[str] = None
    verification_status: str = "verified"


class RetrievalResult(BaseModel):
    query: str
    passages: List[RetrievedPassage]
    total_found: int
    is_sufficient: bool
    context_token_estimate: int


class TextbookRetrievalService:
    """
    Retrieves and ranks grounded textbook passages from the ingested database.
    Designed for fast relational keyword scoring, extensible to vector search.
    """

    def __init__(self, db: Session):
        self.db = db

    def retrieve_passages(
        self,
        query: str,
        board_code: Optional[str] = None,
        grade_number: Optional[int] = None,
        subject_name: Optional[str] = None,
        chapter_id: Optional[int] = None,
        language: str = "en",
        top_k: int = 4,
        min_relevance: float = 0.15,
    ) -> RetrievalResult:
        """
        Retrieves passages matching filters, scored by keyword density and query proximity.
        """
        # Tokenize query keywords (exclude common stop words)
        stop_words = {"what", "is", "how", "to", "the", "a", "an", "of", "and", "in", "for", "with", "explain", "give", "me"}
        tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2 and t.lower() not in stop_words]

        # Base query joined with Document
        base_q = (
            self.db.query(TextbookPassage, TextbookDocument, Chapter)
            .join(TextbookDocument, TextbookPassage.document_id == TextbookDocument.id)
            .outerjoin(Chapter, TextbookPassage.chapter_id == Chapter.id)
        )

        filters = []
        if board_code:
            filters.append(TextbookDocument.board_code == board_code)
        if grade_number:
            filters.append(TextbookDocument.grade_number == grade_number)
        if subject_name:
            filters.append(TextbookDocument.subject_name.ilike(f"%{subject_name}%"))
        if chapter_id:
            filters.append(TextbookPassage.chapter_id == chapter_id)

        if filters:
            base_q = base_q.filter(and_(*filters))

        candidates = base_q.all()

        scored_passages: List[RetrievedPassage] = []
        for passage, doc, ch in candidates:
            score = self._compute_relevance(query, tokens, passage.heading or "", passage.content)
            if score >= min_relevance or not tokens:
                scored_passages.append(
                    RetrievedPassage(
                        passage_id=passage.id,
                        source_title=doc.title,
                        file_path=doc.file_path,
                        page_number=passage.page_number,
                        heading=passage.heading,
                        content=passage.content,
                        relevance_score=score,
                        chapter_title=ch.title if ch else None,
                        verification_status=passage.verification_status,
                    )
                )

        # Sort descending by relevance score
        scored_passages.sort(key=lambda x: x.relevance_score, reverse=True)
        top_passages = scored_passages[:top_k]

        # Estimate token count (approx. 4 chars per token)
        total_chars = sum(len(p.content) for p in top_passages)
        token_estimate = total_chars // 4

        is_sufficient = len(top_passages) > 0 and (top_passages[0].relevance_score >= 0.25 or not tokens)

        return RetrievalResult(
            query=query,
            passages=top_passages,
            total_found=len(scored_passages),
            is_sufficient=is_sufficient,
            context_token_estimate=token_estimate,
        )

    def _compute_relevance(self, full_query: str, tokens: List[str], heading: str, content: str) -> float:
        """Heuristic relevance scorer combining exact phrase match and token hits."""
        score = 0.0
        combined_text = f"{heading} {content}".lower()

        # Exact query match boost
        if full_query.lower() in combined_text:
            score += 0.6

        # Heading keyword match
        heading_lower = heading.lower()
        for token in tokens:
            if token in heading_lower:
                score += 0.35
            if token in combined_text:
                score += 0.15

        return round(min(1.0, score), 3)
