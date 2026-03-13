"""Tests for organvm_engine.pulse.emitter — unified event bridge."""

from __future__ import annotations

import json

import pytest

from organvm_engine.pulse.emitter import _resolve_entity_uid, emit_engine_event
from organvm_engine.pulse.types import (
    ALL_ENGINE_EVENT_TYPES,
    AUDIT_COMPLETED,
    PROMOTION_CHANGED,
    PULSE_HEARTBEAT,
    REGISTRY_UPDATED,
)


@pytest.fixture(autouse=True)
def _isolated_events(tmp_path, monkeypatch):
    """Route engine event log to temp directory."""
    events_file = tmp_path / "events.jsonl"
    monkeypatch.setattr(
        "organvm_engine.pulse.events._events_path",
        lambda: events_file,
    )
    return events_file


@pytest.fixture(autouse=True)
def _disable_ontologia(monkeypatch):
    """Prevent ontologia imports to isolate emitter tests.

    The emitter gracefully handles ImportError, so we block ontologia
    to test the engine-only path without needing a running store.
    """
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name.startswith("ontologia"):
            raise ImportError(f"blocked for test: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------


class TestEventTypeConstants:
    def test_all_engine_event_types_count(self):
        """ALL_ENGINE_EVENT_TYPES contains exactly 20 entries."""
        assert len(ALL_ENGINE_EVENT_TYPES) == 20

    def test_no_duplicates(self):
        """No duplicate event type strings."""
        assert len(ALL_ENGINE_EVENT_TYPES) == len(set(ALL_ENGINE_EVENT_TYPES))

    def test_naming_convention(self):
        """All event types follow domain.action_name pattern."""
        for et in ALL_ENGINE_EVENT_TYPES:
            parts = et.split(".")
            assert len(parts) == 2, f"Bad format: {et}"
            assert parts[0], f"Empty domain in {et}"
            assert parts[1], f"Empty action in {et}"


# ---------------------------------------------------------------------------
# emit_engine_event
# ---------------------------------------------------------------------------


class TestEmitEngineEvent:
    def test_emit_writes_to_engine_log(self, _isolated_events):
        """Event appears in the engine JSONL log."""
        emit_engine_event(
            event_type=REGISTRY_UPDATED,
            source="test",
            payload={"field": "status"},
        )
        content = _isolated_events.read_text().strip()
        assert content, "events file should not be empty"
        data = json.loads(content)
        assert data["event_type"] == REGISTRY_UPDATED
        assert data["source"] == "test"
        assert data["payload"]["field"] == "status"

    def test_emit_with_subject_entity(self, _isolated_events):
        """Subject entity is included in the payload."""
        emit_engine_event(
            event_type=PROMOTION_CHANGED,
            source="governance",
            subject_entity="organvm-engine",
            payload={"new_state": "PUBLIC_PROCESS"},
        )
        data = json.loads(_isolated_events.read_text().strip())
        assert data["payload"]["subject_entity"] == "organvm-engine"
        assert data["payload"]["new_state"] == "PUBLIC_PROCESS"

    def test_emit_with_uid_skips_resolution(self, _isolated_events):
        """UIDs starting with 'ent_' are passed through without resolution."""
        uid = "ent_repo_01JARQ5XB3ABCDEFGHJKMNPQRS"
        emit_engine_event(
            event_type=AUDIT_COMPLETED,
            source="governance",
            subject_entity=uid,
        )
        data = json.loads(_isolated_events.read_text().strip())
        assert data["payload"]["subject_entity"] == uid

    def test_emit_no_payload(self, _isolated_events):
        """Emit works with no payload."""
        emit_engine_event(event_type=PULSE_HEARTBEAT, source="pulse")
        data = json.loads(_isolated_events.read_text().strip())
        assert data["event_type"] == PULSE_HEARTBEAT
        assert "subject_entity" not in data["payload"]

    def test_emit_never_raises(self, monkeypatch):
        """Emitter swallows all exceptions — never raises to caller."""
        monkeypatch.setattr(
            "organvm_engine.pulse.events.emit",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        # Should not raise
        emit_engine_event(event_type=REGISTRY_UPDATED, source="test")

    def test_emit_multiple_events(self, _isolated_events):
        """Multiple emit calls produce multiple lines."""
        for i in range(5):
            emit_engine_event(
                event_type=REGISTRY_UPDATED,
                source=f"s{i}",
            )
        lines = _isolated_events.read_text().strip().splitlines()
        assert len(lines) == 5


# ---------------------------------------------------------------------------
# Entity UID resolution
# ---------------------------------------------------------------------------


class TestResolveEntityUid:
    def test_returns_none_when_ontologia_unavailable(self):
        """Without ontologia, resolution returns None."""
        result = _resolve_entity_uid("organvm-engine")
        assert result is None

    def test_returns_none_for_empty_name(self):
        """Empty string returns None."""
        result = _resolve_entity_uid("")
        assert result is None
