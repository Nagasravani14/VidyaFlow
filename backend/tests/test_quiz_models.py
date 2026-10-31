"""
Step 1 tests: data model, constraints, seeding, curated-bank correctness and
migration/model drift. No LLM or embedding model is used here.
"""
import os
import re
import subprocess
import sys
from collections import Counter

import pytest
import sympy as sp
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from app.models.quiz import (
    LEVEL_TO_BLOOM,
    Concept,
    ConceptPrerequisite,
    Question,
    QuestionAttempt,
    QuizAttempt,
    StudentConceptLevel,
    StudentConceptMastery,
)
from app.models.tutor import PracticeSubmission
from app.seed.curated_bank import BANK
from app.seed.quiz_seed import build_question_payload, seed_concepts, seed_curated_bank, seed_quiz_content
from app.services.question_hash import content_hash, mask_numbers

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
TRANSFORMS = standard_transformations + (implicit_multiplication_application,)
X = sp.Symbol("x")
NUMERIC_OPTION = re.compile(r"^(x\s*=\s*)?-?\d+(\.\d+)?(\s*m)?$")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _sym(expr: str):
    return sp.sympify(expr, rational=True)


def _parse(text: str):
    text = text.replace("^", "**").replace(" x ", " * ")
    return parse_expr(text, transformations=TRANSFORMS, local_dict={"x": X})


def _solve_text(equation: str):
    lhs, rhs = equation.replace("^", "**").split("=")
    sol = sp.solve(sp.Eq(_parse(lhs), _parse(rhs)), X)
    return sol


def _check_verify_entry(entry):
    kind = entry[0]
    if kind == "eval":
        _, expr, expected = entry
        assert sp.simplify(_sym(expr) - _sym(expected)) == 0, f"eval failed: {expr} != {expected}"
    elif kind == "solve":
        _, equation, var, expected = entry
        sol = _solve_text(equation)
        if expected == "none":
            assert sol == [], f"{equation} should have no solution, got {sol}"
        else:
            assert len(sol) == 1 and sp.simplify(sol[0] - _sym(expected)) == 0, f"{equation}: got {sol}, expected {expected}"
    elif kind == "equiv":
        _, e1, e2, should_be_equal = entry
        diff = sp.simplify(_parse(e1) - _parse(e2))
        assert (diff == 0) == should_be_equal, f"equiv({e1}, {e2}) expected {should_be_equal}"
    else:  # pragma: no cover
        raise AssertionError(f"unknown verify kind {kind}")


def _expected_values(item):
    return {e[2] if e[0] == "eval" else e[3] for e in item.get("verify", []) if e[0] in ("eval", "solve")}


def _norm_num(s):
    return str(s).replace(" ", "").replace("\u2212", "-")


@pytest.fixture
def seeded(db_session):
    seed_quiz_content(db_session)
    return db_session


# --------------------------------------------------------------------------
# seeding
# --------------------------------------------------------------------------
def test_three_concepts_seeded_with_prerequisite_edges(seeded):
    concepts = {c.name: c for c in seeded.query(Concept).all()}
    assert set(concepts) == {"Integer Operations", "Algebraic Expressions", "Linear Equations"}
    assert concepts["Integer Operations"].class_num == 6
    assert concepts["Algebraic Expressions"].class_num == 7
    assert concepts["Linear Equations"].class_num == 8

    edges = {(e.concept_id, e.prerequisite_concept_id) for e in seeded.query(ConceptPrerequisite).all()}
    assert edges == {
        (concepts["Algebraic Expressions"].id, concepts["Integer Operations"].id),
        (concepts["Linear Equations"].id, concepts["Algebraic Expressions"].id),
    }


def test_seeding_is_idempotent(db_session):
    first = seed_quiz_content(db_session)
    q1 = db_session.query(Question).count()
    second = seed_quiz_content(db_session)
    assert first["curated_questions_inserted"] == len(BANK)
    assert second["curated_questions_inserted"] == 0
    assert db_session.query(Question).count() == q1 == len(BANK)
    assert db_session.query(Concept).count() == 3


def test_seed_does_not_duplicate_concepts_created_by_migration(db_session):
    """The Alembic migration inserts the concepts; the seeder must reuse them."""
    db_session.add(Concept(id=1, class_num=6, subject="Mathematics", name="Integer Operations"))
    db_session.commit()
    seed_quiz_content(db_session)
    assert db_session.query(Concept).count() == 3
    assert db_session.query(Concept).filter_by(name="Integer Operations").count() == 1


