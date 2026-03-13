"""Tests for organvm_engine.pulse.events — file-based event bus."""

from __future__ import annotations

import json
import time

import pytest

from organvm_engine.pulse.events import (
    ALL_EVENT_TYPES,
    GATE_CHANGED,
    MOOD_SHIFTED,
    ORGANISM_COMPUTED,
    PULSE_HEARTBEAT,
    REGISTRY_UPDATED,
    REPO_PROMOTED,
    Event,
    emit,
    event_counts,
    recent,
    replay,
)


@pytest.fixture(autouse=True)
def _isolated_events(tmp_path, monkeypatch):
    """Route the event log to a temp directory."""
    events_file = tmp_path / "events.jsonl"
    monkeypatch.setattr(
        "organvm_engine.pulse.events._events_path",
        lambda: events_file,
    )
    return events_file


# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------

class TestEventDataclass:
    def test_event_creation(self):
        """Event populates timestamp automatically when not provided."""
        ev = Event(event_type=REGISTRY_UPDATED, source="test")
        assert ev.event_type == REGISTRY_UPDATED
        assert ev.source == "test"
        assert ev.timestamp  # non-empty
        assert "T" in ev.timestamp  # ISO format

    def test_event_from_dict(self):
        """Round-trip through to_json and back via json.loads."""
        ev = Event(
            event_type=REPO_PROMOTED,
            source="engine",
            payload={"repo": "r1", "new_status": "CANDIDATE"},
        )
        data = json.loads(ev.to_json())
        restored = Event(
            event_type=data["event_type"],
            source=data["source"],
            payload=data["payload"],
            timestamp=data["timestamp"],
        )
        assert restored.event_type == ev.event_type
        assert restored.source == ev.source
        assert restored.payload == ev.payload
        assert restored.timestamp == ev.timestamp

    def test_event_payload(self):
        """Payload dict is preserved through emit/replay cycle."""
        payload = {"key": "value", "nested": {"a": 1}}
        emit(GATE_CHANGED, "test", payload)
        events = replay()
        assert len(events) == 1
        assert events[0].payload == payload


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------

class TestEmit:
    def test_emit_creates_file(self, tmp_path):
        """Emit creates the events.jsonl file with a valid JSON line."""
        ev = emit(REGISTRY_UPDATED, "test-source")
        # The fixture routes to tmp_path; the file should now exist
        from organvm_engine.pulse.events import _events_path
        path = _events_path()
        assert path.is_file()
        line = path.read_text().strip()
        data = json.loads(line)
        assert data["event_type"] == REGISTRY_UPDATED
        assert data["source"] == "test-source"

    def test_emit_appends(self):
        """Three successive emits produce three lines in the file."""
        emit(REGISTRY_UPDATED, "s1")
        emit(GATE_CHANGED, "s2")
        emit(REPO_PROMOTED, "s3")
        from organvm_engine.pulse.events import _events_path
        lines = _events_path().read_text().strip().splitlines()
        assert len(lines) == 3

    def test_emit_returns_event(self):
        """Emit returns the Event object that was written."""
        ev = emit(MOOD_SHIFTED, "affective", {"mood": "THRIVING"})
        assert isinstance(ev, Event)
        assert ev.event_type == MOOD_SHIFTED
        assert ev.payload["mood"] == "THRIVING"


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

class TestReplay:
    def test_replay_all(self):
        """Replay with no filters returns all emitted events."""
        for i in range(3):
            emit(REGISTRY_UPDATED, f"s{i}")
        events = replay(limit=100)
        assert len(events) == 3

    def test_replay_by_type(self):
        """Replay filtered by event_type returns only matching events."""
        emit(REGISTRY_UPDATED, "s1")
        emit(GATE_CHANGED, "s2")
        emit(REGISTRY_UPDATED, "s3")
        events = replay(event_type=REGISTRY_UPDATED, limit=100)
        assert len(events) == 2
        assert all(e.event_type == REGISTRY_UPDATED for e in events)

    def test_replay_since(self):
        """Replay filtered by since timestamp excludes older events."""
        emit(REGISTRY_UPDATED, "old")
        # Capture a timestamp after the first event
        cutoff = Event(event_type="x", source="x").timestamp
        # Tiny sleep to ensure distinct timestamps
        time.sleep(0.01)
        emit(GATE_CHANGED, "new")
        events = replay(since=cutoff, limit=100)
        # The 'new' event's timestamp should be > cutoff
        assert len(events) >= 1
        assert all(e.event_type == GATE_CHANGED for e in events)

    def test_replay_limit(self):
        """Replay with limit=5 returns only the last 5 events."""
        for i in range(10):
            emit(REGISTRY_UPDATED, f"s{i}")
        events = replay(limit=5)
        assert len(events) == 5
        # Should be the last 5 (sources s5..s9)
        sources = [e.source for e in events]
        assert sources == [f"s{i}" for i in range(5, 10)]


# ---------------------------------------------------------------------------
# Recent
# ---------------------------------------------------------------------------

class TestRecent:
    def test_recent(self):
        """recent(3) returns the last 3 events."""
        for i in range(5):
            emit(REGISTRY_UPDATED, f"s{i}")
        events = recent(3)
        assert len(events) == 3
        assert events[-1].source == "s4"

    def test_recent_empty(self):
        """recent() with no file returns empty list."""
        events = recent()
        assert events == []


# ---------------------------------------------------------------------------
# Event counts
# ---------------------------------------------------------------------------

class TestEventCounts:
    def test_event_counts(self):
        """Counts are correct for a mix of event types."""
        emit(REGISTRY_UPDATED, "s1")
        emit(REGISTRY_UPDATED, "s2")
        emit(GATE_CHANGED, "s3")
        emit(REPO_PROMOTED, "s4")
        emit(REPO_PROMOTED, "s5")
        emit(REPO_PROMOTED, "s6")
        counts = event_counts()
        assert counts[REGISTRY_UPDATED] == 2
        assert counts[GATE_CHANGED] == 1
        assert counts[REPO_PROMOTED] == 3


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_all_event_types(self):
        """ALL_EVENT_TYPES contains exactly 10 entries."""
        assert len(ALL_EVENT_TYPES) == 10
        assert REGISTRY_UPDATED in ALL_EVENT_TYPES
        assert ORGANISM_COMPUTED in ALL_EVENT_TYPES
        assert PULSE_HEARTBEAT in ALL_EVENT_TYPES
