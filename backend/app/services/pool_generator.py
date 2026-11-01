"""
Chapter Question Pool Generator.

Generates and stores questions across Bloom levels L1-L5 for a chapter until the target
counts are reached. Reuses QuizEngine.generate_for_blueprint, enforcing that:
- One question per LLM call
- Blueprint retrieval & sympy validation
- Duplicate rejection (template & embedding)
- Never stores or counts curated fallbacks as AI questions
- Idempotent and resumable
"""

from typing import Any, Callable, Dict, List, Optional
import logging
from sqlalchemy.orm import Session

from app.models.curriculum import Chapter
from app.models.quiz import Concept, Question
from app.services.concept_mapper import ensure_chapter_concepts
from app.services.quiz_blueprints import Blueprint, build_blueprints
from app.services.quiz_engine import (
    ORIGIN_AI,
    ORIGIN_BANK,
    ORIGIN_CURATED_FALLBACK,
    QuizEngine,
)

logger = logging.getLogger(__name__)

# Default distribution roughly summing to 30 questions
# L1: 6, L2: 7, L3: 7, L4: 6, L5: 4
DEFAULT_TARGET_PER_LEVEL = {1: 6, 2: 7, 3: 7, 4: 6, 5: 4}


def get_target_distribution(total_target: int = 30) -> Dict[int, int]:
    """Calculate per-level question targets for a given total target."""
    if total_target == 30:
        return dict(DEFAULT_TARGET_PER_LEVEL)
    # Proportional split: L1 20%, L2 23%, L3 23%, L4 20%, L5 14%
    ratios = {1: 0.20, 2: 0.233, 3: 0.233, 4: 0.20, 5: 0.134}
    dist = {}
    allocated = 0
    for lvl in (1, 2, 3, 4):
        c = max(1, round(total_target * ratios[lvl]))
        dist[lvl] = c
        allocated += c
    dist[5] = max(1, total_target - allocated)
    return dist


