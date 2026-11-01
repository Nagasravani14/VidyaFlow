"""
Validation of one LLM-authored question item *before* it is stored.

An item uses the same authored shape as ``app/seed/curated_bank.py`` (so the same
``build_question_payload`` turns it into a row). ``validate_item`` returns a list of
human-readable problems; an empty list means the item is acceptable.

Maths is checked with sympy, independently of the answer key the model typed:

    verify = [["eval",  "(-5)+(-3)", "-8"],
              ["solve", "3*x + 5 = 20", "x", "5"],      # "none" = no solution
              ["equiv", "2*x+3*x", "5*x", true]]        # true/false = should be equal

Model-supplied strings are never passed to ``eval`` unchecked: they must match a strict
character whitelist, single-letter variables only, and bounded exponents.

Known limit: sympy proves the *verify entries* are true and that the stored answer matches
them. It cannot prove a model-written verify entry is the *right* thing to check for a
conceptual question, so conceptual items (no computation) are only structure-checked.
"""

import re
from typing import Any, Dict, List

from app.services.quiz_blueprints import Blueprint

FORBIDDEN_FILLER = ("option a", "option b", "option c", "option d", "alternative c", "lorem",
                    "comprehensive exam question", "as an ai", "[insert", "todo")
NEVER_CONCEPTUAL = ("numerical", "step_by_step")
_SAFE_CHARS = re.compile(r"^[0-9a-z+\-*/^().=\s,]*$")
_LONG_WORD = re.compile(r"[a-z]{2,}")
_EXPONENT = re.compile(r"\*\*\s*\(?\s*-?(\d+)")
MAX_EXPR_LEN = 120
MAX_EXPONENT = 12


class _Unsafe(ValueError):
    pass


def _sympy():
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application, parse_expr, standard_transformations,
    )
    return sp, parse_expr, standard_transformations + (implicit_multiplication_application,)


def _clean(text: str) -> str:
    t = str(text).replace("−", "-").replace("–", "-").replace("^", "**").strip()
    return t


def _parse(text: str):
    sp, parse_expr, transforms = _sympy()
    t = _clean(text)
    if not t or len(t) > MAX_EXPR_LEN:
        raise _Unsafe(f"empty or too long expression: {text!r}")
    if not _SAFE_CHARS.match(t.replace("**", "^").lower()):
        raise _Unsafe(f"disallowed characters in {text!r}")
    if _LONG_WORD.search(t.lower()):
        raise _Unsafe(f"only single-letter variables are allowed in {text!r} (write * between letters)")
    if any(int(m) > MAX_EXPONENT for m in _EXPONENT.findall(t)) or t.count("**") > 3 or re.search(r"\*\*[^*]+\*\*", t):
        raise _Unsafe(f"exponent too large or too many powers in {text!r}")
    x = sp.Symbol("x")
    names = {c: sp.Symbol(c) for c in set(re.findall(r"[a-z]", t.lower()))}
    names["x"] = x
    return parse_expr(t, transformations=transforms, local_dict=names)


def _same_value(a: Any, b: Any) -> bool:
    sp = _sympy()[0]
    try:
        return sp.simplify(_parse(str(a)) - _parse(str(b))) == 0
    except Exception:
        return str(a).replace(" ", "") == str(b).replace(" ", "")


