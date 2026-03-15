"""Tests for snapshot staleness advisory."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from organvm_engine.pulse.advisories import check_snapshot_staleness


class TestCheckSnapshotStaleness:
    def test_fresh_snapshot_returns_none(self, tmp_path):
        snapshot = tmp_path / "system-snapshot.json"
        now = datetime.now(timezone.utc).isoformat()
        snapshot.write_text(json.dumps({"generated_at": now}))
        result = check_snapshot_staleness(snapshot, max_age_hours=48)
        assert result is None

    def test_stale_snapshot_returns_advisory(self, tmp_path):
        snapshot = tmp_path / "system-snapshot.json"
        old = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        snapshot.write_text(json.dumps({"generated_at": old}))
        result = check_snapshot_staleness(snapshot, max_age_hours=48)
        assert result is not None
        assert result.severity == "warning"
        assert "stale" in result.description.lower()

    def test_missing_file_returns_advisory(self, tmp_path):
        snapshot = tmp_path / "nonexistent.json"
        result = check_snapshot_staleness(snapshot, max_age_hours=48)
        assert result is not None
        assert "not found" in result.description.lower()

    def test_malformed_json_returns_advisory(self, tmp_path):
        snapshot = tmp_path / "system-snapshot.json"
        snapshot.write_text("not json")
        result = check_snapshot_staleness(snapshot, max_age_hours=48)
        assert result is not None
        assert "malformed" in result.description.lower()

    def test_missing_generated_at_returns_advisory(self, tmp_path):
        snapshot = tmp_path / "system-snapshot.json"
        snapshot.write_text(json.dumps({"other_key": "value"}))
        result = check_snapshot_staleness(snapshot, max_age_hours=48)
        assert result is not None

    def test_advisory_has_correct_policy_id(self, tmp_path):
        snapshot = tmp_path / "nonexistent.json"
        result = check_snapshot_staleness(snapshot)
        assert result.policy_id == "snapshot-staleness"

    def test_stale_evidence_contains_age(self, tmp_path):
        snapshot = tmp_path / "system-snapshot.json"
        old = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
        snapshot.write_text(json.dumps({"generated_at": old}))
        result = check_snapshot_staleness(snapshot, max_age_hours=48)
        assert result is not None
        assert "age_hours" in result.evidence
        assert result.evidence["age_hours"] >= 100