def generate_chapter_pool(
    db: Session,
    chapter: Chapter,
    target_per_level: Optional[Dict[int, int]] = None,
    engine: Optional[QuizEngine] = None,
    max_llm_calls_remaining: Optional[int] = None,
    on_rejection: Optional[Callable[[Blueprint, List[str]], None]] = None,
) -> Dict[str, Any]:
    """
    Builds blueprints across L1-L5 and generates AI questions for `chapter` until targets are met.
    Never stores curated fallbacks as AI questions.
    Resumable: skips questions/levels already stored in the DB.
    """
    target = target_per_level or DEFAULT_TARGET_PER_LEVEL
    quiz_engine = engine or QuizEngine(db)

    # 1. Ensure chapter has a Concept
    concept = db.query(Concept).filter(Concept.chapter_id == chapter.id).first()
    if not concept:
        ensure_chapter_concepts(db)
        concept = db.query(Concept).filter(Concept.chapter_id == chapter.id).first()

    if not concept:
        raise ValueError(f"Could not map concept for chapter {chapter.id} ({chapter.title})")

    total_llm_calls = 0
    all_rejections: List[Dict[str, Any]] = []
    questions_stored_by_level: Dict[int, int] = {lvl: 0 for lvl in (1, 2, 3, 4, 5)}
    quota_exhausted = False
    quota_error_obj = None

    # 2. Iterate levels L1 -> L5
    for level in (1, 2, 3, 4, 5):
        target_count = target.get(level, 0)
        if target_count <= 0:
            continue

        # Count existing non-rejected questions for this concept at this level
        existing_count = (
            db.query(Question)
            .filter(
                Question.concept_id == concept.id,
                Question.level == level,
                Question.review_status != "rejected",
            )
            .count()
        )
        questions_stored_by_level[level] = existing_count

        needed = max(0, target_count - existing_count)
        if needed == 0:
            continue  # Already meets target, skip!

        # Build varied blueprints cycling through allowed types
        blueprints = build_blueprints(concept, level=level, count=needed, start=existing_count)

        for bp in blueprints:
            # Check hard LLM call cap
            if max_llm_calls_remaining is not None and (total_llm_calls >= max_llm_calls_remaining):
                logger.warning("Reached max_llm_calls cap for chapter %s", chapter.title)
                break

            try:
                outcome = quiz_engine.generate_for_blueprint(bp)
                total_llm_calls += outcome.llm_calls

                # Handle rate limit reported in fallback_reason
                if outcome.fallback_reason and "quota_error" in outcome.fallback_reason:
                    is_daily = any(w in outcome.fallback_reason.lower() for w in ["daily", "per day", "free tier limit"])
                    if is_daily:
                        quota_exhausted = True
                        from app.services.gemini_service import GeminiQuotaError
                        quota_error_obj = GeminiQuotaError(outcome.fallback_reason, is_daily_exhaustion=True)
                        break
                    else:
                        logger.info("Rate limit hit from provider (%s). Sleeping 15s before retry...", outcome.fallback_reason[:60])
                        import time
                        time.sleep(15)
                        # retry this blueprint
                        outcome = quiz_engine.generate_for_blueprint(bp)
                        total_llm_calls += outcome.llm_calls

                # Only count genuine AI generated questions (never curated fallback)
                if outcome.origin == ORIGIN_AI and outcome.question is not None:
                    # Explicitly ensure review_status is 'unreviewed' for AI questions
                    if outcome.question.review_status != "unreviewed":
                        outcome.question.review_status = "unreviewed"
                        db.commit()
                    questions_stored_by_level[level] += 1
                else:
                    # It was a fallback or failed generation
                    reasons = outcome.rejections or [outcome.fallback_reason or "unknown_rejection"]
                    rej_record = {
                        "level": level,
                        "question_type": bp.question_type,
                        "reasons": reasons,
                    }
                    all_rejections.append(rej_record)
                    if on_rejection:
                        on_rejection(bp, reasons)

                # Rate pacing: brief pause between calls to respect 15 RPM Gemini limits
                if outcome.llm_calls > 0:
                    import time
                    time.sleep(3.5)

            except Exception as e:
                from app.services.gemini_service import GeminiQuotaError
                if isinstance(e, GeminiQuotaError):
                    if e.is_daily_exhaustion:
                        quota_exhausted = True
                        quota_error_obj = e
                        break
                    else:
                        sleep_sec = min(60, e.retry_after_seconds or 10)
                        logger.info("Temporary rate limit hit. Sleeping %d seconds before retry...", sleep_sec)
                        import time
                        time.sleep(sleep_sec)
                        # retry once
                        try:
                            outcome = quiz_engine.generate_for_blueprint(bp)
                            total_llm_calls += outcome.llm_calls
                            if outcome.origin == ORIGIN_AI and outcome.question is not None:
                                if outcome.question.review_status != "unreviewed":
                                    outcome.question.review_status = "unreviewed"
                                    db.commit()
                                questions_stored_by_level[level] += 1
                                continue
                        except GeminiQuotaError as retry_quota_e:
                            if retry_quota_e.is_daily_exhaustion:
                                quota_exhausted = True
                                quota_error_obj = retry_quota_e
                                break
                        except Exception:
                            pass
                logger.error("Error generating question for bp %s: %s", bp, e)
                all_rejections.append({"level": level, "question_type": bp.question_type, "reasons": [str(e)]})

        if quota_exhausted:
            break

        if max_llm_calls_remaining is not None and (total_llm_calls >= max_llm_calls_remaining):
            break

    total_pool_now = sum(questions_stored_by_level.values())

    result = {
        "chapter_id": chapter.id,
        "chapter_title": chapter.title,
        "concept_id": concept.id,
        "questions_by_level": questions_stored_by_level,
        "total_questions": total_pool_now,
        "newly_generated_llm_calls": total_llm_calls,
        "rejections": all_rejections,
        "quota_exhausted": quota_exhausted,
        "quota_error": quota_error_obj,
    }
    return result
