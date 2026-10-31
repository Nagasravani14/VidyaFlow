from types import SimpleNamespace

import pytest

from app.services.quiz_blueprints import (
    LEVEL_TO_BLOOM, LEVEL_TYPES, blueprint_for, build_blueprints,
)

CONCEPT = SimpleNamespace(id=1, name="Integer Operations", class_num=6, subject="Mathematics",
                          board="TS", chapter="Integers", description="d")


def test_blueprint_level_maps_to_bloom_and_difficulty():
    for level, bloom in LEVEL_TO_BLOOM.items():
        bp = blueprint_for(CONCEPT, level)
        assert bp.bloom_level == bloom and bp.level == level
    assert blueprint_for(CONCEPT, 1).difficulty == "easy"
    assert blueprint_for(CONCEPT, 3).difficulty == "medium"
    assert blueprint_for(CONCEPT, 5).difficulty == "hard"


def test_disallowed_type_or_level_is_rejected():
    with pytest.raises(ValueError):
        blueprint_for(CONCEPT, 1, "assertion_reasoning")
    with pytest.raises(ValueError):
        blueprint_for(CONCEPT, 6)


def test_batch_cycles_types_and_start_rotates():
    types = [b.question_type for b in build_blueprints(CONCEPT, 4, count=6)]
    assert types == list(LEVEL_TYPES[4]) * 2
    assert build_blueprints(CONCEPT, 4, 1, start=1)[0].question_type == LEVEL_TYPES[4][1]


def test_retrieval_query_is_blueprint_specific():
    q1 = blueprint_for(CONCEPT, 1).retrieval_query
    q5 = blueprint_for(CONCEPT, 5).retrieval_query
    assert q1 != q5 and "Integer Operations" in q1
