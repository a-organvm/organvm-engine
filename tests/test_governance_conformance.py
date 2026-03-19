"""Tests for governance.conformance — SPEC-004, van der Aalst conformance checking."""

import pytest

from organvm_engine.governance.conformance import (
    ConformanceResult,
    TraceEntry,
    check_trace_conformance,
    detect_skipped_states,
    detect_unauthorized_transitions,
    extract_promotion_trace,
)
from organvm_engine.governance.state_machine import FALLBACK_TRANSITIONS


# ---------------------------------------------------------------------------
# TraceEntry
# ---------------------------------------------------------------------------

class TestTraceEntry:
    def test_create_basic(self):
        entry = TraceEntry(
            entity_uid="org/repo",
            from_state="LOCAL",
            to_state="CANDIDATE",
        )
        assert entry.entity_uid == "org/repo"
        assert entry.from_state == "LOCAL"
        assert entry.to_state == "CANDIDATE"
        assert entry.timestamp == ""

    def test_create_with_timestamp(self):
        entry = TraceEntry(
            entity_uid="org/repo",
            from_state="LOCAL",
            to_state="CANDIDATE",
            timestamp="2026-03-15T12:00:00Z",
        )
        assert entry.timestamp == "2026-03-15T12:00:00Z"

    def test_frozen(self):
        entry = TraceEntry(entity_uid="x", from_state="LOCAL", to_state="CANDIDATE")
        with pytest.raises(AttributeError):
            entry.from_state = "GRADUATED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConformanceResult
# ---------------------------------------------------------------------------

class TestConformanceResult:
    def test_default_values(self):
        result = ConformanceResult()
        assert result.fitness == 1.0
        assert result.violations == []
        assert result.skipped_states == []
        assert result.unauthorized_transitions == []
        assert result.total_transitions == 0

    def test_summary_no_violations(self):
        result = ConformanceResult(total_transitions=5)
        summary = result.summary()
        assert "fitness=1.000" in summary
        assert "5 transitions" in summary
        assert "No violations" in summary

    def test_summary_with_violations(self):
        result = ConformanceResult(
            fitness=0.5,
            violations=["bad transition"],
            skipped_states=[{
                "entity_uid": "org/repo",
                "from_state": "LOCAL",
                "to_state": "GRADUATED",
            }],
            total_transitions=2,
        )
        summary = result.summary()
        assert "Skipped states: 1" in summary


# ---------------------------------------------------------------------------
# extract_promotion_trace
# ---------------------------------------------------------------------------

class TestExtractPromotionTrace:
    def test_empty_registry(self):
        trace = extract_promotion_trace({"organs": {}})
        assert trace == []

    def test_synthetic_trace_from_status(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "repo-a",
                            "org": "organvm-i-theoria",
                            "promotion_status": "CANDIDATE",
                        },
                    ],
                },
            },
        }
        trace = extract_promotion_trace(registry)
        assert len(trace) == 1
        assert trace[0].entity_uid == "organvm-i-theoria/repo-a"
        assert trace[0].from_state == "LOCAL"
        assert trace[0].to_state == "CANDIDATE"

    def test_local_status_no_trace(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "repo-a",
                            "org": "organvm-i-theoria",
                            "promotion_status": "LOCAL",
                        },
                    ],
                },
            },
        }
        trace = extract_promotion_trace(registry)
        assert trace == []

    def test_explicit_history(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "repo-a",
                            "org": "organvm-i-theoria",
                            "promotion_history": [
                                {
                                    "from_state": "LOCAL",
                                    "to_state": "CANDIDATE",
                                    "timestamp": "2026-01-01",
                                },
                                {
                                    "from_state": "CANDIDATE",
                                    "to_state": "PUBLIC_PROCESS",
                                    "timestamp": "2026-02-01",
                                },
                            ],
                        },
                    ],
                },
            },
        }
        trace = extract_promotion_trace(registry)
        assert len(trace) == 2
        assert trace[0].from_state == "LOCAL"
        assert trace[1].from_state == "CANDIDATE"

    def test_missing_org_field(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "repo-x", "promotion_status": "CANDIDATE"},
                    ],
                },
            },
        }
        trace = extract_promotion_trace(registry)
        assert len(trace) == 1
        assert trace[0].entity_uid == "repo-x"

    def test_multiple_organs(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "a",
                            "org": "org-i",
                            "promotion_status": "CANDIDATE",
                        },
                    ],
                },
                "ORGAN-II": {
                    "repositories": [
                        {
                            "name": "b",
                            "org": "org-ii",
                            "promotion_status": "PUBLIC_PROCESS",
                        },
                    ],
                },
            },
        }
        trace = extract_promotion_trace(registry)
        assert len(trace) == 2

    def test_no_promotion_status_no_trace(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "repo-x", "org": "org-i"},
                    ],
                },
            },
        }
        trace = extract_promotion_trace(registry)
        assert trace == []

    def test_history_overrides_status(self):
        """When promotion_history is present, status-based synthetic trace is skipped."""
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "repo-a",
                            "org": "org-i",
                            "promotion_status": "GRADUATED",
                            "promotion_history": [
                                {"from_state": "LOCAL", "to_state": "CANDIDATE"},
                            ],
                        },
                    ],
                },
            },
        }
        trace = extract_promotion_trace(registry)
        assert len(trace) == 1
        assert trace[0].to_state == "CANDIDATE"


