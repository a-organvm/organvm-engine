"""Tests for entity memory aggregation (G5).

Verifies the cross-store signal collector that aggregates all signals
about a named entity from pulse events, shared memory, ontologia,
continuity, and metrics.
"""

from __future__ import annotations

import json

import pytest

from organvm_engine.pulse.memory import (
    EntityMemory,
    _gather_insights,
    _gather_metrics,
    _gather_pulse_events,
    aggregate_entity_memory,
)


# ---------------------------------------------------------------------------
# EntityMemory dataclass
# ---------------------------------------------------------------------------


class TestEntityMemory:
    def test_empty_memory(self):
        mem = EntityMemory(entity="test")
        assert mem.total_signals == 0

    def test_total_signals(self):
        mem = EntityMemory(
            entity="test",
            pulse_event_count=5,
            insight_count=3,
            ontologia_event_count=2,
            name_history=[{"display_name": "test"}],
            recent_claims=[{"repo": "test"}],
            metrics_trend=[{"date": "2026-03-14"}],
        )
        assert mem.total_signals == 13  # 5 + 3 + 2 + 1 + 1 + 1

    def test_to_dict_structure(self):
        mem = EntityMemory(
            entity="test-repo",
            entity_uid="ent_repo_123",
            entity_type="repo",
            lifecycle_status="active",
        )
        d = mem.to_dict()
        assert d["entity"] == "test-repo"
        assert d["entity_uid"] == "ent_repo_123"
        assert d["entity_type"] == "repo"
        assert d["pulse"]["count"] == 0
        assert d["shared_memory"]["count"] == 0
        assert d["ontologia"]["lifecycle_status"] == "active"

    def test_to_dict_json_serializable(self):
        mem = EntityMemory(entity="test", pulse_events=[{"event_type": "test"}])
        d = mem.to_dict()
        json_str = json.dumps(d)
        assert "test" in json_str


# ---------------------------------------------------------------------------
# Pulse events gathering
# ---------------------------------------------------------------------------


class TestGatherPulseEvents:
    def test_matches_by_source(self, tmp_path, monkeypatch):
        """Events mentioning the entity in source are collected."""
        events_dir = tmp_path / "events"
        events_dir.mkdir()
        events_path = events_dir / "events.jsonl"
        events_path.write_text(
            json.dumps({
                "event_type": "registry.updated",
                "source": "test-repo",
                "payload": {},
                "timestamp": "2026-03-14T00:00:00Z",
            }) + "\n"
            + json.dumps({
                "event_type": "gate.changed",
                "source": "other-repo",
                "payload": {},
                "timestamp": "2026-03-14T00:00:01Z",
            }) + "\n",
        )

        monkeypatch.setattr(
            "organvm_engine.pulse.events._events_path",
            lambda: events_path,
        )

        mem = EntityMemory(entity="test-repo")
        _gather_pulse_events("test-repo", mem, limit=50)
        assert mem.pulse_event_count == 1
        assert mem.pulse_events[0]["event_type"] == "registry.updated"

    def test_matches_by_payload_repo(self, tmp_path, monkeypatch):
        events_dir = tmp_path / "events"
        events_dir.mkdir()
        events_path = events_dir / "events.jsonl"
        events_path.write_text(
            json.dumps({
                "event_type": "repo.promoted",
                "source": "governance",
                "payload": {"repo": "my-repo"},
                "timestamp": "2026-03-14T00:00:00Z",
            }) + "\n",
        )

        monkeypatch.setattr(
            "organvm_engine.pulse.events._events_path",
            lambda: events_path,
        )

        mem = EntityMemory(entity="my-repo")
        _gather_pulse_events("my-repo", mem, limit=50)
        assert mem.pulse_event_count == 1


# ---------------------------------------------------------------------------
# Shared memory gathering
# ---------------------------------------------------------------------------


