"""Tests for era tracker (INST-ERA)."""

import json

import pytest

from organvm_engine.governance.eras import (
    Era,
    EraTracker,
)

# ---------------------------------------------------------------------------
# Era dataclass
# ---------------------------------------------------------------------------


class TestEra:
    def test_active_when_no_end(self):
        era = Era(era_id="ERA-001", started_at="2026-01-01", ended_at="")
        assert era.is_active() is True

    def test_not_active_when_ended(self):
        era = Era(era_id="ERA-001", started_at="2026-01-01", ended_at="2026-06-01")
        assert era.is_active() is False

    def test_to_dict(self):
        era = Era(era_id="ERA-001", title="Test Era", started_at="2026-01-01")
        d = era.to_dict()
        assert d["era_id"] == "ERA-001"
        assert d["title"] == "Test Era"

    def test_from_dict(self):
        data = {
            "era_id": "ERA-X",
            "title": "X Era",
            "started_at": "2026-01-01",
            "ended_at": "",
            "deep_structure": {"key": "val"},
            "transition_reason": "Because",
        }
        era = Era.from_dict(data)
        assert era.era_id == "ERA-X"
        assert era.deep_structure["key"] == "val"

    def test_from_dict_defaults(self):
        era = Era.from_dict({})
        assert era.era_id == ""
        assert era.is_active() is True  # empty ended_at = active


# ---------------------------------------------------------------------------
# EraTracker (in-memory, no path)
# ---------------------------------------------------------------------------


class TestEraTrackerInMemory:
    def test_default_eras_loaded(self):
        tracker = EraTracker()
        eras = tracker.all_eras()
        assert len(eras) == 3
        assert eras[0].era_id == "ERA-001"
        assert eras[2].era_id == "ERA-003"

    def test_current_era_is_post_flood(self):
        tracker = EraTracker()
        current = tracker.current_era()
        assert current is not None
        assert current.era_id == "ERA-003"
        assert current.title == "Post-Flood"

    def test_not_in_transition(self):
        tracker = EraTracker()
        assert tracker.is_in_transition() is False

    def test_get_era_by_id(self):
        tracker = EraTracker()
        era = tracker.get_era("ERA-002")
        assert era is not None
        assert era.title == "The Flood"

    def test_get_era_missing(self):
        tracker = EraTracker()
        assert tracker.get_era("ERA-999") is None

    def test_record_transition(self):
        tracker = EraTracker()
        new = tracker.record_transition(
            new_era_id="ERA-004",
            new_title="Awakening",
            transition_reason="System reached omega",
            deep_structure={"character": "self-governance"},
        )
        assert new.era_id == "ERA-004"
        assert new.is_active() is True
        # Previous era should now be closed
        old = tracker.get_era("ERA-003")
        assert old is not None
        assert old.is_active() is False
        # New current
        assert tracker.current_era().era_id == "ERA-004"

    def test_duplicate_era_id_raises(self):
        tracker = EraTracker()
        with pytest.raises(ValueError, match="already exists"):
            tracker.record_transition(
                new_era_id="ERA-003",
                new_title="Duplicate",
                transition_reason="test",
            )


# ---------------------------------------------------------------------------
# EraTracker (file-backed)
# ---------------------------------------------------------------------------


class TestEraTrackerFileBacked:
    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "eras.json"
        tracker = EraTracker(path=path)
        # Should write defaults
        tracker.record_transition(
            new_era_id="ERA-004",
            new_title="Test Era",
            transition_reason="Testing",
        )
        assert path.is_file()

        # Reload from disk
        tracker2 = EraTracker(path=path)
        assert len(tracker2.all_eras()) == 4
        assert tracker2.current_era().era_id == "ERA-004"

    def test_load_from_existing_file(self, tmp_path):
        path = tmp_path / "eras.json"
        data = {
            "eras": [
                {
                    "era_id": "CUSTOM-1",
                    "title": "Custom",
                    "started_at": "2026-01-01",
                    "ended_at": "",
                    "deep_structure": {},
                    "transition_reason": "",
                },
            ],
        }
        path.write_text(json.dumps(data))

        tracker = EraTracker(path=path)
        assert len(tracker.all_eras()) == 1
        assert tracker.current_era().era_id == "CUSTOM-1"

    def test_empty_file_uses_defaults(self, tmp_path):
        path = tmp_path / "eras.json"
        # Don't create file — should use defaults
        tracker = EraTracker(path=path)
        assert len(tracker.all_eras()) == 3
