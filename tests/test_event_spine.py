"""Tests for the constitutional event spine (INST-EVENT-SPINE).

All file operations use tmp_path — never writes to ~/.organvm/.
"""

from __future__ import annotations

import json
import time

from organvm_engine.events.spine import EventRecord, EventSpine, EventType


class TestEventType:
    """EventType enum completeness and string behavior."""

    def test_all_types_present(self):
        expected = {
            "PROMOTION",
            "DEPENDENCY_CHANGE",
            "SEED_UPDATE",
            "GOVERNANCE_AUDIT",
            "METRIC_UPDATE",
            "ENTITY_CREATED",
            "ENTITY_ARCHIVED",
            "CONTEXT_SYNC",
        }
        actual = {e.name for e in EventType}
        assert actual == expected

    def test_values_are_dotted_strings(self):
        for e in EventType:
            assert "." in e.value, f"{e.name} value should be dotted: {e.value}"

    def test_enum_is_str_subclass(self):
        assert isinstance(EventType.PROMOTION, str)
        assert EventType.PROMOTION == "governance.promotion"


class TestEventRecord:
    """EventRecord construction and serialization."""

    def test_defaults_populated(self):
        record = EventRecord()
        assert record.event_id  # UUID, non-empty
        assert record.timestamp  # ISO timestamp, non-empty
        assert record.payload == {}
        assert record.entity_uid == ""

    def test_explicit_fields(self):
        record = EventRecord(
            event_id="test-id",
            event_type="governance.promotion",
            timestamp="2026-01-01T00:00:00+00:00",
            entity_uid="ent_repo_abc",
            payload={"key": "value"},
            source_spec="SPEC-004",
            actor="cli",
        )
        assert record.event_id == "test-id"
        assert record.event_type == "governance.promotion"
        assert record.entity_uid == "ent_repo_abc"
        assert record.payload == {"key": "value"}
        assert record.source_spec == "SPEC-004"
        assert record.actor == "cli"

    def test_to_json_roundtrip(self):
        record = EventRecord(
            event_type="governance.promotion",
            entity_uid="ent_repo_xyz",
            payload={"from": "LOCAL", "to": "CANDIDATE"},
            source_spec="SPEC-004",
            actor="agent:forge",
        )
        raw = record.to_json()
        data = json.loads(raw)
        assert data["event_type"] == "governance.promotion"
        assert data["entity_uid"] == "ent_repo_xyz"
        assert data["payload"]["from"] == "LOCAL"
        assert data["source_spec"] == "SPEC-004"
        assert data["actor"] == "agent:forge"

    def test_from_dict(self):
        data = {
            "event_id": "uuid-123",
            "event_type": "entity.created",
            "timestamp": "2026-03-19T12:00:00+00:00",
            "entity_uid": "ent_organ_I",
            "payload": {"name": "test"},
            "source_spec": "EVT-003",
            "actor": "human",
        }
        record = EventRecord.from_dict(data)
        assert record.event_id == "uuid-123"
        assert record.event_type == "entity.created"
        assert record.entity_uid == "ent_organ_I"
        assert record.actor == "human"

    def test_from_dict_missing_fields_get_defaults(self):
        record = EventRecord.from_dict({})
        assert record.event_id  # should still generate a UUID
        assert record.event_type == ""
        assert record.payload == {}