# --------------------------------------------------------------------------
# curated bank structure
# --------------------------------------------------------------------------
def test_bank_has_at_least_three_questions_per_level_per_concept(seeded):
    counts = Counter((q.concept_id, q.level) for q in seeded.query(Question).all())
    for concept in seeded.query(Concept).all():
        for level in range(1, 6):
            assert counts[(concept.id, level)] >= 3, f"{concept.name} L{level} has {counts[(concept.id, level)]}"


def test_every_question_has_exactly_one_level_matching_bloom(seeded):
    for q in seeded.query(Question).all():
        assert 1 <= q.level <= 5
        assert q.bloom_level == LEVEL_TO_BLOOM[q.level]
        assert q.source == "curated"
        assert q.assessment_purpose == "practice"


FORBIDDEN_FILLER = ("option a", "option b", "alternative c", "comprehensive exam question", "lorem")


def test_no_placeholder_or_filler_text(seeded):
    for q in seeded.query(Question).all():
        blob = " ".join([q.stem, q.explanation, q.hint or "", str(q.options)]).lower()
        for bad in FORBIDDEN_FILLER:
            assert bad not in blob, f"filler '{bad}' in question {q.id}"


def test_choice_questions_are_well_formed_and_distractors_are_tagged(seeded):
    for q in seeded.query(Question).filter(Question.question_type.in_(["mcq", "assertion_reasoning", "multi_select"])).all():
        keys = [o["key"] for o in q.options]
        texts = [o["text"] for o in q.options]
        assert keys == ["A", "B", "C", "D"][: len(keys)] and len(keys) == 4
        assert len(set(texts)) == len(texts), f"duplicate options in {q.id}"
        correct = [q.correct_answer] if isinstance(q.correct_answer, str) else q.correct_answer
        assert set(correct) <= set(keys)
        if q.question_type == "multi_select":
            assert len(correct) >= 2 and correct == sorted(correct)
        else:
            assert isinstance(q.correct_answer, str)
        wrong = set(keys) - set(correct)
        tagged = q.distractor_misconceptions or {}
        assert set(tagged) == wrong, f"question {q.id}: distractor tags {set(tagged)} != wrong keys {wrong}"
        assert all(isinstance(v, str) and len(v) > 5 for v in tagged.values())


def test_correct_key_is_not_always_a(seeded):
    keys = Counter(q.correct_answer for q in seeded.query(Question).filter_by(question_type="mcq").all())
    assert len(keys) >= 3, f"correct key distribution too narrow: {keys}"
    assert keys["A"] < sum(keys.values()) * 0.5


def test_all_expected_question_types_are_exercised(seeded):
    types = {q.question_type for q in seeded.query(Question).all()}
    assert {"mcq", "multi_select", "true_false", "fill_blank", "numerical", "assertion_reasoning", "step_by_step"} <= types


def test_step_by_step_shape(seeded):
    for q in seeded.query(Question).filter_by(question_type="step_by_step").all():
        steps = q.options["steps"]
        assert len(steps) >= 3 and len(q.correct_answer) == len(steps)
        assert all(s["prompt"] for s in steps)
        assert "answer" not in str(q.options), "answers must not live in the browser-safe options"


# --------------------------------------------------------------------------
# curated bank correctness (sympy, independent of the typed keys)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("item", BANK, ids=lambda i: f"{i['concept']}-L{i['level']}-{i['stem'][:40]}")
def test_curated_bank_math_is_correct(item):
    if item.get("conceptual"):
        assert not item.get("verify"), "conceptual items should not claim a computation"
        return
    assert item.get("verify"), "computed item has no verify entries"
    for entry in item["verify"]:
        _check_verify_entry(entry)

    payload = build_question_payload(item)
    expected = {_norm_num(v) for v in _expected_values(item)}
    qtype = item["type"]
    if qtype == "numerical":
        assert _norm_num(payload["correct_answer"]["value"]) in expected
    elif qtype == "fill_blank" and expected:
        assert any(_norm_num(a) in expected for a in payload["correct_answer"])
    elif qtype == "step_by_step":
        assert _norm_num(payload["correct_answer"][-1]) in expected
    elif qtype == "mcq" and expected and NUMERIC_OPTION.match(item["correct"].strip()):
        # Only when the correct option IS a numeric result (e.g. "-8", "-16 m", "x = 16").
        # Options that name an operation or a pair (e.g. "Subtract 7") are covered by the
        # verify entries above plus the option-level checks below.
        value = re.sub(r"^x\s*=\s*|\s*m$", "", item["correct"].strip())
        assert _norm_num(value) in expected


