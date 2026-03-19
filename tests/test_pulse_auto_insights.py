"""Tests for auto-insight recording in the pulse cycle (Stream 5)."""

from __future__ import annotations

import pytest

from organvm_engine.pulse.ammoi import AMMOI
from organvm_engine.pulse.rhythm import _record_pulse_insights


@pytest.fixture(autouse=True)
def _isolated_memory(tmp_path, monkeypatch):
    """Route shared memory to temp directory."""
    memory_file = tmp_path / "shared-memory.jsonl"
    monkeypatch.setattr(
        "organvm_engine.pulse.shared_memory._memory_path",
        lambda: memory_file,
    )
    return memory_file


class TestRecordPulseInsights:
    def test_trend_shift_records_insight(self, _isolated_memory):
        ammoi = AMMOI(
            system_density=0.5,
            temporal={"dominant_trend": "rising", "total_momentum": 0.05, "metrics": []},
        )
        count = _record_pulse_insights(ammoi, None, None)
        assert count >= 1
        content = _isolated_memory.read_text()
        assert "pulse-daemon" in content
        assert "rising" in content

    def test_stable_trend_no_insight(self, _isolated_memory):
        ammoi = AMMOI(
            system_density=0.5,
            temporal={"dominant_trend": "stable", "total_momentum": 0.0, "metrics": []},
        )
        count = _record_pulse_insights(ammoi, None, None)
        assert count == 0

    def test_no_temporal_no_trend_insight(self, _isolated_memory):
        ammoi = AMMOI(system_density=0.5)
        count = _record_pulse_insights(ammoi, None, None)
        assert count == 0

    def test_tension_increase_records_warning(self, _isolated_memory):
        prev = AMMOI(tension_count=3)
        curr = AMMOI(tension_count=5)
        count = _record_pulse_insights(curr, prev, None)
        assert count >= 1
        content = _isolated_memory.read_text()
        assert "increased" in content

    def test_tension_decrease_records_finding(self, _isolated_memory):
        prev = AMMOI(tension_count=5)
        curr = AMMOI(tension_count=2)
        count = _record_pulse_insights(curr, prev, None)
        assert count >= 1
        content = _isolated_memory.read_text()
        assert "decreased" in content

    def test_no_tension_change_no_insight(self, _isolated_memory):
        prev = AMMOI(tension_count=3)
        curr = AMMOI(tension_count=3)
        count = _record_pulse_insights(curr, prev, None)
        assert count == 0

    def test_heartbeat_diff_significant_change(self, _isolated_memory):
        ammoi = AMMOI(system_density=0.5)
        heartbeat_diff = {"sys_pct_delta": 5}
        count = _record_pulse_insights(ammoi, None, heartbeat_diff)
        assert count >= 1
        content = _isolated_memory.read_text()
        assert "improved" in content

    def test_heartbeat_diff_small_change_ignored(self, _isolated_memory):
        ammoi = AMMOI(system_density=0.5)
        heartbeat_diff = {"sys_pct_delta": 1}
        count = _record_pulse_insights(ammoi, None, heartbeat_diff)
        assert count == 0

    def test_agent_is_pulse_daemon(self, _isolated_memory):
        ammoi = AMMOI(
            system_density=0.5,
            temporal={"dominant_trend": "accelerating", "total_momentum": 0.1, "metrics": []},
        )
        _record_pulse_insights(ammoi, None, None)
        content = _isolated_memory.read_text()
        assert "pulse-daemon" in content

    def test_multiple_insights_in_one_pulse(self, _isolated_memory):
        prev = AMMOI(tension_count=3)
        curr = AMMOI(
            tension_count=5,
            temporal={"dominant_trend": "rising", "total_momentum": 0.05, "metrics": []},
        )
        heartbeat_diff = {"sys_pct_delta": -3}
        count = _record_pulse_insights(curr, prev, heartbeat_diff)
        assert count == 3  # trend + tension + heartbeat