class TestEventSpineEmit:
    """EventSpine.emit() — write path."""

    def test_emit_creates_file(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        spine.emit(
            event_type=EventType.PROMOTION,
            entity_uid="test-repo",
            payload={"from": "LOCAL", "to": "CANDIDATE"},
            source_spec="SPEC-004",
            actor="test",
        )
        assert spine.path.is_file()

    def test_emit_returns_record(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        record = spine.emit(
            event_type=EventType.ENTITY_CREATED,
            entity_uid="ent_repo_new",
            source_spec="EVT-003",
            actor="cli",
        )
        assert isinstance(record, EventRecord)
        assert record.event_type == "entity.created"
        assert record.entity_uid == "ent_repo_new"

    def test_emit_appends_not_overwrites(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        spine.emit(EventType.PROMOTION, "repo-a")
        spine.emit(EventType.PROMOTION, "repo-b")
        lines = spine.path.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_emit_creates_parent_dirs(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c" / "events.jsonl"
        spine = EventSpine(path=deep_path)
        spine.emit(EventType.CONTEXT_SYNC, "ent_repo_x")
        assert deep_path.is_file()

    def test_emit_with_string_event_type(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        record = spine.emit(
            event_type="custom.type",
            entity_uid="entity-1",
        )
        assert record.event_type == "custom.type"

    def test_emit_with_enum_event_type(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        record = spine.emit(
            event_type=EventType.GOVERNANCE_AUDIT,
            entity_uid="system",
        )
        assert record.event_type == "governance.audit"

    def test_each_event_gets_unique_id(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        r1 = spine.emit(EventType.PROMOTION, "a")
        r2 = spine.emit(EventType.PROMOTION, "b")
        assert r1.event_id != r2.event_id

    def test_empty_payload_defaults_to_dict(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        record = spine.emit(EventType.METRIC_UPDATE, "entity-1")
        assert record.payload == {}


class TestEventSpineQuery:
    """EventSpine.query() — read path."""

    def _populated_spine(self, tmp_path) -> EventSpine:
        """Create a spine with several events for query testing."""
        spine = EventSpine(path=tmp_path / "events.jsonl")
        spine.emit(EventType.PROMOTION, "repo-a", {"state": "LOCAL"})
        spine.emit(EventType.ENTITY_CREATED, "repo-b")
        spine.emit(EventType.PROMOTION, "repo-c", {"state": "CANDIDATE"})
        spine.emit(EventType.GOVERNANCE_AUDIT, "system")
        spine.emit(EventType.SEED_UPDATE, "repo-a")
        return spine

    def test_query_all(self, tmp_path):
        spine = self._populated_spine(tmp_path)
        results = spine.query()
        assert len(results) == 5

    def test_query_by_event_type_string(self, tmp_path):
        spine = self._populated_spine(tmp_path)
        results = spine.query(event_type="governance.promotion")
        assert len(results) == 2
        assert all(r.event_type == "governance.promotion" for r in results)

    def test_query_by_event_type_enum(self, tmp_path):
        spine = self._populated_spine(tmp_path)
        results = spine.query(event_type=EventType.PROMOTION)
        assert len(results) == 2

    def test_query_by_entity_uid(self, tmp_path):
        spine = self._populated_spine(tmp_path)
        results = spine.query(entity_uid="repo-a")
        assert len(results) == 2

    def test_query_combined_filters(self, tmp_path):
        spine = self._populated_spine(tmp_path)
        results = spine.query(
            event_type=EventType.PROMOTION,
            entity_uid="repo-a",
        )
        assert len(results) == 1
        assert results[0].entity_uid == "repo-a"
        assert results[0].event_type == "governance.promotion"

    def test_query_since_timestamp(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        spine.emit(EventType.PROMOTION, "old", payload={})
        # Read first event timestamp
        first_ts = spine.query()[0].timestamp
        # Small delay to ensure distinct timestamps
        time.sleep(0.01)
        spine.emit(EventType.PROMOTION, "new", payload={})
        results = spine.query(since=first_ts)
        assert len(results) == 1
        assert results[0].entity_uid == "new"

    def test_query_limit(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        for i in range(10):
            spine.emit(EventType.METRIC_UPDATE, f"entity-{i}")
        results = spine.query(limit=3)
        assert len(results) == 3
        # Should be the LAST 3 events
        assert results[-1].entity_uid == "entity-9"
        assert results[0].entity_uid == "entity-7"

    def test_query_empty_spine(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        results = spine.query()
        assert results == []

    def test_query_nonexistent_file(self, tmp_path):
        spine = EventSpine(path=tmp_path / "does-not-exist.jsonl")
        results = spine.query()
        assert results == []

    def test_query_skips_malformed_lines(self, tmp_path):
        path = tmp_path / "events.jsonl"
        spine = EventSpine(path=path)
        spine.emit(EventType.PROMOTION, "good-event")
        # Inject a malformed line
        with path.open("a") as f:
            f.write("not valid json\n")
        spine.emit(EventType.PROMOTION, "also-good")
        results = spine.query()
        assert len(results) == 2

    def test_query_no_match_returns_empty(self, tmp_path):
        spine = self._populated_spine(tmp_path)
        results = spine.query(event_type="nonexistent.type")
        assert results == []


class TestEventSpineSnapshot:
    """EventSpine.snapshot() — summary."""

    def test_snapshot_empty(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        snap = spine.snapshot()
        assert snap["event_count"] == 0
        assert snap["latest_timestamp"] is None

    def test_snapshot_with_events(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        spine.emit(EventType.PROMOTION, "repo-a")
        spine.emit(EventType.ENTITY_CREATED, "repo-b")
        snap = spine.snapshot()
        assert snap["event_count"] == 2
        assert snap["latest_timestamp"] is not None

    def test_snapshot_latest_timestamp_is_most_recent(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        r1 = spine.emit(EventType.PROMOTION, "first")
        time.sleep(0.01)
        r2 = spine.emit(EventType.PROMOTION, "second")
        snap = spine.snapshot()
        assert snap["latest_timestamp"] == r2.timestamp
        assert snap["latest_timestamp"] >= r1.timestamp

    def test_snapshot_nonexistent_file(self, tmp_path):
        spine = EventSpine(path=tmp_path / "nope.jsonl")
        snap = spine.snapshot()
        assert snap["event_count"] == 0


class TestEventSpinePath:
    """Path configuration."""

    def test_custom_path(self, tmp_path):
        custom = tmp_path / "custom" / "log.jsonl"
        spine = EventSpine(path=custom)
        assert spine.path == custom

    def test_string_path_converted(self, tmp_path):
        spine = EventSpine(path=str(tmp_path / "events.jsonl"))
        assert isinstance(spine.path, type(tmp_path / "events.jsonl"))