def test_multi_select_options_checked_individually():
    """Evaluate every option text, not just the stored key set."""
    by_stem = {i["stem"]: i for i in BANK if i["type"] == "multi_select"}

    # Integer Operations L4: which expressions equal -12?
    item = by_stem["Select ALL the expressions that equal -12."]
    for text in item["correct_set"]:
        assert sp.simplify(_parse(text) + 12) == 0, text
    for text, _ in item["distractors"]:
        assert sp.simplify(_parse(text) + 12) != 0, text

    # Algebraic Expressions L4: equivalent to 3(x+2) - x
    item = by_stem["Select ALL expressions equivalent to 3(x + 2) - x."]
    target = _parse("3(x + 2) - x")
    for text in item["correct_set"]:
        assert sp.simplify(_parse(text) - target) == 0, text
    for text, _ in item["distractors"]:
        assert sp.simplify(_parse(text) - target) != 0, text

    # Linear Equations L4: solution is x = 3
    item = by_stem["Select ALL equations whose solution is x = 3."]
    for text in item["correct_set"]:
        assert _solve_text(text) == [3], text
    for text, _ in item["distractors"]:
        assert _solve_text(text) != [3], text


def test_same_solution_mcq_options_checked_individually():
    item = next(i for i in BANK if i["stem"] == "Which equation has the same solution as 2x = 10?")
    assert _solve_text(item["correct"]) == [5]
    for text, _ in item["distractors"]:
        assert _solve_text(text) != [5], text


# --------------------------------------------------------------------------
# hashing / duplicate rule
# --------------------------------------------------------------------------
def test_same_template_with_changed_numbers_has_same_hash():
    a = content_hash("mcq", "What is the value of (-5) + (-3)?")
    b = content_hash("mcq", "What is the value of (-7) + (-12)?")
    assert a == b
    assert mask_numbers("Solve 3x + 5 = 20") == mask_numbers("Solve 4x + 9 = 41")


def test_different_templates_or_types_have_different_hashes():
    assert content_hash("mcq", "Solve 3x + 5 = 20") != content_hash("mcq", "Solve 2(x - 3) = 10")
    assert content_hash("mcq", "Solve 3x + 5 = 20") != content_hash("numerical", "Solve 3x + 5 = 20")


def test_unicode_minus_and_spacing_do_not_defeat_the_hash():
    assert content_hash("mcq", "Compute (\u22125)  +  (\u22123)") == content_hash("mcq", "compute (-5) + (-3)")


def test_curated_bank_has_no_internal_template_duplicates():
    hashes = Counter((i["concept"], content_hash(i["type"], i["stem"])) for i in BANK)
    dupes = [k for k, v in hashes.items() if v > 1]
    assert not dupes, f"template duplicates in curated bank: {dupes}"


# --------------------------------------------------------------------------
# database constraints
# --------------------------------------------------------------------------
def _question_kwargs(concept_id, **over):
    base = dict(
        concept_id=concept_id, level=1, bloom_level="remember", question_type="true_false",
        difficulty="easy", stem="True or false: 1 + 1 = 2.", options=None, correct_answer=True,
        explanation="Because it is.", source="curated", assessment_purpose="practice",
        content_hash=content_hash("true_false", "True or false: 1 + 1 = 2."),
    )
    base.update(over)
    return base


def test_teacher_assignment_purpose_cannot_be_stored_as_a_practice_question(seeded):
    concept = seeded.query(Concept).first()
    for bad in ("teacher_assignment", "assignment", "homework"):
        seeded.add(Question(**_question_kwargs(concept.id, assessment_purpose=bad, content_hash=f"x{bad}")))
        with pytest.raises(IntegrityError):
            seeded.commit()
        seeded.rollback()


@pytest.mark.parametrize("field,value", [("level", 0), ("level", 6), ("question_type", "essay"),
                                         ("source", "teacher"), ("difficulty", "extreme"), ("bloom_level", "create")])
