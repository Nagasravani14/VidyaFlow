"""
Chapter Mind Map Generator.

Generates structured concept mind maps for curriculum chapters using Gemini 3.5 Flash.
Grounded in ingested textbook passages when available; falls back to chapter title and
curriculum description with grounded=False when no passages exist.
Validates against MindMapSchema with up to 3 retries on validation failure.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.curriculum import Chapter
from app.models.quiz import ChapterMindMap
from app.models.textbook import TextbookPassage, TextbookDocument
from app.schemas.mindmap import MindMapSchema
from app.services.gemini_service import GeminiQuotaError, GeminiService

logger = logging.getLogger(__name__)


def retrieve_chapter_passages(
    db: Session,
    chapter: Chapter,
    top_k: int = 10,
    retriever: Optional[Any] = None,
) -> List[str]:
    """
    Retrieve top text chunks for the chapter from the relational DB or vector store.
    Returns a list of passage text strings.
    """
    # 0. Custom retriever if supplied
    if retriever is not None:
        try:
            res = retriever.retrieve_for_chapter(chapter) if hasattr(retriever, "retrieve_for_chapter") else retriever.retrieve(chapter)
            if res:
                return [r.get("text", "") if isinstance(r, dict) else str(r) for r in res]
            return []
        except Exception as e:
            logger.warning("Custom retriever failed: %s", e)
            return []

    # 1. Check relational TextbookPassage directly linked to chapter
    passages = (
        db.query(TextbookPassage.content)
        .filter(TextbookPassage.chapter_id == chapter.id)
        .limit(top_k)
        .all()
    )
    if passages:
        return [p[0].strip() for p in passages if p[0] and p[0].strip()]

    # 2. Check Chroma vector store if available
    try:
        from app.services.vector_store import ChromaVectorStore
        store = ChromaVectorStore.get_instance()
        board_code = chapter.subject.board.code if chapter.subject and chapter.subject.board else "TS"
        class_num = chapter.subject.class_grade.grade_number if chapter.subject and chapter.subject.class_grade else 8
        subject_name = chapter.subject.name if chapter.subject else "General"

        results = store.query_curriculum(
            query=chapter.title,
            board=board_code,
            class_num=class_num,
            subject=subject_name,
            chapter=chapter.title,
            n_results=top_k,
        )
        if results:
            return [r.get("text", "") for r in results if r.get("text", "").strip()]
    except Exception as e:
        logger.debug("Vector store retrieval skipped: %s", e)

    return []


def _build_mindmap_prompt(
    chapter_title: str,
    subject_name: str,
    grade_number: int,
    description: Optional[str],
    passages: List[str],
    previous_errors: Optional[str] = None,
) -> str:
    """Build the prompt for Gemini mind map generation."""
    schema_instructions = """
You are creating a comprehensive, hierarchical Mind Map for a school textbook chapter.

STRICT SCHEMA CONSTRAINTS:
1. Root title: Exactly the chapter title.
2. Branches: Exactly 4 to 8 main theme branches.
3. Children: Each branch must have between 2 and 6 subtopic children.
4. Depth: Exactly 2 levels below root (Root -> Branch -> Child).
5. Labels: Under 60 characters each, non-empty, concise and educational.
6. Note: Optional brief formula, key takeaway, or summary definition for each child (or null).
7. Content Grounding: Every branch and child label MUST be derived from the chapter topic/curriculum, NEVER generic filler like "Topic 1", "Subtopic A", or irrelevant content.