# ---------------------------------------------------------------------------
# detect_skipped_states
# ---------------------------------------------------------------------------

class TestDetectSkippedStates:
    def test_no_skips(self):
        trace = [
            TraceEntry("r", "LOCAL", "CANDIDATE"),
            TraceEntry("r", "CANDIDATE", "PUBLIC_PROCESS"),
        ]
        skipped = detect_skipped_states(trace)
        assert skipped == []

    def test_skip_candidate(self):
        trace = [
            TraceEntry("org/repo", "LOCAL", "PUBLIC_PROCESS"),
        ]
        skipped = detect_skipped_states(trace)
        assert len(skipped) == 1
        assert "CANDIDATE" in skipped[0]["skipped"]

    def test_skip_multiple_states(self):
        trace = [
            TraceEntry("org/repo", "LOCAL", "GRADUATED"),
        ]
        skipped = detect_skipped_states(trace)
        assert len(skipped) == 1
        assert set(skipped[0]["skipped"]) == {"CANDIDATE", "PUBLIC_PROCESS"}

    def test_backward_transition_not_a_skip(self):
        trace = [
            TraceEntry("org/repo", "CANDIDATE", "LOCAL"),
        ]
        skipped = detect_skipped_states(trace)
        assert skipped == []

    def test_unknown_state_ignored(self):
        trace = [
            TraceEntry("org/repo", "UNKNOWN", "GRADUATED"),
        ]
        skipped = detect_skipped_states(trace)
        assert skipped == []

    def test_direct_valid_transition_not_a_skip(self):
        trace = [
            TraceEntry("org/repo", "LOCAL", "CANDIDATE"),
        ]
        skipped = detect_skipped_states(trace)
        assert skipped == []

    def test_archived_from_local_skip(self):
        """LOCAL -> ARCHIVED is a valid transition, so no skip."""
        trace = [
            TraceEntry("org/repo", "LOCAL", "ARCHIVED"),
        ]
        skipped = detect_skipped_states(trace)
        assert skipped == []

    def test_empty_trace(self):
        assert detect_skipped_states([]) == []


# ---------------------------------------------------------------------------
# detect_unauthorized_transitions
# ---------------------------------------------------------------------------

