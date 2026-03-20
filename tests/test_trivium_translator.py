"""Tests for inter-dialect translation evidence collection."""

import json
from pathlib import Path

from organvm_engine.trivium.dialects import Dialect
from organvm_engine.trivium.translator import (
    TranslationEvidence,
    collect_evidence,
    translation_matrix,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "registry-trivium.json"


def _load_fixture() -> dict:
    with FIXTURE_PATH.open() as f:
        return json.load(f)


def test_translation_evidence_dataclass():
    ev = TranslationEvidence(
        source=Dialect.FORMAL_LOGIC,
        target=Dialect.EXECUTABLE_ALGORITHM,
        correspondences=[],
        aggregate_strength=0.0,
        preservation_assessment="untested",
        summary="",
    )
    assert ev.source == Dialect.FORMAL_LOGIC
    assert ev.aggregate_strength == 0.0
    assert ev.source_organ == "I"
    assert ev.target_organ == "III"


def test_collect_evidence_returns_evidence():
    ev = collect_evidence("I", "III", registry_path=FIXTURE_PATH)
    assert isinstance(ev, TranslationEvidence)
    assert ev.source == Dialect.FORMAL_LOGIC
    assert ev.target == Dialect.EXECUTABLE_ALGORITHM


def test_collect_evidence_has_correspondences():
    ev = collect_evidence("I", "III", registry_path=FIXTURE_PATH)
    assert len(ev.correspondences) > 0


def test_collect_evidence_has_summary():
    ev = collect_evidence("I", "III", registry_path=FIXTURE_PATH)
    assert ev.summary
    assert "Theoria" in ev.summary or "I" in ev.summary


def test_collect_evidence_preservation_assessed():
    ev = collect_evidence("I", "III", registry_path=FIXTURE_PATH)
    assert ev.preservation_assessment != "untested"


def test_collect_evidence_no_registry():
    ev = collect_evidence("I", "III")
    assert isinstance(ev, TranslationEvidence)
    assert ev.aggregate_strength == 0.0


def test_collect_evidence_with_loaded_registry():
    registry = _load_fixture()
    ev = collect_evidence("I", "III", registry=registry)
    assert isinstance(ev, TranslationEvidence)
    assert len(ev.correspondences) > 0


def test_translation_matrix_shape():
    registry = _load_fixture()
    matrix = translation_matrix(registry=registry)
    assert len(matrix) == 28  # C(8,2) pairs
    for key, ev in matrix.items():
        assert isinstance(ev, TranslationEvidence)
        assert isinstance(key, tuple)
        assert len(key) == 2


def test_translation_matrix_keys_are_dialect_pairs():
    registry = _load_fixture()
    matrix = translation_matrix(registry=registry)
    for (a, b), ev in matrix.items():
        assert isinstance(a, Dialect)
        assert isinstance(b, Dialect)
        assert a != b


def test_translation_matrix_i_iii_has_evidence():
    registry = _load_fixture()
    matrix = translation_matrix(registry=registry)
    key = (Dialect.FORMAL_LOGIC, Dialect.EXECUTABLE_ALGORITHM)
    assert key in matrix
    assert matrix[key].aggregate_strength > 0


def test_evidence_summary_mentions_tier():
    ev = collect_evidence("I", "III", registry_path=FIXTURE_PATH)
    # Tier 1 pair — summary should mention the tier
    assert "formal" in ev.summary.lower() or "tier" in ev.summary.lower()
