"""Tests for the Bridge — testament chain integration."""

from __future__ import annotations

from datetime import date, datetime, timezone

from organvm_engine.fossil.archivist import Intention
from organvm_engine.fossil.bridge import (
    emit_drift_event,
    emit_epoch_event,
    emit_intention_event,
    fossil_uri,
)
from organvm_engine.fossil.drift import DriftRecord
from organvm_engine.fossil.narrator import EpochStats
from organvm_engine.fossil.stratum import Archetype, Provenance


def test_emit_epoch_event() -> None:
    stats = EpochStats(
        epoch_id="EPOCH-006",
        epoch_name="Launch",
        start=date(2026, 2, 11),
        end=date(2026, 2, 11),
        commit_count=323,
        repos_touched=["engine"],
        organs_touched=["META"],
        archetype_counts={Archetype.INDIVIDUATION: 75},
        dominant_archetype=Archetype.INDIVIDUATION,
        secondary_archetype=None,
        top_repos=[("engine", 50)],
        total_insertions=400000,
        total_deletions=26000,
        trickster_ratio=0.07,
        authors=["test"],
    )
    event = emit_epoch_event("EPOCH-006", stats, None)
    assert event["event_type"] == "EPOCH_CLOSED"
    assert event["payload"]["epoch_id"] == "EPOCH-006"
    assert event["payload"]["commit_count"] == 323
    assert event["payload"]["dominant_archetype"] == "individuation"
    assert event["payload"]["epoch_name"] == "Launch"
    assert "date_range" in event["payload"]


def test_emit_epoch_event_with_chronicle() -> None:
    from pathlib import Path

    stats = EpochStats(
        epoch_id="EPOCH-001",
        epoch_name="Genesis",
        start=date(2026, 1, 22),
        end=date(2026, 2, 7),
        commit_count=10,
        repos_touched=["engine"],
        organs_touched=["META"],
        archetype_counts={Archetype.SELF: 10},
        dominant_archetype=Archetype.SELF,
        secondary_archetype=None,
        top_repos=[("engine", 10)],
        total_insertions=5000,
        total_deletions=200,
        trickster_ratio=0.0,
        authors=["test"],
    )
    chronicle = Path("/tmp/chronicle/EPOCH-001-genesis.md")
    event = emit_epoch_event("EPOCH-001", stats, chronicle)
    assert event["payload"]["chronicle_path"] == str(chronicle)


def test_emit_intention_event() -> None:
    intention = Intention(
        id="INT-2026-03-21-001",
        timestamp=datetime(2026, 3, 21, tzinfo=timezone.utc),
        raw_text="build the fossil record system for archaeological reconstruction",
        fingerprint="abc",
        uniqueness_score=0.92,
        archetypes=[Archetype.SELF],
        session_id="S30",
        epoch="EPOCH-012",
        provenance=Provenance.RECONSTRUCTED,
        source_file=None,
        tags=[],
    )
    event = emit_intention_event(intention)
    assert event["event_type"] == "INTENTION_BORN"
    assert "fossil record" in event["payload"]["preview"]
    assert event["payload"]["intention_id"] == "INT-2026-03-21-001"
    assert event["payload"]["uniqueness_score"] == 0.92
    assert event["payload"]["archetype"] == "self"


def test_emit_drift_event() -> None:
    intention = Intention(
        id="INT-2026-03-21-001",
        timestamp=datetime(2026, 3, 21, tzinfo=timezone.utc),
        raw_text="test",
        fingerprint="x",
        uniqueness_score=0.9,
        archetypes=[Archetype.ANIMUS],
        session_id=None,
        epoch=None,
        provenance=Provenance.RECONSTRUCTED,
        source_file=None,
        tags=[],
    )
    drift = DriftRecord(
        intention_id="INT-2026-03-21-001",
        intended_scope=["META"],
        actual_scope=["META", "I", "IV"],
        convergence=0.33,
        mutations=["I", "IV"],
        shadows=[],
        drift_archetype=Archetype.INDIVIDUATION,
    )
    event = emit_drift_event(drift, intention)
    assert event["event_type"] == "DRIFT_DETECTED"
    assert event["payload"]["convergence"] == 0.33
    assert event["payload"]["intention_id"] == "INT-2026-03-21-001"
    assert event["payload"]["drift_archetype"] == "individuation"
    assert event["payload"]["mutation_count"] == 2
    assert event["payload"]["shadow_count"] == 0


def test_fossil_uri() -> None:
    assert fossil_uri("epoch", "EPOCH-007") == "fossil://epoch/EPOCH-007"
    assert fossil_uri("intention", "INT-2026-03-21-001") == "fossil://intention/INT-2026-03-21-001"
    assert fossil_uri("drift", "DR-001") == "fossil://drift/DR-001"


def test_event_has_timestamp() -> None:
    """All events should include a timestamp."""
    intention = Intention(
        id="INT-2026-03-21-002",
        timestamp=datetime(2026, 3, 21, tzinfo=timezone.utc),
        raw_text="some test prompt about testing stuff here for length",
        fingerprint="xyz",
        uniqueness_score=0.85,
        archetypes=[Archetype.MOTHER],
        session_id=None,
        epoch=None,
        provenance=Provenance.RECONSTRUCTED,
        source_file=None,
        tags=[],
    )
    event = emit_intention_event(intention)
    assert "timestamp" in event
