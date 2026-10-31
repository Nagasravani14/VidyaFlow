"""
Question identity helpers shared by the seeder, the quiz engine and the tests.

``content_hash`` is intentionally a *template* hash: digits are masked before
hashing, so "What is (-5) + (-3)?" and "What is (-7) + (-2)?" produce the same
hash. The ``uq_question_concept_hash`` constraint therefore rejects "same
template, different numbers" at the database level, which is the duplicate
rule the product asks for.
"""

import hashlib
import re
import unicodedata

_MINUS_VARIANTS = {"\u2212": "-", "\u2013": "-", "\u2014": "-"}


def normalize_text(text: str) -> str:
    """Lower-case, unify unicode minus signs/quotes, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text or "")
    for src, dst in _MINUS_VARIANTS.items():
        text = text.replace(src, dst)
    text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


def mask_numbers(text: str) -> str:
    """Replace every number (incl. decimals and fractions' digits) with '#'."""
    return re.sub(r"\d+(?:\.\d+)?", "#", normalize_text(text))


def content_hash(question_type: str, stem: str) -> str:
    payload = f"{question_type}|{mask_numbers(stem)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
