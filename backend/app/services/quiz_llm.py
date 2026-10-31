"""
The one LLM provider for quiz generation: Gemini (model from ``settings.GEMINI_MODEL``,
default ``gemini-3.5-flash``), reached through the existing ``GeminiService`` so API-key
handling, error classification and the 503 pause are shared with the tutor.

One call = one question. The model never sees the answer key of other questions and is asked
for a single JSON object in the authored-bank shape (see ``app/seed/curated_bank.py``).
"""

import json
import re
from typing import Any, Dict, List, Optional, Protocol

from app.services.gemini_service import GeminiError, GeminiService
from app.services.quiz_blueprints import Blueprint


class QuizLLMOutputError(GeminiError):
    """The model answered, but not with one usable JSON object."""

    def __init__(self, message: str = "Model did not return a usable JSON question."):
        super().__init__(message, status_code=502, error_type="quiz_output_error")


class QuizLLM(Protocol):
    def generate_item(self, bp: Blueprint, passages: List[Dict[str, Any]], avoid_stems: List[str],
                      feedback: Optional[List[str]] = None) -> Dict[str, Any]: ...


SHAPES = {
    "mcq": '{"type":"mcq","objective":"...","stem":"...","correct":"right option text",'
           '"distractors":[{"text":"wrong 1","misconception":"the specific mistake that leads here"},'
           '{"text":"wrong 2","misconception":"..."},{"text":"wrong 3","misconception":"..."}],'
           '"hint":"nudge without giving the answer","explanation":"why the answer is right",'
           '"verify":[["eval","(-5)+(-3)","-8"]]}',
    "logical_reasoning": "same JSON shape as mcq, with \"type\":\"logical_reasoning\"",
    "multi_select": '{"type":"multi_select","objective":"...","stem":"Select ALL ...",'
                    '"correct_set":["right 1","right 2"],"distractors":[{"text":"wrong 1","misconception":"..."},'
                    '{"text":"wrong 2","misconception":"..."}],"hint":"...","explanation":"...","verify":[...]}'
                    " (4 options in total: correct_set + distractors)",
    "true_false": '{"type":"true_false","objective":"...","stem":"True or false: ...","answer":true,'
                  '"hint":"...","explanation":"...","verify":[...]}',
    "fill_blank": '{"type":"fill_blank","objective":"...","stem":"... ____ ...","accepted":["answer","alt form"],'
                  '"hint":"...","explanation":"...","verify":[...]}',
    "numerical": '{"type":"numerical","objective":"...","stem":"...","answer":"7","tolerance":0,'
                 '"hint":"...","explanation":"...","verify":[["eval","-4+11","7"]]}',
    "step_by_step": '{"type":"step_by_step","objective":"...","stem":"... one step at a time.","steps":['
                    '{"prompt":"step 1 question","answer":"3","hint":"..."},{"prompt":"...","answer":"...","hint":"..."},'
                    '{"prompt":"...","answer":"...","hint":"..."}],"hint":"...","explanation":"...","verify":[...]}',
    "assertion_reasoning": '{"type":"assertion_reasoning","objective":"...","stem":"Assertion (A): ...\\nReason (R): ...'
                           '\\nWhich option is correct?","correct_index":0,"hint":"...","explanation":"...","verify":[...]}'
                           " (options are fixed by the app: 0 = both true and R explains A, 1 = both true but R does not "
                           "explain A, 2 = A true R false, 3 = A false R true)",
}

VERIFY_RULES = """verify rules (these are re-computed by a maths engine; wrong entries reject the question):
- ["eval", "expression", "expected value"]            e.g. ["eval","(-8)*(-3)+(-10)","14"]
- ["solve", "lhs = rhs", "x", "expected"]              e.g. ["solve","3*x + 5 = 20","x","5"]  ("none" if no solution)
- ["equiv", "expr1", "expr2", true_or_false]           whether the two expressions are equal for all values
- Use * for every multiplication, ** or ^ for powers, only single-letter variables, ASCII "-" for minus.
- Every computed answer needs verify entries covering the stored answer. For numerical and step_by_step
  questions the FINAL answer must appear as the expected value of an eval or solve entry.
- If nothing is computed (pure definition / recognition), omit verify and set "conceptual": true.
  Never mark numerical or step_by_step questions conceptual."""


def build_system_instruction(bp: Blueprint) -> str:
    return f"""You write ONE original practice question for a school student.
Board: {bp.board}. Class {bp.class_num} {bp.subject}. Concept: {bp.concept_name}.
Level L{bp.level} (Bloom: {bp.bloom_level}, difficulty: {bp.difficulty}). At this level the student must: {bp.focus}.
Question type: {bp.question_type}.

Rules:
1. Base the question on the concept and the textbook passages given. Never copy textbook questions verbatim.
2. Exactly one fully correct answer (multi_select: the stated correct set only). No ambiguity, no trick wording.
3. Every wrong option must come from a real, specific student misconception, written in "misconception".
   No "None of the above", no "All of the above", no filler options.
4. The stem must be self-contained and appropriate for Class {bp.class_num}.
5. The hint must help without revealing the answer. The explanation must justify the correct answer.
6. Be different from the questions listed under AVOID in structure and context, not only in numbers.
7. Return exactly one JSON object and nothing else.

JSON shape for type "{bp.question_type}":
{SHAPES[bp.question_type]}

{VERIFY_RULES}"""


def build_prompt(bp: Blueprint, passages: List[Dict[str, Any]], avoid_stems: List[str],
                 feedback: Optional[List[str]] = None) -> str:
    if passages:
        ctx = "\n\n".join(f"[Passage {i}] {p.get('text', '').strip()[:700]}" for i, p in enumerate(passages, 1))
    else:
        ctx = f"(no textbook passage found) Concept description: {bp.concept_description or bp.concept_name}"
    parts = [f"TEXTBOOK CONTEXT:\n{ctx}"]
    if avoid_stems:
        parts.append("AVOID (already asked):\n" + "\n".join(f"- {s[:160]}" for s in avoid_stems[:8]))
    if feedback:
        parts.append("YOUR PREVIOUS ATTEMPT WAS REJECTED FOR THESE REASONS - fix them:\n"
                     + "\n".join(f"- {f}" for f in feedback[:6]))
    parts.append("Write the question now.")
    return "\n\n".join(parts)


def parse_item(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise QuizLLMOutputError(f"Model did not return valid JSON: {e}")
    if isinstance(data, list):
        data = data[0] if data else None
    if isinstance(data, dict) and isinstance(data.get("question"), dict):
        data = data["question"]
    if not isinstance(data, dict):
        raise QuizLLMOutputError("Model JSON was not a single question object.")
    return data


class GeminiQuizLLM:
    def __init__(self, service: Optional[GeminiService] = None, temperature: float = 0.8):
        self.service = service or GeminiService()
        self.temperature = temperature

    def generate_item(self, bp: Blueprint, passages: List[Dict[str, Any]], avoid_stems: List[str],
                      feedback: Optional[List[str]] = None) -> Dict[str, Any]:
        response = self.service._generate_content(
            contents=build_prompt(bp, passages, avoid_stems, feedback),
            config={
                "system_instruction": build_system_instruction(bp),
                "response_mime_type": "application/json",
                "temperature": self.temperature,
            },
        )
        text = getattr(response, "text", None)
        if not text:
            raise QuizLLMOutputError("Model returned an empty response (possibly blocked).")
        return parse_item(text)
