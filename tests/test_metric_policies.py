"""Tests for organvm_engine.pulse.metric_policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from organvm_engine.pulse.metric_policies import (
    METRIC_THRESHOLDS,
    MetricThreshold,
    evaluate_metric_thresholds,
)


# ---------------------------------------------------------------------------
# Minimal Observation stub — avoids ontologia dependency in tests
# ---------------------------------------------------------------------------


@dataclass
class _Obs:
    """Minimal stand-in for ontologia.metrics.observations.Observation."""

    metric_id: str
    entity_id: str
    value: float


# ---------------------------------------------------------------------------
# MetricThreshold.evaluate()
# ---------------------------------------------------------------------------


class TestMetricThresholdEvaluate:
    def test_below_min_fires(self):
        t = MetricThreshold(metric_id="m", name="M", min_value=20.0)
        breached, threshold_value = t.evaluate(15.0)
        assert breached is True
        assert threshold_value == 20.0

    def test_at_min_does_not_fire(self):
        t = MetricThreshold(metric_id="m", name="M", min_value=20.0)
        breached, _ = t.evaluate(20.0)
        assert breached is False

    def test_above_min_does_not_fire(self):
        t = MetricThreshold(metric_id="m", name="M", min_value=20.0)
        breached, _ = t.evaluate(25.0)
        assert breached is False

    def test_above_max_fires(self):
        t = MetricThreshold(metric_id="m", name="M", max_value=100.0)
        breached, threshold_value = t.evaluate(150.0)
        assert breached is True
        assert threshold_value == 100.0

    def test_at_max_does_not_fire(self):
        t = MetricThreshold(metric_id="m", name="M", max_value=100.0)
        breached, _ = t.evaluate(100.0)
        assert breached is False

    def test_within_range_does_not_fire(self):
        t = MetricThreshold(metric_id="m", name="M", min_value=10.0, max_value=90.0)
        breached, _ = t.evaluate(50.0)
        assert breached is False

    def test_none_value_does_not_fire(self):
        t = MetricThreshold(metric_id="m", name="M", min_value=20.0, max_value=100.0)
        breached, threshold_value = t.evaluate(None)
        assert breached is False
        assert threshold_value is None

    def test_no_bounds_never_fires(self):
        t = MetricThreshold(metric_id="m", name="M")
        breached, _ = t.evaluate(0.0)
        assert breached is False
        breached, _ = t.evaluate(1_000_000.0)
        assert breached is False


# ---------------------------------------------------------------------------
# MetricThreshold.evaluate_delta()
# ---------------------------------------------------------------------------


class TestMetricThresholdEvaluateDelta:
    def test_large_delta_fires(self):
        t = MetricThreshold(metric_id="m", name="M", max_delta=10.0)
        breached, delta = t.evaluate_delta(25.0, 10.0)
        assert breached is True
        assert delta == pytest.approx(15.0)

    def test_small_delta_does_not_fire(self):
        t = MetricThreshold(metric_id="m", name="M", max_delta=10.0)
        breached, _ = t.evaluate_delta(15.0, 10.0)
        assert breached is False

    def test_negative_change_uses_absolute_value(self):
        t = MetricThreshold(metric_id="m", name="M", max_delta=5.0)
        breached, delta = t.evaluate_delta(10.0, 20.0)
        assert breached is True
        assert delta == pytest.approx(10.0)

    def test_none_current_does_not_fire(self):
        t = MetricThreshold(metric_id="m", name="M", max_delta=5.0)
        breached, _ = t.evaluate_delta(None, 10.0)
        assert breached is False

    def test_none_previous_does_not_fire(self):
        t = MetricThreshold(metric_id="m", name="M", max_delta=5.0)
        breached, _ = t.evaluate_delta(10.0, None)
        assert breached is False

    def test_no_max_delta_never_fires(self):
        t = MetricThreshold(metric_id="m", name="M")
        breached, _ = t.evaluate_delta(1000.0, 0.0)
        assert breached is False


# ---------------------------------------------------------------------------
# METRIC_THRESHOLDS catalogue
# ---------------------------------------------------------------------------


class TestMetricThresholdsCatalogue:
    def test_has_at_least_two_entries(self):
        assert len(METRIC_THRESHOLDS) >= 2

    def test_all_entries_have_metric_id_and_name(self):
        for t in METRIC_THRESHOLDS:
            assert t.metric_id, f"Entry {t!r} has no metric_id"
            assert t.name, f"Entry {t!r} has no name"

    def test_ci_coverage_threshold_present(self):
        ids = [t.metric_id for t in METRIC_THRESHOLDS]
        assert "met_ci_coverage" in ids

    def test_test_coverage_threshold_present(self):
        ids = [t.metric_id for t in METRIC_THRESHOLDS]
        assert "met_test_coverage" in ids


# ---------------------------------------------------------------------------
# evaluate_metric_thresholds()
# ---------------------------------------------------------------------------


class TestEvaluateMetricThresholds:
    def test_returns_advisory_for_breached_min(self):
        obs = [_Obs(metric_id="met_ci_coverage", entity_id="ORGAN-I/repo-a", value=5.0)]
        advisories = evaluate_metric_thresholds(obs)
        assert len(advisories) == 1
        adv = advisories[0]
        assert "met_ci_coverage" in adv.policy_id
        assert adv.entity_id == "ORGAN-I/repo-a"
        assert adv.severity == "warning"

    def test_returns_no_advisory_when_healthy(self):
        obs = [
            _Obs(metric_id="met_ci_coverage", entity_id="ORGAN-I/repo-a", value=80.0),
            _Obs(metric_id="met_test_coverage", entity_id="ORGAN-I/repo-a", value=70.0),
        ]
        advisories = evaluate_metric_thresholds(obs)
        assert advisories == []

    def test_returns_advisory_for_delta_breach(self):
        threshold = MetricThreshold(
            metric_id="repo_count",
            name="Repo Count",
            max_delta=5.0,
        )
        obs = [_Obs(metric_id="repo_count", entity_id="system", value=50.0)]
        prev = [_Obs(metric_id="repo_count", entity_id="system", value=30.0)]
        advisories = evaluate_metric_thresholds(obs, prev, thresholds=[threshold])
        assert len(advisories) == 1
        assert advisories[0].evidence["prev_value"] == 30.0

    def test_no_advisory_for_small_delta(self):
        threshold = MetricThreshold(
            metric_id="repo_count",
            name="Repo Count",
            max_delta=5.0,
        )
        obs = [_Obs(metric_id="repo_count", entity_id="system", value=50.0)]
        prev = [_Obs(metric_id="repo_count", entity_id="system", value=48.0)]
        advisories = evaluate_metric_thresholds(obs, prev, thresholds=[threshold])
        assert advisories == []

    def test_empty_observations_returns_empty(self):
        advisories = evaluate_metric_thresholds([])
        assert advisories == []

    def test_advisory_id_is_deterministic_12_chars(self):
        obs = [_Obs(metric_id="met_ci_coverage", entity_id="X/repo", value=5.0)]
        a1 = evaluate_metric_thresholds(obs)
        a2 = evaluate_metric_thresholds(obs)
        assert len(a1) == 1
        assert len(a2) == 1
        # IDs are date-keyed, so same run always produces the same ID
        assert a1[0].advisory_id == a2[0].advisory_id
        assert len(a1[0].advisory_id) == 12

    def test_multiple_entities_produce_separate_advisories(self):
        obs = [
            _Obs(metric_id="met_ci_coverage", entity_id="ORGAN-I/repo-a", value=5.0),
            _Obs(metric_id="met_ci_coverage", entity_id="ORGAN-I/repo-b", value=3.0),
        ]
        advisories = evaluate_metric_thresholds(obs)
        entity_ids = {a.entity_id for a in advisories}
        assert "ORGAN-I/repo-a" in entity_ids
        assert "ORGAN-I/repo-b" in entity_ids

    def test_custom_thresholds_override_defaults(self):
        custom = [
            MetricThreshold(
                metric_id="my_metric",
                name="My Metric",
                min_value=50.0,
                severity="critical",
            )
        ]
        obs = [_Obs(metric_id="my_metric", entity_id="ent-1", value=10.0)]
        advisories = evaluate_metric_thresholds(obs, thresholds=custom)
        assert len(advisories) == 1
        assert advisories[0].severity == "critical"

    def test_evidence_contains_value_and_threshold(self):
        obs = [_Obs(metric_id="met_ci_coverage", entity_id="X/r", value=5.0)]
        advisories = evaluate_metric_thresholds(obs)
        assert len(advisories) == 1
        ev = advisories[0].evidence
        assert ev["value"] == pytest.approx(5.0)
        assert ev["threshold"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Smoke test: evaluate_all_policies() doesn't crash
# ---------------------------------------------------------------------------


class TestEvaluateAllPoliciesSmoke:
    def test_does_not_crash(self, tmp_path, monkeypatch):
        """evaluate_all_policies() must not raise even without ontologia."""
        # Route advisory storage to tmp
        monkeypatch.setattr(
            "organvm_engine.pulse.advisories._advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        from organvm_engine.pulse.advisories import evaluate_all_policies

        result = evaluate_all_policies()
        # Returns a list (may be empty when registry or ontologia unavailable)
        assert isinstance(result, list)
