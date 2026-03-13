"""Tests for organvm_engine.pulse.ammoi — AMMOI computation and history."""

from __future__ import annotations

import json

import pytest

from organvm_engine.pulse.ammoi import (
    AMMOI,
    EntityDensity,
    OrganDensity,
    _build_compressed_text,
    _compute_temporal_deltas,
)


# ---------------------------------------------------------------------------
# Dataclass basics
# ---------------------------------------------------------------------------


class TestEntityDensity:
    def test_defaults(self):
        ed = EntityDensity(entity_id="ent_1", entity_name="test", organ="ORGAN-I")
        assert ed.density == 0.0
        assert ed.local_edges == 0

    def test_to_dict(self):
        ed = EntityDensity(
            entity_id="ent_1", entity_name="test", organ="ORGAN-I", density=0.5,
        )
        d = ed.to_dict()
        assert d["entity_id"] == "ent_1"
        assert d["density"] == 0.5


class TestOrganDensity:
    def test_defaults(self):
        od = OrganDensity(organ_id="ORGAN-I", organ_name="Theory")
        assert od.repo_count == 0
        assert od.density == 0.0

    def test_to_dict(self):
        od = OrganDensity(
            organ_id="META", organ_name="Meta", repo_count=8, density=0.65,
        )
        d = od.to_dict()
        assert d["organ_id"] == "META"
        assert d["repo_count"] == 8


class TestAMMOI:
    def test_defaults(self):
        a = AMMOI()
        assert a.system_density == 0.0
        assert a.total_entities == 0
        assert a.organs == {}
        assert a.pulse_interval == 900

    def test_to_dict_roundtrip(self):
        """AMMOI.to_dict() → from_dict() preserves all fields."""
        a = AMMOI(
            timestamp="2026-03-13T10:00:00Z",
            system_density=0.42,
            total_entities=112,
            active_edges=87,
            tension_count=3,
            event_frequency_24h=42,
            density_delta_24h=0.015,
            density_delta_7d=0.03,
            density_delta_30d=0.08,
            organs={
                "ORGAN-I": OrganDensity(
                    organ_id="ORGAN-I", organ_name="Theory",
                    repo_count=20, density=0.38,
                ),
            },
            pulse_count=96,
            compressed_text="test",
        )
        d = a.to_dict()
        restored = AMMOI.from_dict(d)
        assert restored.system_density == 0.42
        assert restored.total_entities == 112
        assert restored.active_edges == 87
        assert "ORGAN-I" in restored.organs
        assert restored.organs["ORGAN-I"].repo_count == 20
        assert restored.pulse_count == 96
        assert restored.compressed_text == "test"

    def test_from_dict_missing_fields(self):
        """from_dict uses defaults for missing keys."""
        a = AMMOI.from_dict({"timestamp": "2026-01-01T00:00:00Z"})
        assert a.system_density == 0.0
        assert a.organs == {}
        assert a.pulse_interval == 900

    def test_to_dict_organ_serialization(self):
        """Organ values are plain dicts, not OrganDensity objects."""
        a = AMMOI(
            organs={
                "X": OrganDensity(organ_id="X", organ_name="Test"),
            },
        )
        d = a.to_dict()
        assert isinstance(d["organs"]["X"], dict)
        assert d["organs"]["X"]["organ_id"] == "X"


# ---------------------------------------------------------------------------
# History storage
# ---------------------------------------------------------------------------


class TestHistory:
    @pytest.fixture(autouse=True)
    def _isolated_history(self, tmp_path, monkeypatch):
        self.history_file = tmp_path / "ammoi-history.jsonl"
        monkeypatch.setattr(
            "organvm_engine.pulse.ammoi._history_path",
            lambda: self.history_file,
        )

    def test_append_and_read(self):
        from organvm_engine.pulse.ammoi import _append_history, _read_history

        a = AMMOI(timestamp="2026-03-13T10:00:00Z", system_density=0.5)
        _append_history(a)
        snapshots = _read_history()
        assert len(snapshots) == 1
        assert snapshots[0].system_density == 0.5

    def test_append_multiple(self):
        from organvm_engine.pulse.ammoi import _append_history, _read_history

        for i in range(5):
            _append_history(AMMOI(
                timestamp=f"2026-03-13T{i:02d}:00:00Z",
                system_density=i * 0.1,
            ))
        snapshots = _read_history()
        assert len(snapshots) == 5

    def test_read_limit(self):
        from organvm_engine.pulse.ammoi import _append_history, _read_history

        for i in range(10):
            _append_history(AMMOI(
                timestamp=f"2026-03-13T{i:02d}:00:00Z",
                system_density=i * 0.1,
            ))
        snapshots = _read_history(limit=3)
        assert len(snapshots) == 3
        # Should be the last 3
        assert snapshots[0].system_density == pytest.approx(0.7)

    def test_read_empty(self):
        from organvm_engine.pulse.ammoi import _read_history

        snapshots = _read_history()
        assert snapshots == []

    def test_count_history(self):
        from organvm_engine.pulse.ammoi import _append_history, _count_history

        assert _count_history() == 0
        for i in range(3):
            _append_history(AMMOI(timestamp=f"2026-03-13T{i:02d}:00:00Z"))
        assert _count_history() == 3

    def test_malformed_lines_skipped(self):
        from organvm_engine.pulse.ammoi import _read_history

        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        valid = json.dumps({"timestamp": "2026-03-13T10:00:00Z", "system_density": 0.5})
        self.history_file.write_text(f"not json\n{valid}\nalso bad\n")
        snapshots = _read_history()
        assert len(snapshots) == 1
        assert snapshots[0].system_density == 0.5


# ---------------------------------------------------------------------------
# Temporal deltas
# ---------------------------------------------------------------------------


class TestTemporalDeltas:
    def test_empty_history(self):
        d24, d7, d30 = _compute_temporal_deltas(0.5, [])
        assert d24 == 0.0
        assert d7 == 0.0
        assert d30 == 0.0

    def test_with_matching_snapshot(self):
        """When history has a snapshot close to 24h ago, delta is computed."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        snap_24h = AMMOI(
            timestamp=(now - timedelta(hours=24)).isoformat(),
            system_density=0.3,
        )
        d24, d7, d30 = _compute_temporal_deltas(0.5, [snap_24h])
        assert d24 == pytest.approx(0.2)
        # 7d and 30d have no matching snapshots → 0
        assert d7 == 0.0
        assert d30 == 0.0


# ---------------------------------------------------------------------------
# Compressed text
# ---------------------------------------------------------------------------


class TestCompressedText:
    def test_basic_output(self):
        a = AMMOI(
            system_density=0.42,
            active_edges=87,
            tension_count=3,
            event_frequency_24h=42,
            organs={
                "ORGAN-I": OrganDensity(
                    organ_id="ORGAN-I", organ_name="Theory", density=0.38,
                ),
            },
        )
        text = _build_compressed_text(a)
        assert "AMMOI:42%" in text
        assert "E:87" in text
        assert "T:3" in text
        assert "ORGAN-I:38%" in text

    def test_includes_delta_when_nonzero(self):
        a = AMMOI(
            system_density=0.5,
            density_delta_24h=0.02,
        )
        text = _build_compressed_text(a)
        assert "d24h:+2.0%" in text

    def test_no_delta_when_zero(self):
        a = AMMOI(system_density=0.5, density_delta_24h=0.0)
        text = _build_compressed_text(a)
        assert "d24h" not in text
