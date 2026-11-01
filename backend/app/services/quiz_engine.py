"""
Step 3 - quiz engine.

Pipeline for one question:

    Blueprint (concept, level, Bloom, type)
      -> retrieval for THIS blueprint (Chroma, board/class/subject/chapter filtered)
      -> ONE Gemini call for ONE question
      -> structural + sympy validation (quiz_validation)
      -> duplicate rejection (template hash, optional embedding similarity)
      -> stored as source="ai"
      -> on repeated failure / provider unavailable: curated fallback

``select_question`` is what the Step 4 endpoints call: it applies the "do not repeat
recent questions unless mode == 'revision'" rule, then generates, then falls back.
Answer keys never leave the server: use ``public_question`` for anything sent to a browser.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.quiz import Concept, Question, QuestionAttempt
from app.seed.curated_bank import _AR_OPTIONS
from app.seed.quiz_seed import build_question_payload
from app.services.gemini_service import GeminiAuthError, GeminiError, GeminiQuotaError
from app.services.quiz_blueprints import Blueprint, blueprint_for
from app.services.quiz_llm import GeminiQuizLLM, QuizLLM
from app.services.quiz_validation import validate_item

logger = logging.getLogger(__name__)

MAX_ATTEMPTS_PER_BLUEPRINT = 3
RECENT_QUESTION_WINDOW = 30  # a student's last N question attempts (per concept) count as "recent"
EMBEDDING_DUPLICATE_THRESHOLD = 0.92
PASSAGES_PER_BLUEPRINT = 4

ORIGIN_AI = "ai_generated"            # generated and stored just now
ORIGIN_BANK = "bank"                  # an already stored question (ai or curated) served normally
ORIGIN_CURATED_FALLBACK = "curated_fallback"  # generation failed; label this in the UI


# --------------------------------------------------------------------------- retrieval
class Retriever(Protocol):
    def retrieve(self, bp: Blueprint) -> List[Dict[str, Any]]: ...


class ChromaRetriever:
    """Per-blueprint retrieval. Any failure (Chroma down, empty index) yields no passages:
    the model then works from the concept description alone."""

    def __init__(self, store=None, n_results: int = PASSAGES_PER_BLUEPRINT):
        self._store = store
        self.n_results = n_results

    def _get_store(self):
        if self._store is None:
            from app.services.vector_store import ChromaVectorStore
            self._store = ChromaVectorStore.get_instance()
        return self._store

    def retrieve(self, bp: Blueprint) -> List[Dict[str, Any]]:
        try:
            return self._get_store().query_curriculum(
                query=bp.retrieval_query,
                board=bp.board,
                class_num=bp.class_num,
                subject=bp.subject,
                chapter=bp.chapter,
                n_results=self.n_results,
            )
        except Exception as e:  # pragma: no cover - depends on local chroma state
            logger.warning("Retrieval failed for %s: %s", bp.concept_name, e)
            return []


# --------------------------------------------------------------------------- results
@dataclass
class GenerationOutcome:
    question: Optional[Question]
    origin: str
    rejections: List[str] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    llm_calls: int = 0


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def public_question(q: Question) -> Dict[str, Any]:
    """Browser-safe view: no answer key, no distractor misconception tags, no embedding."""
    return {
        "id": q.id,
        "concept_id": q.concept_id,
        "level": q.level,
        "bloom_level": q.bloom_level,
        "question_type": q.question_type,
        "difficulty": q.difficulty,
        "stem": q.stem,
        "options": q.options,  # step_by_step options hold prompts/hints only; answers live in correct_answer
        "has_hint": bool(q.hint),
        "source": q.source,
    }


def _item_for_payload(item: Dict[str, Any], bp: Optional[Blueprint] = None) -> Dict[str, Any]:
    """Convert a validated LLM item into the authored-bank shape ``build_question_payload`` reads."""
    out = dict(item)
    if "level" not in out and bp is not None:
        out["level"] = bp.level
    if "distractors" in out:
        out["distractors"] = [(d["text"].strip(), d["misconception"].strip()) for d in out["distractors"]]
    if out["type"] == "assertion_reasoning":
        out["fixed_options"] = _AR_OPTIONS
    if out["type"] == "multi_select":
        out["correct_set"] = [c.strip() for c in out["correct_set"]]
    if out["type"] in ("mcq", "logical_reasoning"):
        out["correct"] = out["correct"].strip()
    return out


# --------------------------------------------------------------------------- engine
class QuizEngine:
    def __init__(
        self,
        db: Session,
        llm: Optional[QuizLLM] = None,
        retriever: Optional[Retriever] = None,
        embedder: Optional[Callable[[str], Sequence[float]]] = None,
        max_attempts: int = MAX_ATTEMPTS_PER_BLUEPRINT,
    ):
        self.db = db
        self._llm = llm
        self.retriever = retriever or ChromaRetriever()
        self.embedder = embedder  # optional; e.g. a sentence-transformers encode function
        self.max_attempts = max_attempts

    @property
    def llm(self) -> QuizLLM:
        if self._llm is None:
            self._llm = GeminiQuizLLM()
        return self._llm

    # ---- generation ---------------------------------------------------------------
    def generate_for_blueprint(self, bp: Blueprint, exclude_ids: Sequence[int] = ()) -> GenerationOutcome:
        """Generate and store one question for ``bp``; fall back to a curated question on failure."""
        outcome = GenerationOutcome(question=None, origin=ORIGIN_AI)
        passages = self.retriever.retrieve(bp)  # once per blueprint, reused across retries
        avoid = self._recent_stems(bp)
        feedback: List[str] = []

        for attempt in range(1, self.max_attempts + 1):
            try:
                outcome.llm_calls += 1
                item = self.llm.generate_item(bp, passages, avoid, feedback or None)
            except (GeminiAuthError, GeminiQuotaError) as e:
                # Retrying cannot help (bad key / exhausted quota): go straight to the fallback.
                outcome.fallback_reason = f"{e.error_type}: {e.message}"
                break
            except GeminiError as e:
                outcome.rejections.append(f"attempt {attempt}: provider error: {e.message}")
                feedback = ["Return exactly one valid JSON object."]
                outcome.fallback_reason = f"provider_error: {e.message}"
                continue

            reasons = validate_item(item, bp)
            payload = None
            if not reasons:
                try:
                    payload = build_question_payload(_item_for_payload(item, bp=bp))
                except (KeyError, ValueError, TypeError) as e:
                    reasons = [f"malformed item: {type(e).__name__}: {e}"]
            if not reasons:
                reasons = self._duplicate_reasons(bp, payload)
            if reasons:
                outcome.rejections.append(f"attempt {attempt}: " + "; ".join(reasons))
                feedback = reasons
                outcome.fallback_reason = "validation_failed"
                continue

            question = self._store(bp, payload)
            if question is None:  # lost a race on the unique (concept, template hash) constraint
                outcome.rejections.append(f"attempt {attempt}: duplicate template rejected by the database")
                feedback = ["This question template already exists; change the structure and context."]
                outcome.fallback_reason = "duplicate"
                continue
            outcome.question = question
            outcome.fallback_reason = None
            return outcome

        return self._curated_fallback(bp, exclude_ids, outcome)

    def _recent_stems(self, bp: Blueprint) -> List[str]:
        rows = (
            self.db.query(Question.stem)
            .filter(Question.concept_id == bp.concept_id, Question.level == bp.level)
            .order_by(Question.id.desc())
            .limit(8)
            .all()
        )
        return [r[0] for r in rows]

    def _duplicate_reasons(self, bp: Blueprint, payload: Dict[str, Any]) -> List[str]:
        exists = (
            self.db.query(Question.id)
            .filter_by(concept_id=bp.concept_id, content_hash=payload["content_hash"])
            .first()
        )
        if exists:
            return ["same question template (numbers masked) already exists for this concept"]
        if self.embedder is not None:
            vec = list(self.embedder(payload["stem"]))
            payload["embedding"] = vec
            rows = (
                self.db.query(Question.id, Question.embedding)
                .filter(Question.concept_id == bp.concept_id, Question.embedding.isnot(None))
                .all()
            )
            for qid, emb in rows:
                if emb and cosine(vec, emb) >= EMBEDDING_DUPLICATE_THRESHOLD:
                    return [f"stem is too similar to existing question {qid}"]
        return []

    def _store(self, bp: Blueprint, payload: Dict[str, Any]) -> Optional[Question]:
        payload = dict(payload)
        payload["source"] = "ai"
        payload["assessment_purpose"] = "practice" if bp.purpose not in ("diagnostic", "revision") else bp.purpose
        q = Question(concept_id=bp.concept_id, **payload)
        try:
            with self.db.begin_nested():
                self.db.add(q)
                self.db.flush()
        except IntegrityError:
            return None
        self.db.commit()
        return q

    # ---- curated fallback ---------------------------------------------------------
    def _curated_fallback(self, bp: Blueprint, exclude_ids: Sequence[int], outcome: GenerationOutcome) -> GenerationOutcome:
        q = self._pick_stored(bp.concept_id, bp.level, exclude_ids, source="curated", question_type=bp.question_type) \
            or self._pick_stored(bp.concept_id, bp.level, exclude_ids, source="curated")
        outcome.question = q
        outcome.origin = ORIGIN_CURATED_FALLBACK
        if q is None:
            outcome.fallback_reason = (outcome.fallback_reason or "unknown") + "; no unused curated question left"
        return outcome

    def _pick_stored(self, concept_id: int, level: int, exclude_ids: Sequence[int],
                     source: Optional[str] = None, question_type: Optional[str] = None) -> Optional[Question]:
        query = self.db.query(Question).filter(Question.concept_id == concept_id, Question.level == level)
        if source:
            query = query.filter(Question.source == source)
        if question_type:
            query = query.filter(Question.question_type == question_type)
        if exclude_ids:
            query = query.filter(~Question.id.in_(list(exclude_ids)))
        return query.order_by(Question.id).first()

    # ---- selection (what Step 4 calls) --------------------------------------------
    def recent_question_ids(self, student_id: str, concept_id: int) -> List[int]:
        rows = (
            self.db.query(QuestionAttempt.question_id)
            .join(Question, Question.id == QuestionAttempt.question_id)
            .filter(QuestionAttempt.student_id == student_id, Question.concept_id == concept_id)
            .order_by(QuestionAttempt.id.desc())
            .limit(RECENT_QUESTION_WINDOW)
            .all()
        )
        seen: List[int] = []
        for (qid,) in rows:
            if qid not in seen:
                seen.append(qid)
        return seen

    def select_question(
        self,
        student_id: str,
        concept_id: int,
        level: int,
        mode: str = "practice",
        extra_exclude_ids: Sequence[int] = (),
    ) -> GenerationOutcome:
        """
        Pick the next question for a student.

        1. Rule 7: skip the student's recent questions, unless ``mode == "revision"``
           (revision is allowed to repeat). ``extra_exclude_ids`` are questions already served
           in the current quiz attempt, which are excluded in every mode.
        2. An unseen stored question is served as-is (origin "bank").
        3. Otherwise generate a new one with Gemini (origin "ai_generated").
        4. If generation fails, use an unseen curated question (origin "curated_fallback").
        5. If everything unseen is used up, repeat the least recently seen question
           rather than leave the student with nothing (origin "bank", fallback_reason set).
        """
        concept = self.db.get(Concept, concept_id)
        if concept is None:
            raise ValueError(f"unknown concept {concept_id}")

        recent = [] if mode == "revision" else self.recent_question_ids(student_id, concept_id)
        exclude = list(dict.fromkeys([*recent, *extra_exclude_ids]))

        stored = self._pick_stored(concept_id, level, exclude)
        if stored is not None:
            return GenerationOutcome(question=stored, origin=ORIGIN_BANK)

        bp = blueprint_for(concept, level, purpose=mode)
        bp = self._rotate_type(bp, concept, level)
        outcome = self.generate_for_blueprint(bp, exclude)
        if outcome.question is not None:
            return outcome

        # Everything unseen is gone: repeat the least recently seen, but never one from this attempt.
        hard_exclude = list(extra_exclude_ids)
        oldest_first = list(reversed(recent))
        for qid in oldest_first:
            if qid in hard_exclude:
                continue
            q = self.db.get(Question, qid)
            if q is not None and q.level == level:
                outcome.question = q
                outcome.origin = ORIGIN_BANK
                outcome.fallback_reason = (outcome.fallback_reason or "") + "; repeated an earlier question"
                return outcome
        outcome.question = self._pick_stored(concept_id, level, hard_exclude)
        outcome.origin = ORIGIN_BANK
        return outcome

    def _rotate_type(self, bp: Blueprint, concept, level: int) -> Blueprint:
        """Vary the question type with the number of questions already stored at this level."""
        from app.services.quiz_blueprints import LEVEL_TYPES
        stored = (
            self.db.query(func.count(Question.id))
            .filter(Question.concept_id == concept.id, Question.level == level)
            .scalar()
        ) or 0
        types = LEVEL_TYPES[level]
        return blueprint_for(concept, level, types[stored % len(types)], bp.purpose)
