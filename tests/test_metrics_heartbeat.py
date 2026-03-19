"""Tests for heartbeat engine (INST-HEARTBEAT)."""

import pytest

from organvm_engine.metrics.heartbeat import (
    GestaltState,
    HeartbeatReport,
    compute_gestalt,
    compute_heartbeat,
    heartbeat_from_gate_results,
)

# ---------------------------------------------------------------------------
# GestaltState computation
# ---------------------------------------------------------------------------


class TestComputeGestalt:
    def test_empty_is_brittle(self):
        assert compute_gestalt({}) == GestaltState.BRITTLE

    def test_all_high_is_thriving(self):
        scores = {"a": 0.9, "b": 0.8, "c": 0.95}
        assert compute_gestalt(scores) == GestaltState.THRIVING

    def test_threshold_075_is_thriving(self):
        scores = {"a": 0.75, "b": 0.80}
        assert compute_gestalt(scores) == GestaltState.THRIVING

    def test_one_low_drags_down(self):
        scores = {"a": 0.9, "b": 0.9, "c": 0.3}
        assert compute_gestalt(scores) == GestaltState.STRAINED

    def test_all_medium_is_coherent(self):
        scores = {"a": 0.6, "b": 0.7, "c": 0.55}
        assert compute_gestalt(scores) == GestaltState.COHERENT

    def test_one_very_low_is_brittle(self):
        scores = {"a": 0.9, "b": 0.1}
        assert compute_gestalt(scores) == GestaltState.BRITTLE

    def test_exact_050_is_coherent(self):
        scores = {"a": 0.50}
        assert compute_gestalt(scores) == GestaltState.COHERENT

    def test_exact_025_is_strained(self):
        scores = {"a": 0.25}
        assert compute_gestalt(scores) == GestaltState.STRAINED

    def test_zero_is_brittle(self):
        scores = {"a": 0.0}
        assert compute_gestalt(scores) == GestaltState.BRITTLE


# ---------------------------------------------------------------------------
# Heartbeat report
# ---------------------------------------------------------------------------


class TestComputeHeartbeat:
    def test_basic_report(self):
        scores = {"existence": 0.9, "identity": 0.8, "law": 0.7}
        report = compute_heartbeat(scores)
        assert isinstance(report, HeartbeatReport)
        assert report.gestalt == GestaltState.COHERENT
        assert report.min_dimension == "law"
        assert report.min_score == pytest.approx(0.7)

    def test_empty_scores(self):
        report = compute_heartbeat({})
        assert report.gestalt == GestaltState.BRITTLE
        assert report.min_dimension == ""

    def test_to_dict(self):
        scores = {"a": 0.8, "b": 0.9}
        report = compute_heartbeat(scores)
        d = report.to_dict()
        assert d["gestalt"] == "THRIVING"
        assert "dimension_scores" in d
        assert "min_dimension" in d

    def test_summary_output(self):
        scores = {"test": 0.5}
        report = compute_heartbeat(scores)
        s = report.summary()
        assert "Heartbeat Report" in s
        assert "Gestalt" in s


# ---------------------------------------------------------------------------
# From gate results
# ---------------------------------------------------------------------------


class TestHeartbeatFromGateResults:
    def test_score_based_gates(self):
        gates = {
            "SEED": {"score": 0.9},
            "CI": {"score": 0.8},
            "TESTS": {"score": 0.7},
        }
        report = heartbeat_from_gate_results(gates)
        assert report.gestalt == GestaltState.COHERENT
        assert report.min_dimension == "TESTS"

    def test_bool_based_gates(self):
        gates = {
            "SEED": {"passed": True},
            "CI": {"passed": True},
            "TESTS": {"passed": False},
        }
        report = heartbeat_from_gate_results(gates)
        assert report.gestalt == GestaltState.BRITTLE
        assert report.min_score == 0.0

    def test_numeric_values(self):
        gates = {"a": 0.8, "b": 0.9}
        report = heartbeat_from_gate_results(gates)
        assert report.gestalt == GestaltState.THRIVING

    def test_bool_values(self):
        gates = {"a": True, "b": False}
        report = heartbeat_from_gate_results(gates)
        assert report.gestalt == GestaltState.BRITTLE

    def test_empty_gates(self):
        report = heartbeat_from_gate_results({})
        assert report.gestalt == GestaltState.BRITTLE

    def test_mixed_gate_types(self):
        gates = {
            "a": {"score": 0.9},
            "b": {"passed": True},
            "c": 0.85,
        }
        report = heartbeat_from_gate_results(gates)
        assert report.gestalt == GestaltState.THRIVING