class TestDetectUnauthorizedTransitions:
    def test_valid_transitions(self):
        trace = [
            TraceEntry("r", "LOCAL", "CANDIDATE"),
            TraceEntry("r", "CANDIDATE", "PUBLIC_PROCESS"),
        ]
        unauthorized = detect_unauthorized_transitions(trace)
        assert unauthorized == []

    def test_invalid_transition(self):
        trace = [
            TraceEntry("org/repo", "LOCAL", "GRADUATED"),
        ]
        unauthorized = detect_unauthorized_transitions(trace)
        assert len(unauthorized) == 1
        assert unauthorized[0]["from_state"] == "LOCAL"
        assert unauthorized[0]["to_state"] == "GRADUATED"

    def test_unknown_source_state(self):
        trace = [
            TraceEntry("org/repo", "PHANTOM", "LOCAL"),
        ]
        unauthorized = detect_unauthorized_transitions(trace)
        assert len(unauthorized) == 1
        assert "unknown source state" in unauthorized[0]["reason"]

    def test_archived_is_terminal(self):
        trace = [
            TraceEntry("org/repo", "ARCHIVED", "LOCAL"),
        ]
        unauthorized = detect_unauthorized_transitions(trace)
        assert len(unauthorized) == 1

    def test_empty_trace(self):
        assert detect_unauthorized_transitions([]) == []

    def test_custom_transition_table(self):
        custom = {"A": ["B"], "B": ["C"], "C": []}
        trace = [
            TraceEntry("r", "A", "B"),
            TraceEntry("r", "A", "C"),  # not valid
        ]
        unauthorized = detect_unauthorized_transitions(trace, custom)
        assert len(unauthorized) == 1
        assert unauthorized[0]["to_state"] == "C"

    def test_mixed_valid_and_invalid(self):
        trace = [
            TraceEntry("r1", "LOCAL", "CANDIDATE"),
            TraceEntry("r2", "LOCAL", "GRADUATED"),
            TraceEntry("r3", "CANDIDATE", "PUBLIC_PROCESS"),
        ]
        unauthorized = detect_unauthorized_transitions(trace)
        assert len(unauthorized) == 1
        assert unauthorized[0]["entity_uid"] == "r2"


# ---------------------------------------------------------------------------
# check_trace_conformance (integration)
# ---------------------------------------------------------------------------

class TestCheckTraceConformance:
    def test_perfect_conformance(self):
        trace = [
            TraceEntry("r", "LOCAL", "CANDIDATE"),
            TraceEntry("r", "CANDIDATE", "PUBLIC_PROCESS"),
            TraceEntry("r", "PUBLIC_PROCESS", "GRADUATED"),
        ]
        result = check_trace_conformance(trace)
        assert result.fitness == 1.0
        assert result.violations == []
        assert result.total_transitions == 3

    def test_empty_trace(self):
        result = check_trace_conformance([])
        assert result.fitness == 1.0
        assert result.total_transitions == 0

    def test_all_unauthorized(self):
        trace = [
            TraceEntry("r", "LOCAL", "GRADUATED"),
            TraceEntry("r", "ARCHIVED", "LOCAL"),
        ]
        result = check_trace_conformance(trace)
        assert result.fitness == 0.0
        # LOCAL->GRADUATED is both a skip and unauthorized; ARCHIVED->LOCAL is unauthorized
        assert len(result.violations) >= 2

    def test_partial_conformance(self):
        trace = [
            TraceEntry("r1", "LOCAL", "CANDIDATE"),       # valid
            TraceEntry("r2", "CANDIDATE", "LOCAL"),        # valid (demotion)
            TraceEntry("r3", "ARCHIVED", "LOCAL"),         # invalid (unauthorized only)
        ]
        result = check_trace_conformance(trace)
        assert 0.0 < result.fitness < 1.0
        assert result.total_transitions == 3

    def test_custom_transition_table(self):
        custom = {"A": ["B"], "B": ["C"], "C": []}
        trace = [
            TraceEntry("r", "A", "B"),
            TraceEntry("r", "B", "C"),
        ]
        result = check_trace_conformance(trace, custom)
        assert result.fitness == 1.0

    def test_fitness_clamped(self):
        result = check_trace_conformance(
            [TraceEntry("r", "LOCAL", "GRADUATED")],
        )
        assert 0.0 <= result.fitness <= 1.0

    def test_uses_fallback_transitions_by_default(self):
        """Ensure the default transition table matches FALLBACK_TRANSITIONS."""
        trace = [TraceEntry("r", "LOCAL", "CANDIDATE")]
        result = check_trace_conformance(trace)
        assert result.fitness == 1.0
        assert "CANDIDATE" in FALLBACK_TRANSITIONS["LOCAL"]

    def test_skipped_and_unauthorized_combined(self):
        trace = [
            TraceEntry("r1", "LOCAL", "PUBLIC_PROCESS"),   # skip
            TraceEntry("r2", "PHANTOM", "LOCAL"),           # unauthorized
        ]
        result = check_trace_conformance(trace)
        assert result.fitness == 0.0
        assert len(result.skipped_states) >= 1
        assert len(result.unauthorized_transitions) >= 1