def _check_verify_entry(entry: Any) -> List[str]:
    sp = _sympy()[0]
    if not isinstance(entry, (list, tuple)) or not entry:
        return [f"verify entry is not a list: {entry!r}"]
    kind = entry[0]
    try:
        if kind == "eval" and len(entry) == 3:
            _, expr, expected = entry
            if sp.simplify(_parse(expr) - _parse(expected)) != 0:
                return [f"verify failed: {expr} is not {expected}"]
        elif kind == "solve" and len(entry) == 4:
            _, equation, var, expected = entry
            if str(equation).count("=") != 1:
                return [f"equation must contain exactly one '=': {equation!r}"]
            lhs, rhs = str(equation).split("=")
            diff = sp.simplify(_parse(lhs) - _parse(rhs))
            x = sp.Symbol("x")
            if diff == 0:
                solutions = "all"
            elif diff.free_symbols == set():
                solutions = []
            else:
                solutions = sp.solve(sp.Eq(_parse(lhs), _parse(rhs)), x)
            if expected == "none":
                if solutions != []:
                    return [f"{equation} should have no solution but has {solutions}"]
            elif solutions == "all" or len(solutions) != 1 or sp.simplify(solutions[0] - _parse(expected)) != 0:
                return [f"{equation}: solution is {solutions}, not {expected}"]
        elif kind == "equiv" and len(entry) == 4:
            _, e1, e2, should_equal = entry
            equal = sp.simplify(_parse(e1) - _parse(e2)) == 0
            if equal != bool(should_equal):
                return [f"equiv({e1}, {e2}) is {equal}, claimed {bool(should_equal)}"]
        else:
            return [f"unknown or malformed verify entry: {entry!r}"]
    except _Unsafe as e:
        return [f"unsafe verify expression: {e}"]
    except Exception as e:  # sympy parse errors etc.
        return [f"could not evaluate verify entry {entry!r}: {type(e).__name__}"]
    return []


def _expected_values(item: Dict[str, Any]) -> List[str]:
    out = []
    for e in item.get("verify") or []:
        if isinstance(e, (list, tuple)) and e:
            if e[0] == "eval" and len(e) == 3:
                out.append(str(e[2]))
            elif e[0] == "solve" and len(e) == 4 and e[3] != "none":
                out.append(str(e[3]))
    return out


_NUMERIC_OPTION = re.compile(r"^(x\s*=\s*)?-?\d+(\.\d+)?(\s*m)?$")


def _check_answer_consistency(item: Dict[str, Any]) -> List[str]:
    expected = _expected_values(item)
    qtype = item["type"]
    if qtype == "numerical":
        if not expected:
            return ["numerical answer has no eval/solve verify entry to check it against"]
        if not any(_same_value(item["answer"], v) for v in expected):
            return [f"numerical answer {item['answer']!r} does not match any verified value {expected}"]
    elif qtype == "fill_blank" and expected:
        if not any(_same_value(a, v) for a in item["accepted"] for v in expected):
            return [f"no accepted fill-blank answer matches a verified value {expected}"]
    elif qtype == "step_by_step":
        if not expected:
            return ["step_by_step has no eval/solve verify entry for the final answer"]
        if not any(_same_value(item["steps"][-1]["answer"], v) for v in expected):
            return [f"final step answer {item['steps'][-1]['answer']!r} does not match verified {expected}"]
    elif qtype in ("mcq", "logical_reasoning") and expected and _NUMERIC_OPTION.match(item["correct"].strip()):
        value = re.sub(r"^x\s*=\s*|\s*m$", "", item["correct"].strip())
        if not any(_same_value(value, v) for v in expected):
            return [f"correct option {item['correct']!r} does not match verified {expected}"]
    return []


