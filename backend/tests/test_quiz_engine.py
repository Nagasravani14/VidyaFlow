"""
Step 3 tests. No real Gemini call and no Chroma: the LLM and retriever are fakes.
"""
import copy

import pytest

from app.models.quiz import Concept, Question, QuestionAttempt, QuizAttempt
from app.seed.quiz_seed import seed_quiz_content
from app.services.gemini_service import GeminiAuthError, GeminiError, GeminiQuotaError
from app.services.quiz_blueprints import blueprint_for
from app.services.quiz_engine import (
    ORIGIN_AI, ORIGIN_BANK, ORIGIN_CURATED_FALLBACK, QuizEngine, public_question,
)
from app.services.quiz_llm import QuizLLMOutputError, build_prompt, build_system_instruction, parse_item
from app.services.quiz_validation import validate_item


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, bp):
        self.calls.append(bp)
        return [{"text": "Adding two negative integers gives a negative integer."}]


class ScriptedLLM:
    """Returns / raises the scripted items in order; counts calls (one call = one question)."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = 0
        self.feedbacks = []

    def generate_item(self, bp, passages, avoid_stems, feedback=None):
        self.calls += 1
        self.feedbacks.append(feedback)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return copy.deepcopy(step)


def good_numerical(stem="At dawn the temperature was -9 degrees Celsius. By noon it rose by 14 degrees. What was it at noon?",
                   answer="5", expr="-9+14"):
    return {"type": "numerical", "objective": "Apply integer addition.", "stem": stem, "answer": answer, "tolerance": 0,
            "hint": "A rise is added to the start value.", "explanation": "-9 + 14 = 5.",
            "verify": [["eval", expr, "5"]]}


def good_mcq():
    return {"type": "mcq", "objective": "Add negatives.", "stem": "What is (-6) + (-4)?", "correct": "-10",
            "distractors": [{"text": "2", "misconception": "subtracted magnitudes"},
                            {"text": "10", "misconception": "ignored the negative signs"},
                            {"text": "-2", "misconception": "subtracted in the wrong direction"}],
            "hint": "Move left on the number line.", "explanation": "Both negative, so add sizes: -10.",
            "verify": [["eval", "(-6)+(-4)", "-10"]]}


@pytest.fixture
def env(db_session):
    seed_quiz_content(db_session)
    concept = db_session.query(Concept).filter_by(name="Integer Operations").one()
    return db_session, concept


def engine(db, llm, retriever=None, **kw):
    return QuizEngine(db, llm=llm, retriever=retriever or FakeRetriever(), **kw)


# ----------------------------------------------------------------- validation
def bp3(concept, qtype="numerical"):
    return blueprint_for(concept, 3, qtype)


def test_valid_numerical_passes(env):
    _, c = env
    assert validate_item(good_numerical(), bp3(c)) == []


def test_wrong_answer_key_is_caught_by_sympy(env):
    _, c = env
    bad = good_numerical(answer="6")  # verify says -9+14 = 5, but the key says 6
    errs = validate_item(bad, bp3(c))
    assert errs and "does not match" in errs[0]


def test_false_verify_entry_is_caught(env):
    _, c = env
    bad = good_numerical()
    bad["verify"] = [["eval", "-9+14", "6"]]
    assert any("verify failed" in e for e in validate_item(bad, bp3(c)))


def test_numerical_without_verify_or_marked_conceptual_is_rejected(env):
    _, c = env
    no_verify = good_numerical(); del no_verify["verify"]
    assert validate_item(no_verify, bp3(c))
    conceptual = good_numerical(); conceptual["conceptual"] = True; del conceptual["verify"]
    assert any("conceptual" in e for e in validate_item(conceptual, bp3(c)))


def test_unsafe_expression_is_rejected_not_evaluated(env):
    _, c = env
    for evil in ["__import__('os').system('x')", "10**10**10", "open('f')", "9**99"]:
        bad = good_numerical(); bad["verify"] = [["eval", evil, "5"]]
        errs = validate_item(bad, bp3(c))
        assert errs and "unsafe" in " ".join(errs).lower() or "could not evaluate" in " ".join(errs)


def test_mcq_structure_rules(env):
    _, c = env
    bp = blueprint_for(c, 1, "mcq")
    assert validate_item(good_mcq(), bp) == []
    dup = good_mcq(); dup["distractors"][0]["text"] = "-10"
    assert any("distinct" in e for e in validate_item(dup, bp))
    untagged = good_mcq(); untagged["distractors"][1]["misconception"] = ""
    assert any("misconception" in e for e in validate_item(untagged, bp))
    two = good_mcq(); two["distractors"].pop()
    assert any("exactly 3" in e for e in validate_item(two, bp))
    wrong_numeric = good_mcq(); wrong_numeric["correct"] = "-9"
    assert validate_item(wrong_numeric, bp)


def test_type_must_match_blueprint_and_filler_rejected(env):
    _, c = env
    assert any("blueprint" in e for e in validate_item(good_mcq(), bp3(c, "numerical")))
    filler = good_mcq(); filler["distractors"][0]["text"] = "Option A"
    filler["explanation"] = "Option B is wrong. Both negative, so add sizes: -10."
    assert validate_item(filler, blueprint_for(c, 1, "mcq"))


# ----------------------------------------------------------------- generation
def test_one_llm_call_per_question_and_retrieval_once_per_blueprint(env):
    db, c = env
    retr, llm = FakeRetriever(), ScriptedLLM(good_numerical())
    out = engine(db, llm, retr).generate_for_blueprint(bp3(c))
    assert out.origin == ORIGIN_AI and out.question.source == "ai" and out.llm_calls == 1
    assert llm.calls == 1 and len(retr.calls) == 1
    stored = db.get(Question, out.question.id)
    assert stored.level == 3 and stored.bloom_level == "apply" and stored.assessment_purpose == "practice"


def test_retry_after_rejection_sends_feedback_and_reuses_retrieval(env):
    db, c = env
    retr = FakeRetriever()
    llm = ScriptedLLM(good_numerical(answer="6"), good_numerical())
    out = engine(db, llm, retr).generate_for_blueprint(bp3(c))
    assert out.question is not None and out.origin == ORIGIN_AI
    assert llm.calls == 2 and len(retr.calls) == 1
    assert llm.feedbacks[0] is None and llm.feedbacks[1]
    assert len(out.rejections) == 1


def test_same_template_with_new_numbers_is_rejected_as_duplicate(env):
    db, c = env
    e = engine(db, ScriptedLLM(good_numerical()))
    first = e.generate_for_blueprint(bp3(c))
    assert first.origin == ORIGIN_AI
    # identical template, only the numbers changed
    twin = good_numerical("At dawn the temperature was -3 degrees Celsius. By noon it rose by 8 degrees. What was it at noon?",
                          "5", "-3+8")
    e2 = engine(db, ScriptedLLM(twin, twin, twin))
    out = e2.generate_for_blueprint(bp3(c))
    assert out.origin == ORIGIN_CURATED_FALLBACK  # all attempts were duplicates
    assert any("template" in r for r in out.rejections)


def test_embedding_near_duplicate_is_rejected(env):
    db, c = env
    embed = lambda text: [1.0, 0.0, 0.0]  # every stem looks identical
    e = engine(db, ScriptedLLM(good_numerical()), embedder=embed)
    assert e.generate_for_blueprint(bp3(c)).origin == ORIGIN_AI
    different = good_numerical("A submarine sits at -40 m and climbs 15 m. Where is it now, in metres?", "-25", "-40+15")
    different["verify"] = [["eval", "-40+15", "-25"]]
    out = engine(db, ScriptedLLM(different, different, different), embedder=embed).generate_for_blueprint(bp3(c))
    assert out.origin == ORIGIN_CURATED_FALLBACK
    assert any("too similar" in r for r in out.rejections)


@pytest.mark.parametrize("err", [GeminiAuthError(), GeminiQuotaError()])
def test_auth_or_quota_error_falls_back_immediately_without_retrying(env, err):
    db, c = env
    llm = ScriptedLLM(err)
    out = engine(db, llm).generate_for_blueprint(bp3(c))
    assert llm.calls == 1
    assert out.origin == ORIGIN_CURATED_FALLBACK and out.question.source == "curated"
    assert out.fallback_reason


def test_malformed_output_retries_then_falls_back(env):
    db, c = env
    llm = ScriptedLLM(QuizLLMOutputError(), {"type": "numerical"}, "not a dict")
    out = engine(db, llm).generate_for_blueprint(bp3(c))
    assert llm.calls == 3 and out.origin == ORIGIN_CURATED_FALLBACK
    assert out.question.level == 3


def test_fallback_respects_exclusions_and_reports_when_exhausted(env):
    db, c = env
    curated_l3 = [q.id for q in db.query(Question).filter_by(concept_id=c.id, level=3, source="curated")]
    out = engine(db, ScriptedLLM(GeminiError("boom"), GeminiError("boom"), GeminiError("boom"))).generate_for_blueprint(
        bp3(c), exclude_ids=curated_l3)
    assert out.question is None and "no unused curated" in out.fallback_reason


# ----------------------------------------------------------------- selection / rule 7
def attempt(db, concept, student, question):
    qa = QuizAttempt(student_id=student, concept_id=concept.id, mode="practice", current_level=question.level)
    db.add(qa); db.flush()
    db.add(QuestionAttempt(quiz_attempt_id=qa.id, student_id=student, question_id=question.id,
                           level=question.level, is_correct=True))
    db.commit()


def test_recent_questions_are_not_repeated_unless_revision(env):
    db, c = env
    l1 = db.query(Question).filter_by(concept_id=c.id, level=1).order_by(Question.id).all()
    for q in l1:
        attempt(db, c, "s1", q)
    # practice: every stored L1 question is recent, so the engine must generate a new one
    llm = ScriptedLLM(good_mcq())
    out = engine(db, llm).select_question("s1", c.id, 1, mode="practice")
    assert out.origin == ORIGIN_AI and out.question.id not in {q.id for q in l1}
    # revision: repeats are allowed, so a stored question is served and the LLM is not called
    llm2 = ScriptedLLM()
    out2 = engine(db, llm2).select_question("s1", c.id, 1, mode="revision")
    assert out2.origin == ORIGIN_BANK and llm2.calls == 0


def test_other_students_history_does_not_matter(env):
    db, c = env
    first = db.query(Question).filter_by(concept_id=c.id, level=1).order_by(Question.id).first()
    attempt(db, c, "s1", first)
    out = engine(db, ScriptedLLM()).select_question("s2", c.id, 1)
    assert out.question.id == first.id


def test_questions_already_in_this_quiz_are_excluded_even_in_revision(env):
    db, c = env
    l1 = db.query(Question).filter_by(concept_id=c.id, level=1).order_by(Question.id).all()
    out = engine(db, ScriptedLLM()).select_question("s1", c.id, 1, mode="revision",
                                                    extra_exclude_ids=[l1[0].id])
    assert out.question.id != l1[0].id


def test_when_everything_is_used_and_ai_is_down_the_least_recent_is_repeated(env):
    db, c = env
    l1 = db.query(Question).filter_by(concept_id=c.id, level=1).order_by(Question.id).all()
    for q in l1:
        attempt(db, c, "s1", q)
    out = engine(db, ScriptedLLM(GeminiQuotaError())).select_question("s1", c.id, 1)
    assert out.question.id == l1[0].id  # attempted first = least recently seen
    assert "repeated" in out.fallback_reason


# ----------------------------------------------------------------- safety / prompts
def test_public_question_never_exposes_answers(env):
    db, c = env
    for q in db.query(Question).all():
        view = public_question(q)
        assert "correct_answer" not in view and "distractor_misconceptions" not in view and "explanation" not in view
        if q.question_type == "step_by_step":
            assert "answer" not in str(view["options"])


def test_prompt_is_one_question_with_blueprint_and_passages(env):
    _, c = env
    bp = blueprint_for(c, 4, "multi_select")
    system = build_system_instruction(bp)
    assert "Class 6" in system and "L4" in system and "analyze" in system and "multi_select" in system
    user = build_prompt(bp, [{"text": "Rule text"}], ["old stem"], ["fix this"])
    assert "Rule text" in user and "old stem" in user and "fix this" in user


def test_parse_item_handles_fences_lists_and_garbage():
    assert parse_item('```json\n{"type":"mcq"}\n```') == {"type": "mcq"}
    assert parse_item('[{"type":"mcq"}]') == {"type": "mcq"}
    with pytest.raises(QuizLLMOutputError):
        parse_item("not json")
    with pytest.raises(QuizLLMOutputError):
        parse_item("[]")