def test_question_check_constraints(seeded, field, value):
    concept = seeded.query(Concept).first()
    seeded.add(Question(**_question_kwargs(concept.id, **{field: value, "content_hash": "unique-" + field})))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


def test_duplicate_content_hash_in_same_concept_is_rejected(seeded):
    concept = seeded.query(Concept).first()
    existing = seeded.query(Question).filter_by(concept_id=concept.id).first()
    seeded.add(Question(**_question_kwargs(concept.id, content_hash=existing.content_hash)))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


def test_student_concept_level_and_mastery_are_unique_per_student_and_concept(seeded):
    concept = seeded.query(Concept).first()
    seeded.add(StudentConceptLevel(student_id="s1", concept_id=concept.id))
    seeded.add(StudentConceptMastery(student_id="s1", concept_id=concept.id))
    seeded.commit()

    seeded.add(StudentConceptLevel(student_id="s1", concept_id=concept.id))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()
    seeded.add(StudentConceptMastery(student_id="s1", concept_id=concept.id))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()

    # another student, same concept: allowed
    seeded.add(StudentConceptLevel(student_id="s2", concept_id=concept.id))
    seeded.commit()


def test_student_concept_level_defaults_and_stored_values_round_trip(seeded):
    concept = seeded.query(Concept).first()
    row = StudentConceptLevel(student_id="s1", concept_id=concept.id)
    seeded.add(row)
    seeded.commit()
    seeded.refresh(row)
    assert row.comfortable_level == 1
    assert row.max_level_reached == 1
    assert row.struggling_level is None and row.struggling_since is None
    assert row.failed_counts == {}
    assert row.possible_prerequisite_gap is False

    row.struggling_level = 4
    row.failed_counts = {"4": 1}
    seeded.commit()
    seeded.refresh(row)
    assert row.struggling_level == 4 and row.failed_counts == {"4": 1}

    row.struggling_level = 9
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


def test_mastery_status_and_range_constraints(seeded):
    concept = seeded.query(Concept).first()
    seeded.add(StudentConceptMastery(student_id="s1", concept_id=concept.id, status="expert"))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()
    seeded.add(StudentConceptMastery(student_id="s1", concept_id=concept.id, mastery_score=1.5))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


def test_quiz_and_question_attempts_store_student_id(seeded):
    concept = seeded.query(Concept).first()
    question = seeded.query(Question).filter_by(concept_id=concept.id, level=1).first()
    quiz = QuizAttempt(student_id="s1", concept_id=concept.id, mode="practice", current_level=1)
    seeded.add(quiz)
    seeded.flush()
    seeded.add(QuestionAttempt(quiz_attempt_id=quiz.id, student_id="s1", question_id=question.id,
                               level=1, answer="B", is_correct=True, hints_used=0, response_time_ms=4200))
    seeded.commit()
    stored = seeded.query(QuestionAttempt).one()
    assert stored.student_id == "s1" and stored.attempt_no == 1

    seeded.add(QuizAttempt(student_id="s1", concept_id=concept.id, mode="teacher_assignment"))
    with pytest.raises(IntegrityError):
        seeded.commit()
    seeded.rollback()


def test_practice_submissions_now_has_student_id(seeded):
    sub = PracticeSubmission(student_id="s1", question_text="q", student_answer="a", is_correct=True)
    seeded.add(sub)
    seeded.commit()
    assert seeded.query(PracticeSubmission).filter_by(student_id="s1").count() == 1


# --------------------------------------------------------------------------
# migration vs models
# --------------------------------------------------------------------------
def test_alembic_migration_matches_models_and_seeds_concepts(tmp_path):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.database import Base
    import app.models  # noqa: F401

    db_file = tmp_path / "migrated.db"
    url = f"sqlite:///{db_file}"
    env = {**os.environ, "DATABASE_URL": url}

    for cmd in (["upgrade", "head"], ["downgrade", "-1"], ["upgrade", "head"]):
        result = subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=BACKEND_DIR, env=env,
                                capture_output=True, text=True)
        assert result.returncode == 0, f"alembic {' '.join(cmd)} failed:\n{result.stderr}"

    engine = create_engine(url)
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": False}), Base.metadata)
        names = [r[0] for r in conn.exec_driver_sql("SELECT name FROM concepts ORDER BY id")]
    assert diffs == [], f"models and migration drifted: {diffs}"
    assert names == ["Integer Operations", "Algebraic Expressions", "Linear Equations"]
