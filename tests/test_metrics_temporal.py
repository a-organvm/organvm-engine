"""Tests for temporal metrics, variable resolution, and AMMOI layer."""

import pytest

from organvm_engine.metrics.temporal import (
    MetricType,
    TrendDirection,
    VariableBinding,
    VariableScope,
    classify_metric,
    compute_trend,
    resolve_all,
    resolve_variable,
)

# ---------------------------------------------------------------------------
# Metric classification
# ---------------------------------------------------------------------------


class TestClassifyMetric:
    def test_total_repos_is_stock(self):
        assert classify_metric("total_repos") == MetricType.STOCK

    def test_code_files_is_stock(self):
        assert classify_metric("code_files") == MetricType.STOCK

    def test_commits_per_week_is_flow(self):
        assert classify_metric("commits_per_week") == MetricType.FLOW

    def test_deploys_per_month_is_flow(self):
        assert classify_metric("deploys_per_month") == MetricType.FLOW

    def test_ci_pass_rate_is_rate(self):
        assert classify_metric("ci_pass_rate") == MetricType.RATE

    def test_coverage_is_rate(self):
        assert classify_metric("test_coverage") == MetricType.RATE

    def test_unknown_defaults_to_stock(self):
        assert classify_metric("some_random_thing") == MetricType.STOCK

    def test_case_insensitive(self):
        assert classify_metric("TOTAL_REPOS") == MetricType.STOCK
        assert classify_metric("CI_PASS_RATE") == MetricType.RATE


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------


class TestComputeTrend:
    def test_increasing_is_improving(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert compute_trend(values) == TrendDirection.IMPROVING

    def test_decreasing_is_declining(self):
        values = [5.0, 4.0, 3.0, 2.0, 1.0]
        assert compute_trend(values) == TrendDirection.DECLINING

    def test_flat_is_stable(self):
        values = [5.0, 5.0, 5.0, 5.0]
        assert compute_trend(values) == TrendDirection.STABLE

    def test_nearly_flat_is_stable(self):
        # Symmetric noise around 10.0 — slope/range near zero, not volatile
        values = [10.0, 9.8, 10.2, 9.9, 10.1, 10.0, 9.95, 10.05]
        assert compute_trend(values) == TrendDirection.STABLE

    def test_single_value_is_stable(self):
        values = [42.0]
        assert compute_trend(values) == TrendDirection.STABLE

    def test_two_values_increasing(self):
        values = [1.0, 10.0]
        assert compute_trend(values) == TrendDirection.IMPROVING

    def test_volatile_oscillation(self):
        values = [1.0, 100.0, 1.0, 100.0, 1.0]
        assert compute_trend(values) == TrendDirection.VOLATILE

    def test_empty_is_stable(self):
        assert compute_trend([]) == TrendDirection.STABLE

    def test_all_zeros_is_stable(self):
        values = [0.0, 0.0, 0.0]
        assert compute_trend(values) == TrendDirection.STABLE

    def test_custom_thresholds(self):
        values = [1.0, 1.1, 1.2]
        # With very strict stability threshold, this should still be IMPROVING
        result = compute_trend(values, stability_threshold=0.01)
        assert result == TrendDirection.IMPROVING


# ---------------------------------------------------------------------------
# Variable scope
# ---------------------------------------------------------------------------


class TestVariableScope:
    def test_all_six_scopes(self):
        assert len(VariableScope) == 6

    def test_values(self):
        assert VariableScope.MODULE.value == "MODULE"
        assert VariableScope.COMPUTED.value == "COMPUTED"


# ---------------------------------------------------------------------------
# Variable resolution
# ---------------------------------------------------------------------------


class TestResolveVariable:
    @pytest.fixture
    def scope_chain(self):
        return {
            "MODULE": {"x": 10, "local_only": "m"},
            "REPO": {"x": 20, "y": 30},
            "ORGAN": {"y": 40, "z": 50},
            "GLOBAL": {"z": 60, "w": 70},
        }

    def test_narrowest_wins(self, scope_chain):
        result = resolve_variable("x", scope_chain)
        assert result is not None
        assert result.value == 10
        assert result.scope == VariableScope.MODULE

    def test_repo_scope(self, scope_chain):
        result = resolve_variable("y", scope_chain)
        assert result is not None
        assert result.value == 30
        assert result.scope == VariableScope.REPO

    def test_organ_scope(self, scope_chain):
        result = resolve_variable("z", scope_chain)
        assert result is not None
        assert result.value == 50
        assert result.scope == VariableScope.ORGAN

    def test_global_scope(self, scope_chain):
        result = resolve_variable("w", scope_chain)
        assert result is not None
        assert result.value == 70
        assert result.scope == VariableScope.GLOBAL

    def test_not_found(self, scope_chain):
        result = resolve_variable("missing", scope_chain)
        assert result is None

    def test_empty_chain(self):
        result = resolve_variable("x", {})
        assert result is None

    def test_partial_chain(self):
        chain = {"ORGAN": {"a": 1}}
        result = resolve_variable("a", chain)
        assert result is not None
        assert result.scope == VariableScope.ORGAN

    def test_module_only_var(self, scope_chain):
        result = resolve_variable("local_only", scope_chain)
        assert result is not None
        assert result.value == "m"


# ---------------------------------------------------------------------------
# Resolve all
# ---------------------------------------------------------------------------


class TestResolveAll:
    def test_multiple_names(self):
        chain = {
            "REPO": {"a": 1, "b": 2},
            "GLOBAL": {"c": 3},
        }
        results = resolve_all(["a", "b", "c", "missing"], chain)
        assert results["a"] is not None
        assert results["a"].value == 1
        assert results["b"].value == 2
        assert results["c"].value == 3
        assert results["missing"] is None

    def test_empty_names(self):
        results = resolve_all([], {"GLOBAL": {"x": 1}})
        assert results == {}
