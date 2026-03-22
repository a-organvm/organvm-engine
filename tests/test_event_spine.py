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
            # Constitutional
            "PROMOTION", "DEPENDENCY_CHANGE", "SEED_UPDATE",
            "GOVERNANCE_AUDIT", "METRIC_UPDATE",
            "ENTITY_CREATED", "ENTITY_ARCHIVED", "CONTEXT_SYNC",
            # Testament Protocol
            "TESTAMENT_GENESIS", "TESTAMENT_CHECKPOINT", "TESTAMENT_VERIFIED",
            # Governance (engine)
            "PROMOTION_CHANGED", "GATE_EVALUATED",
            "DEPENDENCY_VIOLATION", "AUDIT_COMPLETED",
            # Registry
            "REGISTRY_UPDATE", "REGISTRY_UPDATED", "REGISTRY_LOADED",
            # Coordination
            "AGENT_PUNCH_IN", "AGENT_PUNCH_OUT", "AGENT_TOOL_LOCK",
            "AGENT_PUNCHED_IN", "AGENT_PUNCHED_OUT", "CAPACITY_WARNING",
            # Metrics / Organism
            "ORGANISM_COMPUTED", "STALENESS_DETECTED",
            # Seed
            "SEED_EDGE_ADDED", "SEED_EDGE_REMOVED", "SEED_UNRESOLVED",
            # Context
            "CONTEXT_SYNCED", "CONTEXT_AMMOI_DISTRIBUTED",
            # Sensor
            "SENSOR_SCAN_COMPLETED", "SENSOR_CHANGE_DETECTED",
            # Pulse
            "PULSE_HEARTBEAT", "AMMOI_COMPUTED",
            "INFERENCE_COMPLETED", "ADVISORY_GENERATED",
            "HEARTBEAT_DIFF", "EDGES_SYNCED", "VARIABLES_SYNCED",
            # CI, Content, Ecosystem, Pitch, Git, Ontologia
            "CI_HEALTH", "CONTENT_PUBLISHED", "ECOSYSTEM_MUTATION",
            "PITCH_GENERATED", "GIT_SYNC", "ONTOLOGIA_VARIABLE",
            # Session, Density, Affective (pulse-origin)
            "SESSION_STARTED", "SESSION_ENDED",
            "DENSITY_COMPUTED", "MOOD_SHIFTED",
            # Self-referential (testament chain)
            "ARCHITECTURE_CHANGED", "SCORECARD_EXPANDED",
            "VOCABULARY_EXPANDED", "MODULE_ADDED", "SESSION_RECORDED",
            # Legacy pulse aliases
            "GATE_CHANGED", "REPO_PROMOTED", "SEED_CHANGED",
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


class TestSelfReferentialEventTypes:
    """Self-referential testament event types are registered and usable."""

    def test_architecture_changed_value(self):
        assert EventType.ARCHITECTURE_CHANGED == "architecture.changed"

    def test_scorecard_expanded_value(self):
        assert EventType.SCORECARD_EXPANDED == "scorecard.expanded"

    def test_vocabulary_expanded_value(self):
        assert EventType.VOCABULARY_EXPANDED == "vocabulary.expanded"

    def test_module_added_value(self):
        assert EventType.MODULE_ADDED == "module.added"

    def test_session_recorded_value(self):
        assert EventType.SESSION_RECORDED == "session.recorded"

    def test_self_referential_types_are_str(self):
        for etype in [
            EventType.ARCHITECTURE_CHANGED,
            EventType.SCORECARD_EXPANDED,
            EventType.VOCABULARY_EXPANDED,
            EventType.MODULE_ADDED,
            EventType.SESSION_RECORDED,
        ]:
            assert isinstance(etype, str)
            assert "." in etype

    def test_emit_self_referential_events(self, tmp_path):
        spine = EventSpine(path=tmp_path / "events.jsonl")
        for etype in [
            EventType.ARCHITECTURE_CHANGED,
            EventType.SCORECARD_EXPANDED,
            EventType.VOCABULARY_EXPANDED,
            EventType.MODULE_ADDED,
            EventType.SESSION_RECORDED,
        ]:
            record = spine.emit(etype, "organvm-engine", payload={"test": True})
            assert record.event_type == etype.value


