"""Tests for organvm_engine.pulse.rhythm — pulse cycle orchestration."""

from __future__ import annotations

import json

import pytest

from organvm_engine.pulse.ammoi import AMMOI
from organvm_engine.pulse.rhythm import pulse_history, pulse_once


@pytest.fixture(autouse=True)
def _isolated_pulse(tmp_path, monkeypatch):
    """Route all pulse I/O to temp directory."""
    # Isolate AMMOI history
    history_file = tmp_path / "ammoi-history.jsonl"
    monkeypatch.setattr(
        "organvm_engine.pulse.ammoi._history_path",
        lambda: history_file,
    )

    # Isolate engine events
    events_file = tmp_path / "events.jsonl"
    monkeypatch.setattr(
        "organvm_engine.pulse.events._events_path",
        lambda: events_file,
    )

    return {"history": history_file, "events": events_file}


@pytest.fixture
def _mock_ammoi(monkeypatch):
    """Replace compute_ammoi with a deterministic stub."""
    fake = AMMOI(
        timestamp="2026-03-13T15:00:00Z",
        system_density=0.42,
        total_entities=112,
        active_edges=87,
    )
    monkeypatch.setattr(
        "organvm_engine.pulse.rhythm.compute_ammoi",
        lambda **kwargs: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# pulse_once
# ---------------------------------------------------------------------------


class TestPulseOnce:
    def test_returns_ammoi(self, _mock_ammoi):
        """pulse_once returns an AMMOI snapshot."""
        result = pulse_once(run_sensors=False)
        assert isinstance(result, AMMOI)
        assert result.system_density == 0.42

    def test_appends_to_history(self, _mock_ammoi, _isolated_pulse):
        """pulse_once writes one entry to AMMOI history."""
        pulse_once(run_sensors=False)
        content = _isolated_pulse["history"].read_text().strip()
        assert content, "history file should not be empty"
        lines = content.splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["system_density"] == 0.42

    def test_multiple_pulses_accumulate(self, _mock_ammoi, _isolated_pulse):
        """Multiple pulse_once calls append multiple history entries."""
        for _ in range(3):
            pulse_once(run_sensors=False)
        lines = _isolated_pulse["history"].read_text().strip().splitlines()
        assert len(lines) == 3

    def test_sensors_skipped_when_disabled(self, _mock_ammoi):
        """run_sensors=False skips sensor scanning."""
        # If scan_and_emit were called, it would fail (ontologia blocked by conftest).
        # This test passes because sensors are skipped.
        result = pulse_once(run_sensors=False)
        assert result is not None

    def test_sensor_import_failure_graceful(self, _mock_ammoi, monkeypatch):
        """When ontologia.sensing is not importable, pulse_once still works."""
        import builtins
        real_import = builtins.__import__

        def _block_sensing(name, *args, **kwargs):
            if "sensing" in name:
                raise ImportError("no sensing")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_sensing)
        result = pulse_once(run_sensors=True)
        assert isinstance(result, AMMOI)


# ---------------------------------------------------------------------------
# pulse_history
# ---------------------------------------------------------------------------


class TestPulseHistory:
    def test_empty_history(self):
        """Returns empty list when no snapshots exist."""
        result = pulse_history()
        assert result == []

    def test_returns_dicts(self, _isolated_pulse):
        """Returns list of plain dicts (not AMMOI objects)."""
        from organvm_engine.pulse.ammoi import _append_history

        _append_history(AMMOI(
            timestamp="2026-03-13T10:00:00Z",
            system_density=0.5,
        ))
        result = pulse_history()
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["system_density"] == 0.5

    def test_days_filter(self, _isolated_pulse):
        """days parameter filters old snapshots."""
        from organvm_engine.pulse.ammoi import _append_history

        # Add an old snapshot (well before the cutoff)
        _append_history(AMMOI(
            timestamp="2020-01-01T00:00:00Z",
            system_density=0.1,
        ))
        # And a recent one
        from datetime import datetime, timezone
        _append_history(AMMOI(
            timestamp=datetime.now(timezone.utc).isoformat(),
            system_density=0.5,
        ))
        result = pulse_history(days=1)
        assert len(result) == 1
        assert result[0]["system_density"] == 0.5
