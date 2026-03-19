"""Temporal metrics, variable resolution, and AMMOI integration layer.

Implements: INST-TEMPORAL-METRICS, INST-VARIABLE-RESOLUTION, INST-AMMOI

Three sub-systems unified in a thin operational layer:

  INST-TEMPORAL-METRICS — classify metrics as STOCK, FLOW, or RATE and
  detect trend direction from time-series values.

  INST-VARIABLE-RESOLUTION — resolve named variables through a scope
  chain (module < repo < organ < global), narrowest-first.

  INST-AMMOI — metric type classification used by the AMMOI sense cycle
  to distinguish what kind of quantity is being observed.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Metric classification (INST-TEMPORAL-METRICS + INST-AMMOI)
# ---------------------------------------------------------------------------


class MetricType(str, enum.Enum):
    """Temporal classification of a metric.

    STOCK  — point-in-time quantity (repo count, code files)
    FLOW   — quantity over a period (commits/week, deploys/month)
    RATE   — ratio or percentage (test coverage, CI pass rate)
    """

    STOCK = "STOCK"
    FLOW = "FLOW"
    RATE = "RATE"


# Known metric name prefixes/patterns
_STOCK_PATTERNS = frozenset({
    "total_", "count_", "code_files", "test_files", "repos",
    "repo_count", "module_count", "word_count", "entity_count",
})
_FLOW_PATTERNS = frozenset({
    "commits_", "deploys_", "events_", "sessions_",
    "per_week", "per_month", "per_day",
})
_RATE_PATTERNS = frozenset({
    "rate", "ratio", "coverage", "percentage", "pct_", "fraction",
    "ci_pass", "pass_rate",
})


def classify_metric(metric_name: str) -> MetricType:
    """Classify a metric name into its temporal type.

    Uses pattern matching on the metric name. Defaults to STOCK
    if no pattern matches.

    Args:
        metric_name: The metric name to classify.

    Returns:
        MetricType (STOCK, FLOW, or RATE).
    """
    name_lower = metric_name.lower()

    for pattern in _RATE_PATTERNS:
        if pattern in name_lower:
            return MetricType.RATE

    for pattern in _FLOW_PATTERNS:
        if pattern in name_lower:
            return MetricType.FLOW

    for pattern in _STOCK_PATTERNS:
        if pattern in name_lower:
            return MetricType.STOCK

    return MetricType.STOCK


# ---------------------------------------------------------------------------
# Trend detection (INST-TEMPORAL-METRICS)
# ---------------------------------------------------------------------------


class TrendDirection(str, enum.Enum):
    """Direction of a metric trend over time."""

    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"
    VOLATILE = "VOLATILE"


def compute_trend(
    values: list[float],
    stability_threshold: float = 0.05,
    volatility_threshold: float = 0.3,
) -> TrendDirection:
    """Detect trend direction from a series of numeric values.

    Uses a simple linear regression slope normalized by range.

    Args:
        values: Time-ordered list of metric values (at least 2).
        stability_threshold: Max |slope| to consider STABLE.
        volatility_threshold: Min coefficient of variation for VOLATILE.

    Returns:
        TrendDirection.
    """
    if len(values) < 2:
        return TrendDirection.STABLE

    n = len(values)
    mean_val = sum(values) / n

    # Linear regression slope
    x_mean = (n - 1) / 2.0
    numerator = sum((i - x_mean) * (v - mean_val) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return TrendDirection.STABLE

    slope = numerator / denominator

    # Volatility check: measure residuals from the linear fit.
    # A monotonic series has low residuals; an oscillating series has high.
    predicted = [mean_val + slope * (i - x_mean) for i in range(n)]
    residuals = [v - p for v, p in zip(values, predicted, strict=True)]
    val_range = max(values) - min(values)

    if val_range > 0:
        residual_var = sum(r * r for r in residuals) / n
        residual_cv = math.sqrt(residual_var) / val_range
        if residual_cv > volatility_threshold:
            return TrendDirection.VOLATILE

    # Normalize slope by value range for comparability
    if val_range > 0:
        normalized_slope = slope / val_range
    else:
        return TrendDirection.STABLE

    if abs(normalized_slope) <= stability_threshold:
        return TrendDirection.STABLE
    if normalized_slope > 0:
        return TrendDirection.IMPROVING
    return TrendDirection.DECLINING


# ---------------------------------------------------------------------------
# Variable resolution (INST-VARIABLE-RESOLUTION)
# ---------------------------------------------------------------------------


class VariableScope(str, enum.Enum):
    """Scopes for variable resolution, narrowest to broadest."""

    MODULE = "MODULE"
    REPO = "REPO"
    ORGAN = "ORGAN"
    GLOBAL = "GLOBAL"
    SESSION = "SESSION"
    COMPUTED = "COMPUTED"


# Resolution order: narrowest first
_RESOLUTION_ORDER: list[VariableScope] = [
    VariableScope.MODULE,
    VariableScope.REPO,
    VariableScope.ORGAN,
    VariableScope.GLOBAL,
]


@dataclass
class VariableBinding:
    """A resolved variable with its source scope."""

    name: str
    value: Any
    scope: VariableScope
    source: str = ""  # which scope dict it came from


def resolve_variable(
    name: str,
    scope_chain: dict[str, dict[str, Any]],
) -> VariableBinding | None:
    """Resolve a variable through the scope chain, narrowest first.

    The scope_chain is a dict keyed by VariableScope values, each
    containing a flat dict of variable names to values.

    Example:
        scope_chain = {
            "MODULE": {"x": 10},
            "REPO": {"x": 20, "y": 30},
            "ORGAN": {"y": 40, "z": 50},
            "GLOBAL": {"z": 60, "w": 70},
        }
        resolve_variable("x", scope_chain)  # → VariableBinding("x", 10, MODULE)
        resolve_variable("z", scope_chain)  # → VariableBinding("z", 50, ORGAN)

    Args:
        name: The variable name to resolve.
        scope_chain: Dict of scope_name -> {var_name: value}.

    Returns:
        VariableBinding if found, None if not found in any scope.
    """
    for scope in _RESOLUTION_ORDER:
        scope_dict = scope_chain.get(scope.value, {})
        if name in scope_dict:
            return VariableBinding(
                name=name,
                value=scope_dict[name],
                scope=scope,
                source=scope.value,
            )
    return None


def resolve_all(
    names: list[str],
    scope_chain: dict[str, dict[str, Any]],
) -> dict[str, VariableBinding | None]:
    """Resolve multiple variables through the scope chain.

    Args:
        names: List of variable names to resolve.
        scope_chain: Dict of scope_name -> {var_name: value}.

    Returns:
        Dict of name -> VariableBinding (or None if unresolved).
    """
    return {name: resolve_variable(name, scope_chain) for name in names}
