"""Tests for epoch definitions and session boundary detection."""

from datetime import datetime, timedelta, timezone

from organvm_engine.fossil.epochs import (
    DECLARED_EPOCHS,
    assign_epoch,
    detect_session_boundaries,
)


def test_declared_epochs_exist():
    assert len(DECLARED_EPOCHS) >= 10
    names = [e.name for e in DECLARED_EPOCHS]
    assert "Genesis" in names
    assert "Launch" in names


def test_assign_epoch_by_date():
    dt = datetime(2026, 2, 11, 12, 0, tzinfo=timezone.utc)
    epoch = assign_epoch(dt)
    assert epoch is not None
    assert epoch.name == "Launch"


def test_assign_epoch_before_genesis():
    dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    epoch = assign_epoch(dt)
    assert epoch is None


def test_session_boundary_detection():
    base = datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)
    timestamps = [
        base,
        base + timedelta(minutes=10),
        base + timedelta(minutes=30),
        base + timedelta(hours=3),
        base + timedelta(hours=3, minutes=15),
    ]
    sessions = detect_session_boundaries(timestamps, gap_minutes=90)
    assert len(sessions) == 2
    assert len(sessions[0]) == 3
    assert len(sessions[1]) == 2


def test_session_single_commit():
    timestamps = [datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)]
    sessions = detect_session_boundaries(timestamps, gap_minutes=90)
    assert len(sessions) == 1
