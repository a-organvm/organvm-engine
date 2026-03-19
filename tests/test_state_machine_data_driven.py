"""Tests for the data-driven state machine (SPEC-004).

Tests cover:
  - Loading transitions from governance-rules.json
  - Fallback to hardcoded transitions
  - execute_transition with EventSpine emission
  - Backward compatibility of the TRANSITIONS alias

All file operations use tmp_path — never writes to production paths.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from organvm_engine.events.spine import EventSpine, EventType
from organvm_engine.governance.state_machine import (
    FALLBACK_TRANSITIONS,
    TRANSITIONS,
    check_transition,
    execute_transition,
    get_valid_transitions,
    load_transitions_from_rules,
    reset_loaded_transitions,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset the module-level transition cache before each test."""
    reset_loaded_transitions()
    yield
    reset_loaded_transitions()


# ---------------------------------------------------------------------------
# Helper: write a minimal governance-rules.json to tmp_path
# ---------------------------------------------------------------------------

def _write_rules(
    tmp_path: Path,
    transitions: dict[str, list[str]] | None = None,
    *,
    states: list[str] | None = None,
) -> Path:
    """Write a governance-rules.json file and return its path."""
    if transitions is None:
        transitions = {
            "LOCAL": ["CANDIDATE", "ARCHIVED"],
            "CANDIDATE": ["PUBLIC_PROCESS", "ARCHIVED"],
            "PUBLIC_PROCESS": ["GRADUATED", "ARCHIVED"],
            "GRADUATED": ["ARCHIVED"],
            "ARCHIVED": [],
        }
    if states is None:
        states = list(transitions.keys())
    rules = {
        "version": "1.0",
        "state_machine": {
            "states": states,
            "transitions": transitions,
        },
    }
    path = tmp_path / "governance-rules.json"
    path.write_text(json.dumps(rules))
    return path


# ---------------------------------------------------------------------------
# load_transitions_from_rules
# ---------------------------------------------------------------------------

class TestLoadTransitionsFromRules:
    def test_loads_from_fixture(self):
        result = load_transitions_from_rules(FIXTURES / "governance-rules-test.json")
        assert "LOCAL" in result
        assert "CANDIDATE" in result["LOCAL"]

    def test_loads_custom_file(self, tmp_path):
        path = _write_rules(tmp_path, {
            "ALPHA": ["BETA"],
            "BETA": ["GAMMA"],
            "GAMMA": [],
        })
        result = load_transitions_from_rules(path)
        assert result == {"ALPHA": ["BETA"], "BETA": ["GAMMA"], "GAMMA": []}

    def test_returns_empty_for_missing_file(self, tmp_path):
        result = load_transitions_from_rules(tmp_path / "nonexistent.json")
        assert result == {}

    def test_returns_empty_for_malformed_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        result = load_transitions_from_rules(bad)
        assert result == {}

    def test_returns_empty_for_missing_state_machine_key(self, tmp_path):
        path = tmp_path / "rules.json"
        path.write_text(json.dumps({"version": "1.0"}))
        result = load_transitions_from_rules(path)
        assert result == {}

    def test_returns_empty_for_non_dict_transitions(self, tmp_path):
        path = tmp_path / "rules.json"
        path.write_text(json.dumps({
            "state_machine": {"transitions": "not a dict"},
        }))
        result = load_transitions_from_rules(path)
        assert result == {}

    def test_returns_empty_for_non_list_targets(self, tmp_path):
        path = tmp_path / "rules.json"
        path.write_text(json.dumps({
            "state_machine": {
                "transitions": {"LOCAL": "CANDIDATE"},
            },
        }))
        result = load_transitions_from_rules(path)
        assert result == {}

    def test_returns_empty_for_non_string_target_entries(self, tmp_path):
        path = tmp_path / "rules.json"
        path.write_text(json.dumps({
            "state_machine": {
                "transitions": {"LOCAL": [42]},
            },
        }))
        result = load_transitions_from_rules(path)
        assert result == {}


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_transitions_alias_equals_fallback(self):
        assert TRANSITIONS is FALLBACK_TRANSITIONS

    def test_fallback_has_all_states(self):
        expected = {"INCUBATOR", "LOCAL", "CANDIDATE", "PUBLIC_PROCESS", "GRADUATED", "ARCHIVED"}
        assert set(FALLBACK_TRANSITIONS.keys()) == expected

    def test_archived_is_terminal(self):
        assert FALLBACK_TRANSITIONS["ARCHIVED"] == []


# ---------------------------------------------------------------------------
# get_valid_transitions — data-driven
# ---------------------------------------------------------------------------

class TestGetValidTransitionsDataDriven:
    def test_uses_rules_file(self, tmp_path):
        path = _write_rules(tmp_path, {
            "ALPHA": ["BETA", "GAMMA"],
            "BETA": [],
            "GAMMA": [],
        })
        valid = get_valid_transitions("ALPHA", rules_path=path)
        assert valid == ["BETA", "GAMMA"]

    def test_unknown_state_returns_empty(self, tmp_path):
        path = _write_rules(tmp_path)
        valid = get_valid_transitions("BOGUS", rules_path=path)
        assert valid == []

    def test_fallback_when_file_missing(self, tmp_path):
        valid = get_valid_transitions("LOCAL", rules_path=tmp_path / "nope.json")
        assert "CANDIDATE" in valid


# ---------------------------------------------------------------------------
# check_transition — data-driven
# ---------------------------------------------------------------------------

