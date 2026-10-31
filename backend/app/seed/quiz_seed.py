"""
Idempotent seeding of the 3 starter concepts, their prerequisite edges and the
curated fallback question bank. Safe to call on every start-up.
"""

import hashlib
import random
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.quiz import (
    LEVEL_TO_BLOOM,
    Concept,
    ConceptPrerequisite,
    Question,
)
from app.seed.curated_bank import BANK, CONCEPTS, PREREQUISITES
from app.services.question_hash import content_hash

LEVEL_TO_DIFFICULTY = {1: "easy", 2: "easy", 3: "medium", 4: "hard", 5: "hard"}
KEYS = ["A", "B", "C", "D", "E", "F"]

# Used only when an assertion/reason option that is not the standard "correct"
# option has no distractor tag of its own.
_AR_FALLBACK_MISCONCEPTION = "Misjudged how the assertion and the reason relate"


def _rng_for(stem: str) -> random.Random:
    seed = int(hashlib.sha256(stem.encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(seed)


def build_question_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert one authored bank item into the stored column values."""
    qtype = item["type"]
    options: Any = None
    misconceptions: Any = None

    if qtype in ("mcq", "logical_reasoning"):
        entries: List[Tuple[str, bool, str]] = [(item["correct"], True, "")]
        entries += [(text, False, why) for text, why in item["distractors"]]
        _rng_for(item["stem"]).shuffle(entries)
        options = [{"key": KEYS[i], "text": text} for i, (text, _, _) in enumerate(entries)]
        correct = next(KEYS[i] for i, (_, ok, _) in enumerate(entries) if ok)
        misconceptions = {KEYS[i]: why for i, (_, ok, why) in enumerate(entries) if not ok}

    elif qtype == "multi_select":
        entries = [(t, True, "") for t in item["correct_set"]]
        entries += [(text, False, why) for text, why in item["distractors"]]
        _rng_for(item["stem"]).shuffle(entries)
        options = [{"key": KEYS[i], "text": text} for i, (text, _, _) in enumerate(entries)]
        correct = sorted(KEYS[i] for i, (_, ok, _) in enumerate(entries) if ok)
        misconceptions = {KEYS[i]: why for i, (_, ok, why) in enumerate(entries) if not ok}

    elif qtype == "assertion_reasoning":
        fixed = item["fixed_options"]
        idx = item["correct_index"]
        options = [{"key": KEYS[i], "text": text} for i, (text, _) in enumerate(fixed)]
        correct = KEYS[idx]
        misconceptions = {
            KEYS[i]: (why or _AR_FALLBACK_MISCONCEPTION)
            for i, (_, why) in enumerate(fixed)
            if i != idx
        }

    elif qtype == "true_false":
        correct = bool(item["answer"])

    elif qtype == "fill_blank":
        correct = list(item["accepted"])

    elif qtype == "numerical":
        correct = {"value": str(item["answer"]), "tolerance": item.get("tolerance", 0)}

    elif qtype == "step_by_step":
        options = {"steps": [{"prompt": s["prompt"], "hint": s.get("hint")} for s in item["steps"]]}
        correct = [str(s["answer"]) for s in item["steps"]]

    else:  # pragma: no cover - the authored bank only uses the types above
        raise ValueError(f"Unsupported curated question type: {qtype}")

    level = item["level"]
    return {
        "learning_objective": item.get("objective"),
        "level": level,
        "bloom_level": LEVEL_TO_BLOOM[level],
        "question_type": qtype,
        "difficulty": LEVEL_TO_DIFFICULTY[level],
        "stem": item["stem"],
        "options": options,
        "correct_answer": correct,
        "explanation": item["explanation"],
        "hint": item.get("hint"),
        "assessment_purpose": "practice",
        "distractor_misconceptions": misconceptions,
        "language": "en",
        "source": "curated",
        "content_hash": content_hash(qtype, item["stem"]),
    }


def seed_concepts(db: Session) -> Dict[str, Concept]:
    """Create the starter concepts + prerequisite edges. Returns {key: Concept}."""
    by_key: Dict[str, Concept] = {}
    for spec in CONCEPTS:
        concept = (
            db.query(Concept)
            .filter_by(class_num=spec["class_num"], subject=spec["subject"], name=spec["name"])
            .one_or_none()
        )
        if concept is None:
            concept = Concept(
                class_num=spec["class_num"],
                subject=spec["subject"],
                name=spec["name"],
                description=spec["description"],
                chapter=spec.get("chapter"),
            )
            db.add(concept)
            db.flush()
        by_key[spec["key"]] = concept

    for child_key, prereq_key in PREREQUISITES:
        exists = (
            db.query(ConceptPrerequisite)
            .filter_by(
                concept_id=by_key[child_key].id,
                prerequisite_concept_id=by_key[prereq_key].id,
            )
            .one_or_none()
        )
        if exists is None:
            db.add(
                ConceptPrerequisite(
                    concept_id=by_key[child_key].id,
                    prerequisite_concept_id=by_key[prereq_key].id,
                )
            )
    db.commit()
    return by_key


def seed_curated_bank(db: Session, concepts: Dict[str, Concept] = None) -> int:
    """Insert curated questions that are not stored yet. Returns the number inserted."""
    concepts = concepts or seed_concepts(db)
    inserted = 0
    for item in BANK:
        payload = build_question_payload(item)
        concept = concepts[item["concept"]]
        exists = (
            db.query(Question.id)
            .filter_by(concept_id=concept.id, content_hash=payload["content_hash"])
            .first()
        )
        if exists:
            continue
        db.add(Question(concept_id=concept.id, **payload))
        inserted += 1
    db.commit()
    return inserted


def seed_quiz_content(db: Session) -> Dict[str, int]:
    concepts = seed_concepts(db)
    inserted = seed_curated_bank(db, concepts)
    return {"concepts": len(concepts), "curated_questions_inserted": inserted}