def _text(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _check_structure(item: Dict[str, Any], bp: Blueprint) -> List[str]:
    errs: List[str] = []
    qtype = item.get("type")
    if qtype != bp.question_type:
        return [f"type {qtype!r} does not match blueprint type {bp.question_type!r}"]

    stem = _text(item.get("stem")).strip()
    if not 12 <= len(stem) <= 900:
        errs.append("stem must be 12-900 characters")
    for field in ("explanation", "hint"):
        if len(_text(item.get(field)).strip()) < 8:
            errs.append(f"{field} is missing or too short")
    blob = " ".join(_text(item.get(k)) for k in ("stem", "explanation", "hint")).lower()
    for bad in FORBIDDEN_FILLER:
        if bad in blob:
            errs.append(f"filler text '{bad}'")

    if item.get("conceptual") and qtype in NEVER_CONCEPTUAL:
        errs.append(f"{qtype} questions must be computed and verified, not marked conceptual")

    def check_distractors(expected_count=None, min_count=1):
        ds = item.get("distractors")
        if not isinstance(ds, list) or not all(isinstance(d, dict) for d in ds):
            errs.append("distractors must be a list of {text, misconception}")
            return []
        if expected_count is not None and len(ds) != expected_count:
            errs.append(f"expected exactly {expected_count} distractors, got {len(ds)}")
        if len(ds) < min_count:
            errs.append("not enough distractors")
        for d in ds:
            if not _text(d.get("text")).strip():
                errs.append("empty distractor text")
            if len(_text(d.get("misconception")).strip()) < 6:
                errs.append(f"distractor {d.get('text')!r} has no misconception tag")
        return ds

    if qtype in ("mcq", "logical_reasoning"):
        correct = _text(item.get("correct")).strip()
        ds = check_distractors(expected_count=3)
        texts = [correct] + [_text(d.get("text")).strip() for d in ds]
        if not correct:
            errs.append("missing correct option")
        if len({t.lower() for t in texts}) != len(texts):
            errs.append("option texts are not all distinct")
    elif qtype == "multi_select":
        cs = item.get("correct_set")
        if not isinstance(cs, list) or len(cs) < 2 or not all(_text(c).strip() for c in cs):
            errs.append("multi_select needs a correct_set of at least 2 non-empty options")
            cs = []
        ds = check_distractors(min_count=1)
        texts = [_text(c).strip() for c in cs] + [_text(d.get("text")).strip() for d in ds]
        if len(texts) != 4:
            errs.append("multi_select must have exactly 4 options in total")
        if len({t.lower() for t in texts}) != len(texts):
            errs.append("option texts are not all distinct")
    elif qtype == "assertion_reasoning":
        if "assertion" not in stem.lower() or "reason" not in stem.lower():
            errs.append("assertion_reasoning stem must contain both an Assertion (A) and a Reason (R)")
        if item.get("correct_index") not in (0, 1, 2, 3):
            errs.append("correct_index must be 0, 1, 2 or 3")
    elif qtype == "true_false":
        if not isinstance(item.get("answer"), bool):
            errs.append("true_false answer must be true or false")
    elif qtype == "fill_blank":
        acc = item.get("accepted")
        if not isinstance(acc, list) or not acc or not all(_text(a).strip() for a in acc):
            errs.append("fill_blank needs a non-empty accepted list of strings")
        if "____" not in stem and "_" not in stem:
            errs.append("fill_blank stem needs a blank (____)")
    elif qtype == "numerical":
        if not _text(str(item.get("answer", ""))).strip():
            errs.append("numerical needs an answer")
        tol = item.get("tolerance", 0)
        if not isinstance(tol, (int, float)) or isinstance(tol, bool) or tol < 0:
            errs.append("tolerance must be a number >= 0")
    elif qtype == "step_by_step":
        steps = item.get("steps")
        if not isinstance(steps, list) or not 3 <= len(steps) <= 5:
            errs.append("step_by_step needs 3-5 steps")
        else:
            for s in steps:
                if not isinstance(s, dict) or not _text(s.get("prompt")).strip() or not str(s.get("answer", "")).strip():
                    errs.append("every step needs a prompt and an answer")
                    break
    return errs


def validate_item(item: Any, bp: Blueprint) -> List[str]:
    """All problems with ``item`` for blueprint ``bp``. Empty list = acceptable."""
    if not isinstance(item, dict):
        return ["model output is not a JSON object"]
    errs = _check_structure(item, bp)
    if errs:  # structural problems make the maths checks meaningless
        return errs

    verify = item.get("verify")
    if item.get("conceptual"):
        if verify:
            errs.append("conceptual items must not include verify entries")
        return errs
    if not verify or not isinstance(verify, list):
        return ["computed question has no verify entries (set conceptual=true only if nothing is computed)"]
    for entry in verify:
        errs.extend(_check_verify_entry(entry))
    if errs:
        return errs
    return _check_answer_consistency(item)
