"""Tests for The Mirror — drift detection between intentions and reality."""

from datetime import datetime, timedelta, timezone

from organvm_engine.fossil.archivist import Intention
from organvm_engine.fossil.drift import (
    compute_drift,
    extract_scope_from_text,
    find_following_commits,
)
from organvm_engine.fossil.stratum import Archetype, FossilRecord, Provenance


def _make_intention(text: str = "build governance", ts: datetime | None = None) -> Intention:
    return Intention(
        id="INT-2026-03-21-001",
        timestamp=ts or datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
        raw_text=text,
        fingerprint="x",
        uniqueness_score=0.9,
        archetypes=[Archetype.ANIMUS],
        session_id=None,
        epoch=None,
        provenance=Provenance.RECONSTRUCTED,
        source_file=None,
        tags=[],
    )


def _make_record(
    organ: str = "META",
    repo: str = "organvm-engine",
    ts: datetime | None = None,
) -> FossilRecord:
    return FossilRecord(
        commit_sha="abc",
        timestamp=ts or datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
        author="test",
        organ=organ,
        repo=repo,
        message="feat: test",
        conventional_type="feat",
        files_changed=1,
        insertions=10,
        deletions=2,
        archetypes=[Archetype.ANIMUS],
        provenance=Provenance.RECONSTRUCTED,
        session_id=None,
        epoch=None,
        tags=[],
        prev_hash="",
    )


def test_extract_scope_organ():
    scope = extract_scope_from_text("work on ORGAN-I theoria research")
    assert "I" in scope or "theoria" in [s.lower() for s in scope]


def test_extract_scope_repo():
    scope = extract_scope_from_text("update organvm-engine governance module")
    assert any("engine" in s.lower() for s in scope)


def test_extract_scope_keyword_mapping():
    scope = extract_scope_from_text("write an essay about the system")
    assert "V" in scope  # "essay" maps to organ V


def test_extract_scope_multiple():
    scope = extract_scope_from_text("integrate ORGAN-I theoria with ORGAN-II poiesis")
    # Should find references to both organs
    assert len(scope) >= 2


def test_find_following_commits():
    base = datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc)
    intention = _make_intention(ts=base)
    records = [
        _make_record(ts=base - timedelta(hours=1)),  # before -- excluded
        _make_record(ts=base + timedelta(hours=1)),  # within window
        _make_record(ts=base + timedelta(hours=49)),  # after window -- excluded
    ]
    following = find_following_commits(intention, records, window_hours=48)
    assert len(following) == 1


def test_find_following_commits_empty():
    base = datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc)
    intention = _make_intention(ts=base)
    records = [
        _make_record(ts=base - timedelta(hours=2)),
        _make_record(ts=base - timedelta(hours=5)),
    ]
    following = find_following_commits(intention, records, window_hours=48)
    assert len(following) == 0


def test_compute_drift_convergent():
    intention = _make_intention("work on organvm-engine governance")
    commits = [_make_record(organ="META", repo="organvm-engine")]
    drift = compute_drift(intention, commits)
    assert drift.convergence > 0.0
    assert isinstance(drift.drift_archetype, Archetype)


def test_compute_drift_no_commits():
    intention = _make_intention("build something new")
    drift = compute_drift(intention, [])
    assert drift.convergence == 0.0
    assert drift.drift_archetype == Archetype.SHADOW  # nothing done = avoidance


def test_compute_drift_trickster():
    """When actual scope diverges completely from intended scope."""
    intention = _make_intention("work on ORGAN-I theoria research")
    # Commits went to a completely different organ
    commits = [
        _make_record(organ="III", repo="some-product"),
        _make_record(organ="III", repo="another-product"),
    ]
    drift = compute_drift(intention, commits)
    # Low convergence should classify as Trickster
    assert drift.convergence < 0.3


def test_drift_record_fields():
    intention = _make_intention("work on organvm-engine")
    commits = [_make_record(organ="META", repo="organvm-engine")]
    drift = compute_drift(intention, commits)
    assert drift.intention_id == intention.id
    assert isinstance(drift.intended_scope, list)
    assert isinstance(drift.actual_scope, list)
    assert isinstance(drift.mutations, list)
    assert isinstance(drift.shadows, list)
