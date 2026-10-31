"""
Question blueprints: a blueprint says *what* one question must be (concept, level,
Bloom level, type, difficulty) before anything is retrieved or generated.

Pure Python (no DB, no LLM) so it is trivial to test.
"""

from dataclasses import dataclass
from typing import List, Optional

LEVEL_TO_BLOOM = {1: "remember", 2: "understand", 3: "apply", 4: "analyze", 5: "evaluate"}
LEVEL_TO_DIFFICULTY = {1: "easy", 2: "easy", 3: "medium", 4: "hard", 5: "hard"}

# Question types allowed per level, in preference order.
LEVEL_TYPES = {
    1: ("mcq", "true_false", "fill_blank"),
    2: ("mcq", "true_false", "numerical"),
    3: ("numerical", "mcq", "fill_blank"),
    4: ("mcq", "multi_select", "step_by_step"),
    5: ("mcq", "assertion_reasoning", "logical_reasoning"),
}

# What the question should ask the student to do at each level (used in the prompt and
# in the retrieval query).
LEVEL_FOCUS = {
    1: "recall a definition, term or basic fact",
    2: "explain or recognise why a rule works",
    3: "apply the rule to a short worked problem or real-life situation",
    4: "analyse a multi-step situation, find an error or compare cases",
    5: "evaluate a claim, a method or a student's reasoning and justify the judgement",
}


@dataclass(frozen=True)
class Blueprint:
    concept_id: int
    concept_name: str
    class_num: int
    subject: str
    board: str
    chapter: Optional[str]
    concept_description: Optional[str]
    level: int
    bloom_level: str
    question_type: str
    difficulty: str
    purpose: str = "practice"

    @property
    def focus(self) -> str:
        return LEVEL_FOCUS[self.level]

    @property
    def retrieval_query(self) -> str:
        return f"{self.concept_name} {self.focus}"


def blueprint_for(concept, level: int, question_type: Optional[str] = None, purpose: str = "practice") -> Blueprint:
    """Build one blueprint from a ``Concept`` row (or any object with the same attributes)."""
    if level not in LEVEL_TYPES:
        raise ValueError(f"level must be 1..5, got {level}")
    qtype = question_type or LEVEL_TYPES[level][0]
    if qtype not in LEVEL_TYPES[level]:
        raise ValueError(f"question type '{qtype}' is not allowed at level {level}: {LEVEL_TYPES[level]}")
    return Blueprint(
        concept_id=concept.id,
        concept_name=concept.name,
        class_num=concept.class_num,
        subject=concept.subject,
        board=getattr(concept, "board", None) or "TS",
        chapter=getattr(concept, "chapter", None),
        concept_description=getattr(concept, "description", None),
        level=level,
        bloom_level=LEVEL_TO_BLOOM[level],
        question_type=qtype,
        difficulty=LEVEL_TO_DIFFICULTY[level],
        purpose=purpose,
    )


def build_blueprints(concept, level: int, count: int = 1, purpose: str = "practice", start: int = 0) -> List[Blueprint]:
    """
    ``count`` blueprints for one concept/level, cycling through the allowed question types so
    a batch is varied. ``start`` rotates the cycle (e.g. pass the number of questions already
    stored so the next batch does not begin with the same type).
    """
    types = LEVEL_TYPES[level]
    return [blueprint_for(concept, level, types[(start + i) % len(types)], purpose) for i in range(count)]
