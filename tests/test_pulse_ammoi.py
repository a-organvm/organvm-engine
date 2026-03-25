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
    extract_timeseries,
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
        assert d24 is None
        assert d7 is None
        assert d30 is None

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
        # 7d and 30d have no matching snapshots → None
        assert d7 is None
        assert d30 is None


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

    def test_delta_shown_when_zero(self):
        """Zero delta means stable — should render as 'd24h:0.0%', not be hidden."""
        a = AMMOI(system_density=0.5, density_delta_24h=0.0)
        text = _build_compressed_text(a)
        assert "d24h:0.0%" in text

    def test_no_delta_when_none(self):
        """None delta means no historical data — should not render."""
        a = AMMOI(system_density=0.5, density_delta_24h=None)
        text = _build_compressed_text(a)
        assert "d24h" not in text

    def test_includes_trend_when_nonstable(self):
        """Compressed text includes trend indicator when temporal data has non-stable trend."""
        a = AMMOI(
            system_density=0.5,
            temporal={"dominant_trend": "rising", "total_momentum": 0.05, "metrics": []},
        )
        text = _build_compressed_text(a)
        assert "trend:rising" in text

    def test_no_trend_when_stable(self):
        """No trend indicator when dominant trend is stable."""
        a = AMMOI(
            system_density=0.5,
            temporal={"dominant_trend": "stable", "total_momentum": 0.0, "metrics": []},
        )
        text = _build_compressed_text(a)
        assert "trend:" not in text

    def test_no_trend_without_temporal(self):
        """No trend indicator when temporal data is absent."""
        a = AMMOI(system_density=0.5)
        text = _build_compressed_text(a)
        assert "trend:" not in text


# ---------------------------------------------------------------------------
# New fields: temporal + flow (Streams 1+4)
# ---------------------------------------------------------------------------


class TestAMMOINewFields:
    def test_temporal_defaults_to_none(self):
        a = AMMOI()
        assert a.temporal is None

    def test_flow_defaults(self):
        a = AMMOI()
        assert a.flow_score == 0.0
        assert a.flow_active == 0
        assert a.flow_dormant == 0

    def test_to_dict_includes_temporal(self):
        a = AMMOI(
            temporal={"dominant_trend": "rising", "total_momentum": 0.1, "metrics": []},
        )
        d = a.to_dict()
        assert d["temporal"]["dominant_trend"] == "rising"

    def test_to_dict_temporal_none(self):
        a = AMMOI()
        d = a.to_dict()
        assert d["temporal"] is None

    def test_to_dict_includes_flow(self):
        a = AMMOI(flow_score=42.5, flow_active=10, flow_dormant=30)
        d = a.to_dict()
        assert d["flow_score"] == 42.5
        assert d["flow_active"] == 10
        assert d["flow_dormant"] == 30

    def test_from_dict_roundtrip_with_temporal(self):
        tp = {"dominant_trend": "accelerating", "total_momentum": 0.3, "metrics": []}
        a = AMMOI(temporal=tp, flow_score=15.0, flow_active=5, flow_dormant=20)
        restored = AMMOI.from_dict(a.to_dict())
        assert restored.temporal == tp
        assert restored.flow_score == 15.0
        assert restored.flow_active == 5
        assert restored.flow_dormant == 20

    def test_from_dict_missing_new_fields(self):
        """Existing AMMOI history without new fields loads cleanly."""
        a = AMMOI.from_dict({"timestamp": "2026-01-01T00:00:00Z"})
        assert a.temporal is None
        assert a.flow_score == 0.0
        assert a.flow_active == 0
        assert a.flow_dormant == 0


# ---------------------------------------------------------------------------
# extract_timeseries (Stream 1)
# ---------------------------------------------------------------------------


class TestExtractTimeseries:
    def test_empty_history(self):
        result = extract_timeseries([])
        assert result == {}

    def test_extracts_all_metric_keys(self):
        history = [
            AMMOI(system_density=0.4, active_edges=80, tension_count=3,
                  event_frequency_24h=10, cluster_count=2, orphan_count=5,
                  overcoupled_count=1, inference_score=0.8, flow_score=30.0),
            AMMOI(system_density=0.45, active_edges=85, tension_count=2,
                  event_frequency_24h=12, cluster_count=3, orphan_count=4,
                  overcoupled_count=1, inference_score=0.85, flow_score=35.0),
        ]
        result = extract_timeseries(history)
        expected_keys = {
            "system_density", "active_edges", "tension_count",
            "event_frequency_24h", "cluster_count", "orphan_count",
            "overcoupled_count", "inference_score", "flow_score",
        }
        assert set(result.keys()) == expected_keys

    def test_preserves_order(self):
        history = [
            AMMOI(system_density=0.1),
            AMMOI(system_density=0.2),
            AMMOI(system_density=0.3),
        ]
        result = extract_timeseries(history)
        assert result["system_density"] == [0.1, 0.2, 0.3]

    def test_single_snapshot(self):
        result = extract_timeseries([AMMOI(system_density=0.5)])
        assert result["system_density"] == [0.5]