class TestCheckTransitionDataDriven:
    def test_valid_transition_from_rules(self, tmp_path):
        path = _write_rules(tmp_path)
        ok, msg = check_transition("LOCAL", "CANDIDATE", rules_path=path)
        assert ok
        assert "LOCAL -> CANDIDATE" in msg

    def test_invalid_transition_from_rules(self, tmp_path):
        path = _write_rules(tmp_path)
        ok, msg = check_transition("LOCAL", "GRADUATED", rules_path=path)
        assert not ok
        assert "Cannot transition" in msg

    def test_unknown_state_from_rules(self, tmp_path):
        path = _write_rules(tmp_path)
        ok, msg = check_transition("BOGUS", "LOCAL", rules_path=path)
        assert not ok
        assert "Unknown state" in msg

    def test_terminal_state_from_rules(self, tmp_path):
        path = _write_rules(tmp_path)
        ok, msg = check_transition("ARCHIVED", "LOCAL", rules_path=path)
        assert not ok
        assert "terminal state" in msg

    def test_fallback_check_still_works(self):
        ok, msg = check_transition("LOCAL", "CANDIDATE")
        assert ok


# ---------------------------------------------------------------------------
# execute_transition — with EventSpine
# ---------------------------------------------------------------------------

class TestExecuteTransition:
    def test_valid_transition_emits_event(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "test-repo",
            "LOCAL",
            "CANDIDATE",
            rules_path=rules,
            actor="test-agent",
            spine_path=spine_path,
        )
        assert ok
        assert "LOCAL -> CANDIDATE" in msg

        # Verify event was emitted
        spine = EventSpine(path=spine_path)
        events = spine.query(event_type=EventType.PROMOTION)
        assert len(events) == 1
        evt = events[0]
        assert evt.entity_uid == "test-repo"
        assert evt.payload["previous_state"] == "LOCAL"
        assert evt.payload["new_state"] == "CANDIDATE"
        assert evt.source_spec == "SPEC-004"

    def test_invalid_transition_does_not_emit(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "test-repo",
            "LOCAL",
            "GRADUATED",
            rules_path=rules,
            spine_path=spine_path,
        )
        assert not ok
        # Spine file should not exist (no events written)
        assert not spine_path.exists()

    def test_actor_recorded_in_event(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        execute_transition(
            "repo-x",
            "LOCAL",
            "CANDIDATE",
            rules_path=rules,
            actor="agent:forge-7",
            spine_path=spine_path,
        )
        spine = EventSpine(path=spine_path)
        events = spine.query()
        assert events[0].actor == "agent:forge-7"

    def test_multiple_transitions_accumulate_events(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        execute_transition("r1", "LOCAL", "CANDIDATE", rules_path=rules, spine_path=spine_path)
        execute_transition(
            "r1", "CANDIDATE", "PUBLIC_PROCESS", rules_path=rules, spine_path=spine_path,
        )
        spine = EventSpine(path=spine_path)
        events = spine.query(entity_uid="r1")
        assert len(events) == 2
        assert events[0].payload["new_state"] == "CANDIDATE"
        assert events[1].payload["new_state"] == "PUBLIC_PROCESS"

    def test_uses_fallback_when_no_rules_path(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "repo-y",
            "LOCAL",
            "CANDIDATE",
            spine_path=spine_path,
        )
        assert ok

    def test_default_actor_is_cli(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        execute_transition(
            "repo-z", "LOCAL", "CANDIDATE",
            rules_path=rules, spine_path=spine_path,
        )
        spine = EventSpine(path=spine_path)
        events = spine.query()
        assert events[0].actor == "cli"


# ---------------------------------------------------------------------------
# Caching behavior
# ---------------------------------------------------------------------------

class TestTransitionCaching:
    def test_loaded_transitions_cached(self, tmp_path):
        path = _write_rules(tmp_path, {
            "A": ["B"],
            "B": [],
        })
        # First call loads
        ok1, _ = check_transition("A", "B", rules_path=path)
        assert ok1
        # Modify file on disk
        _write_rules(tmp_path, {
            "A": [],
            "B": [],
        })
        # Second call should use cached version (A -> B still valid)
        ok2, _ = check_transition("A", "B")
        assert ok2

    def test_reset_clears_cache(self, tmp_path):
        path = _write_rules(tmp_path, {
            "X": ["Y"],
            "Y": [],
        })
        check_transition("X", "Y", rules_path=path)
        reset_loaded_transitions()
        # After reset with no rules_path, falls back to FALLBACK_TRANSITIONS
        valid = get_valid_transitions("X")
        assert valid == []  # X not in fallback


# ---------------------------------------------------------------------------
# Original test_governance.py tests still pass (regression)
# ---------------------------------------------------------------------------

class TestStateMachineRegression:
    """These mirror the existing TestStateMachine in test_governance.py."""

    def test_local_to_candidate(self):
        ok, msg = check_transition("LOCAL", "CANDIDATE")
        assert ok

    def test_local_to_graduated_invalid(self):
        ok, msg = check_transition("LOCAL", "GRADUATED")
        assert not ok

    def test_archived_is_terminal(self):
        ok, msg = check_transition("ARCHIVED", "LOCAL")
        assert not ok

    def test_get_valid_transitions(self):
        valid = get_valid_transitions("CANDIDATE")
        assert "PUBLIC_PROCESS" in valid
        assert "LOCAL" in valid
        assert "ARCHIVED" in valid

    def test_unknown_state(self):
        ok, msg = check_transition("BOGUS", "LOCAL")
        assert not ok
