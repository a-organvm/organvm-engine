"""Tests for the Archivist — intention capture and uniqueness scoring."""

from datetime import datetime, timezone

from organvm_engine.fossil.archivist import (
    Intention,
    classify_intention,
    compute_uniqueness,
    deserialize_intention,
    fingerprint_prompt,
    normalize_prompt,
    serialize_intention,
)
from organvm_engine.fossil.stratum import Archetype, Provenance


def test_normalize_prompt():
    text = "  Please can you   build a new   governance module  "
    result = normalize_prompt(text)
    assert "please" not in result
    assert "can you" not in result
    assert "governance" in result
    assert "  " not in result  # no double spaces


def test_normalize_strips_lets():
    result = normalize_prompt("let's build a thing okay so")
    assert "let's" not in result
    assert "okay so" not in result
    assert "build" in result
    assert "thing" in result


def test_fingerprint_deterministic():
    a = fingerprint_prompt("build governance module")
    b = fingerprint_prompt("build governance module")
    assert a == b
    assert len(a) == 64


def test_fingerprint_normalizes():
    a = fingerprint_prompt("Please build governance module")
    b = fingerprint_prompt("build governance module")
    assert a == b  # filler stripped


def test_uniqueness_no_existing():
    score = compute_uniqueness("abc", "build governance", [])
    assert score == 1.0


def test_uniqueness_identical():
    existing = [
        Intention(
            id="INT-2026-01-01-001",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            raw_text="build governance module",
            fingerprint=fingerprint_prompt("build governance module"),
            uniqueness_score=1.0,
            archetypes=[Archetype.ANIMUS],
            session_id=None,
            epoch=None,
            provenance=Provenance.RECONSTRUCTED,
            source_file=None,
            tags=[],
        )
    ]
    score = compute_uniqueness(
        fingerprint_prompt("build governance module"),
        "build governance module",
        existing,
    )
    assert score < 0.3  # very similar


def test_uniqueness_different():
    existing = [
        Intention(
            id="INT-2026-01-01-001",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            raw_text="build governance module",
            fingerprint=fingerprint_prompt("build governance module"),
            uniqueness_score=1.0,
            archetypes=[Archetype.ANIMUS],
            session_id=None,
            epoch=None,
            provenance=Provenance.RECONSTRUCTED,
            source_file=None,
            tags=[],
        )
    ]
    score = compute_uniqueness(
        fingerprint_prompt("design generative art pipeline for organ aesthetics"),
        "design generative art pipeline for organ aesthetics",
        existing,
    )
    assert score > 0.7  # very different


def test_classify_intention():
    result = classify_intention("build a testament self-referential event system")
    assert Archetype.SELF in result[:2]


def test_serialize_deserialize_roundtrip():
    intention = Intention(
        id="INT-2026-03-21-001",
        timestamp=datetime(2026, 3, 21, 3, 42, tzinfo=timezone.utc),
        raw_text="build the fossil record system",
        fingerprint="abc123",
        uniqueness_score=0.92,
        archetypes=[Archetype.SELF],
        session_id="S30",
        epoch="EPOCH-012",
        provenance=Provenance.RECONSTRUCTED,
        source_file="/some/path.jsonl",
        tags=["fossil"],
    )
    yaml_str = serialize_intention(intention)
    restored = deserialize_intention(yaml_str)
    assert restored.id == intention.id
    assert restored.raw_text == intention.raw_text
    assert restored.uniqueness_score == intention.uniqueness_score
    assert restored.archetypes == intention.archetypes


def test_serialize_deserialize_multiline_raw_text():
    intention = Intention(
        id="INT-2026-03-21-002",
        timestamp=datetime(2026, 3, 21, 4, 0, tzinfo=timezone.utc),
        raw_text="build a system that does:\n- thing one\n- thing two",
        fingerprint="def456",
        uniqueness_score=0.88,
        archetypes=[Archetype.ANIMUS, Archetype.SELF],
        session_id=None,
        epoch=None,
        provenance=Provenance.WITNESSED,
        source_file=None,
        tags=[],
    )
    yaml_str = serialize_intention(intention)
    restored = deserialize_intention(yaml_str)
    assert restored.raw_text == intention.raw_text
    assert restored.provenance == Provenance.WITNESSED


def test_serialize_deserialize_empty_optionals():
    intention = Intention(
        id="INT-2026-03-21-003",
        timestamp=datetime(2026, 3, 21, 5, 0, tzinfo=timezone.utc),
        raw_text="simple prompt text here",
        fingerprint="ghi789",
        uniqueness_score=1.0,
        archetypes=[Archetype.MOTHER],
        session_id=None,
        epoch=None,
        provenance=Provenance.RECONSTRUCTED,
        source_file=None,
        tags=[],
    )
    yaml_str = serialize_intention(intention)
    restored = deserialize_intention(yaml_str)
    assert restored.session_id is None
    assert restored.epoch is None
    assert restored.source_file is None
    assert restored.tags == []