OUTPUT FORMAT:
Return ONLY a valid JSON object matching this schema:
{
  "title": "Exact Chapter Title",
  "branches": [
    {
      "label": "Main Topic / Section (<= 60 chars)",
      "children": [
        {
          "label": "Subtopic / Concept (<= 60 chars)",
          "note": "Optional brief note, formula or definition, or null"
        }
      ]
    }
  ]
}
"""
    context_parts = [
        f"CHAPTER: {chapter_title}",
        f"SUBJECT: {subject_name}",
        f"CLASS / GRADE: Class {grade_number}",
    ]
    if description:
        context_parts.append(f"CURRICULUM OVERVIEW: {description.strip()}")

    if passages:
        passages_text = "\n---\n".join(passages[:10])
        context_parts.append(f"TEXTBOOK EXCERPTS:\n{passages_text}")
    else:
        context_parts.append(
            "NOTE: No textbook passages are available in the database. "
            "Generate the mind map strictly based on standard curriculum requirements for this chapter and class level."
        )

    prompt = schema_instructions + "\n\n" + "\n\n".join(context_parts)

    if previous_errors:
        prompt += f"\n\nCRITICAL FIX REQUIRED:\nYour previous attempt failed validation with:\n{previous_errors}\nEnsure all constraints (4-8 branches, 2-6 children per branch, label <= 60 chars, valid JSON) are strictly satisfied."

    return prompt


def generate_chapter_mindmap(
    db: Session,
    chapter: Chapter,
    gemini_service: Optional[GeminiService] = None,
    max_retries: int = 3,
    retriever: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Generates a structured MindMap for `chapter`, validates it against MindMapSchema,
    and stores/updates it in chapter_mindmaps.

    Returns dict:
    {
        "chapter_id": int,
        "chapter_title": str,
        "mindmap": Optional[ChapterMindMap],
        "grounded": bool,
        "llm_calls": int,
        "error": Optional[str],
        "validation_errors": List[str],
    }
    """
    gemini = gemini_service or GeminiService()
    subject_name = chapter.subject.name if chapter.subject else "General"
    grade_number = chapter.subject.class_grade.grade_number if (chapter.subject and chapter.subject.class_grade) else 8

    # 1. Retrieve passages
    passages = retrieve_chapter_passages(db, chapter, top_k=10, retriever=retriever)
    is_grounded = len(passages) > 0

    llm_calls = 0
    validation_errors: List[str] = []
    previous_errors: Optional[str] = None
    validated_schema: Optional[MindMapSchema] = None

    # 2. Generation attempt loop with retries
    for attempt in range(1 + max_retries):
        prompt = _build_mindmap_prompt(
            chapter_title=chapter.title,
            subject_name=subject_name,
            grade_number=grade_number,
            description=chapter.description,
            passages=passages,
            previous_errors=previous_errors,
        )

        llm_calls += 1
        try:
            response = gemini._generate_content(
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            raw_text = getattr(response, "text", "") or str(response)

            # Strip markdown formatting if any
            clean_text = raw_text.strip()
            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                clean_text = re.sub(r"\s*```$", "", clean_text)

            parsed_data = json.loads(clean_text)

            # Enforce chapter title if model slightly altered it
            if isinstance(parsed_data, dict) and not parsed_data.get("title"):
                parsed_data["title"] = chapter.title

            validated = MindMapSchema(**parsed_data)
            validated_schema = validated
            break  # Success!

        except GeminiQuotaError as e:
            if not getattr(e, "is_daily_exhaustion", False):
                import time
                sleep_sec = min(60, getattr(e, "retry_after_seconds", None) or 15)
                logger.info("Rate limit in mindmap. Sleeping %ds before retry...", sleep_sec)
                time.sleep(sleep_sec)
                continue
            raise  # Let caller catch quota errors for clean shutdown
        except (json.JSONDecodeError, ValidationError, Exception) as e:
            err_msg = f"Attempt {attempt + 1} failed: {type(e).__name__} - {str(e)}"
            logger.warning("Mind map validation error for '%s': %s", chapter.title, err_msg)
            validation_errors.append(err_msg)
            previous_errors = str(e)

    if validated_schema is None:
        logger.error(
            "Failed to generate valid mind map for chapter %d (%s) after %d calls",
            chapter.id,
            chapter.title,
            llm_calls,
        )
        return {
            "chapter_id": chapter.id,
            "chapter_title": chapter.title,
            "mindmap": None,
            "grounded": is_grounded,
            "llm_calls": llm_calls,
            "error": f"Failed validation after {llm_calls} attempts",
            "validation_errors": validation_errors,
        }

    # 3. Store / update in DB
    existing = db.query(ChapterMindMap).filter(ChapterMindMap.chapter_id == chapter.id).first()
    model_name = getattr(gemini, "model", settings.GEMINI_MODEL)

    if existing:
        existing.mindmap_json = validated_schema.model_dump()
        existing.version = (existing.version or 1) + 1
        existing.source = "ai"
        existing.review_status = "unreviewed"
        existing.grounded = is_grounded
        existing.model_name = model_name
        mindmap_record = existing
    else:
        mindmap_record = ChapterMindMap(
            chapter_id=chapter.id,
            version=1,
            mindmap_json=validated_schema.model_dump(),
            source="ai",
            review_status="unreviewed",
            grounded=is_grounded,
            model_name=model_name,
        )
        db.add(mindmap_record)

    db.commit()
    db.refresh(mindmap_record)

    return {
        "chapter_id": chapter.id,
        "chapter_title": chapter.title,
        "mindmap": mindmap_record,
        "grounded": is_grounded,
        "llm_calls": llm_calls,
        "error": None,
        "validation_errors": validation_errors,
    }