class TestGatherInsights:
    def test_matches_by_repo(self, tmp_path, monkeypatch):
        mem_path = tmp_path / "shared-memory.jsonl"
        mem_path.write_text(
            json.dumps({
                "agent": "claude",
                "category": "finding",
                "content": "Found a bug in test-repo",
                "tags": [],
                "organ": "",
                "repo": "test-repo",
                "timestamp": "2026-03-14T00:00:00Z",
            }) + "\n"
            + json.dumps({
                "agent": "gemini",
                "category": "decision",
                "content": "Unrelated insight",
                "tags": [],
                "organ": "",
                "repo": "other-repo",
                "timestamp": "2026-03-14T00:00:01Z",
            }) + "\n",
        )

        monkeypatch.setattr(
            "organvm_engine.pulse.shared_memory._memory_path",
            lambda: mem_path,
        )

        mem = EntityMemory(entity="test-repo")
        _gather_insights("test-repo", mem, limit=50)
        assert mem.insight_count == 1
        assert mem.insights[0]["category"] == "finding"

    def test_matches_by_tag(self, tmp_path, monkeypatch):
        mem_path = tmp_path / "shared-memory.jsonl"
        mem_path.write_text(
            json.dumps({
                "agent": "claude",
                "category": "pattern",
                "content": "Observed pattern",
                "tags": ["my-entity"],
                "organ": "",
                "repo": "",
                "timestamp": "2026-03-14T00:00:00Z",
            }) + "\n",
        )

        monkeypatch.setattr(
            "organvm_engine.pulse.shared_memory._memory_path",
            lambda: mem_path,
        )

        mem = EntityMemory(entity="my-entity")
        _gather_insights("my-entity", mem, limit=50)
        assert mem.insight_count == 1


# ---------------------------------------------------------------------------
# Metrics gathering
# ---------------------------------------------------------------------------


class TestGatherMetrics:
    def test_empty_soak_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.metrics.timeseries.load_snapshots",
            lambda soak_dir=None: [],
        )
        mem = EntityMemory(entity="test")
        _gather_metrics("test", mem)
        assert mem.metrics_trend == []

    def test_limits_to_14_days(self, monkeypatch):
        fake_snapshots = [
            {"date": f"2026-03-{i:02d}", "ci": {"total_checked": 10, "passing": 9, "failing": 1}}
            for i in range(1, 21)  # 20 snapshots
        ]
        monkeypatch.setattr(
            "organvm_engine.metrics.timeseries.load_snapshots",
            lambda soak_dir=None: fake_snapshots,
        )
        monkeypatch.setattr(
            "organvm_engine.metrics.timeseries.ci_trend",
            lambda snaps: [{"date": s["date"], "passing": 9, "failing": 1, "total": 10, "rate": 0.9} for s in snaps],
        )

        mem = EntityMemory(entity="test")
        _gather_metrics("test", mem)
        assert len(mem.metrics_trend) == 14  # last 14 only


# ---------------------------------------------------------------------------
# Full aggregation
# ---------------------------------------------------------------------------


class TestAggregateEntityMemory:
    def test_returns_entity_memory(self):
        mem = aggregate_entity_memory(
            "nonexistent-repo",
            include_pulse=False,
            include_insights=False,
            include_ontologia=False,
            include_continuity=False,
            include_metrics=False,
        )
        assert isinstance(mem, EntityMemory)
        assert mem.entity == "nonexistent-repo"
        assert mem.total_signals == 0

    def test_selective_sources(self):
        mem = aggregate_entity_memory(
            "test",
            include_pulse=True,
            include_insights=False,
            include_ontologia=False,
            include_continuity=False,
            include_metrics=False,
        )
        assert isinstance(mem, EntityMemory)

    def test_to_dict_json_roundtrip(self):
        mem = aggregate_entity_memory(
            "test",
            include_pulse=False,
            include_insights=False,
            include_ontologia=False,
            include_continuity=False,
            include_metrics=False,
        )
        d = mem.to_dict()
        json_str = json.dumps(d, indent=2)
        restored = json.loads(json_str)
        assert restored["entity"] == "test"
        assert restored["total_signals"] == 0