class TestRecordSession:
    """Tests for cmd_testament_record_session with mock git output."""

    def _mock_git_diff(self, output: str, returncode: int = 0):
        """Create a mock for subprocess.run that returns fixed git diff output."""
        import subprocess
        from unittest.mock import MagicMock

        mock_result = MagicMock(spec=subprocess.CompletedProcess)
        mock_result.stdout = output
        mock_result.stderr = ""
        mock_result.returncode = returncode
        return mock_result

    def test_record_session_dry_run_new_module(self, tmp_path, monkeypatch):
        import argparse
        from unittest.mock import patch

        from organvm_engine.cli.testament import cmd_testament_record_session

        diff_output = (
            "A\tsrc/organvm_engine/newmod/__init__.py\n"
            "M\tsrc/organvm_engine/events/spine.py\n"
            "M\tsrc/organvm_engine/omega/scorecard.py\n"
        )
        mock_result = self._mock_git_diff(diff_output)

        args = argparse.Namespace(
            from_commit="abc123",
            to_commit="def456",
            write=False,
            spine_path=None,
        )

        with patch("subprocess.run", return_value=mock_result):
            rc = cmd_testament_record_session(args)

        assert rc == 0

    def test_record_session_write_emits_events(self, tmp_path, monkeypatch):
        import argparse
        from unittest.mock import patch

        from organvm_engine.cli.testament import cmd_testament_record_session

        diff_output = (
            "A\tsrc/organvm_engine/newmod/__init__.py\n"
            "M\tsrc/organvm_engine/events/spine.py\n"
            "M\tsrc/organvm_engine/omega/scorecard.py\n"
        )
        mock_result = self._mock_git_diff(diff_output)
        spine_path = str(tmp_path / "test-events.jsonl")

        args = argparse.Namespace(
            from_commit="abc123",
            to_commit="def456",
            write=True,
            spine_path=spine_path,
        )

        with patch("subprocess.run", return_value=mock_result):
            rc = cmd_testament_record_session(args)

        assert rc == 0

        # Verify events were written
        spine = EventSpine(path=spine_path)
        records = spine.query(limit=100)
        # Expected: MODULE_ADDED + VOCABULARY_EXPANDED + SCORECARD_EXPANDED
        #           + ARCHITECTURE_CHANGED + SESSION_RECORDED = 5
        assert len(records) == 5

        types_emitted = {r.event_type for r in records}
        assert "module.added" in types_emitted
        assert "vocabulary.expanded" in types_emitted
        assert "scorecard.expanded" in types_emitted
        assert "architecture.changed" in types_emitted
        assert "session.recorded" in types_emitted

    def test_record_session_no_changes(self, tmp_path, monkeypatch):
        import argparse
        from unittest.mock import patch

        from organvm_engine.cli.testament import cmd_testament_record_session

        mock_result = self._mock_git_diff("")

        args = argparse.Namespace(
            from_commit="abc123",
            to_commit="abc123",
            write=True,
            spine_path=str(tmp_path / "events.jsonl"),
        )

        with patch("subprocess.run", return_value=mock_result):
            rc = cmd_testament_record_session(args)

        assert rc == 0

    def test_record_session_git_failure(self, tmp_path, monkeypatch):
        import argparse
        import subprocess
        from unittest.mock import patch

        from organvm_engine.cli.testament import cmd_testament_record_session

        args = argparse.Namespace(
            from_commit="bad",
            to_commit="bad",
            write=False,
            spine_path=None,
        )

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(128, "git"),
        ):
            rc = cmd_testament_record_session(args)

        assert rc == 1

    def test_record_session_only_regular_files(self, tmp_path, monkeypatch):
        """Changes to non-special files emit only ARCHITECTURE_CHANGED + SESSION_RECORDED."""
        import argparse
        from unittest.mock import patch

        from organvm_engine.cli.testament import cmd_testament_record_session

        diff_output = "M\tsrc/organvm_engine/registry/loader.py\n"
        mock_result = self._mock_git_diff(diff_output)
        spine_path = str(tmp_path / "events.jsonl")

        args = argparse.Namespace(
            from_commit="aaa",
            to_commit="bbb",
            write=True,
            spine_path=spine_path,
        )

        with patch("subprocess.run", return_value=mock_result):
            rc = cmd_testament_record_session(args)

        assert rc == 0
        spine = EventSpine(path=spine_path)
        records = spine.query(limit=100)
        assert len(records) == 2
        types_emitted = {r.event_type for r in records}
        assert "architecture.changed" in types_emitted
        assert "session.recorded" in types_emitted
