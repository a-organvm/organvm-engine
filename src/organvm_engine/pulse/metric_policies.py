"""Metric threshold advisory policies.

Evaluates numeric observations against defined thresholds and emits Advisory
objects when values breach min/max bounds or change too rapidly.

Completely optional — if ontologia is unavailable, all evaluation returns
empty lists without raising.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MetricThreshold:
    """Declarative threshold policy for a single metric.

    Fields
    ------
    metric_id : str
        The ontologia metric_id this threshold targets (e.g. "ci_coverage").
    name : str
        Human-readable name for display and advisory descriptions.
    severity : str
        Severity level emitted when this threshold fires: "info", "warning",
        or "critical".
    min_value : float | None
        Breach fires when the observed value is *below* this. None = no lower
        bound.
    max_value : float | None
        Breach fires when the observed value is *above* this. None = no upper
        bound.
    max_delta : float | None
        Breach fires when ``abs(current - previous)`` exceeds this. None =
        no delta check.
    description_template : str
        Format string rendered with ``{metric_id}``, ``{name}``, ``{value}``,
        ``{threshold}`` and ``{entity_id}``.
    """

    metric_id: str
    name: str
    severity: str = "warning"
    min_value: float | None = None
    max_value: float | None = None
    max_delta: float | None = None
    description_template: str = (
        "{name} threshold breached for {entity_id}: value {value} "
        "(threshold {threshold})"
    )

    def evaluate(self, value: float | None) -> tuple[bool, float | None]:
        """Check whether *value* breaches a min or max bound.

        Parameters
        ----------
        value:
            The current observed numeric value.  ``None`` never fires.

        Returns
        -------
        (breached, threshold_value)
            ``breached`` is True when a bound is violated; ``threshold_value``
            is the bound that was crossed (for evidence), or None.
        """
        if value is None:
            return False, None

        if self.min_value is not None and value < self.min_value:
            return True, self.min_value

        if self.max_value is not None and value > self.max_value:
            return True, self.max_value

        return False, None

    def evaluate_delta(
        self,
        current: float | None,
        previous: float | None,
    ) -> tuple[bool, float | None]:
        """Check whether the absolute change between two observations is too large.

        Parameters
        ----------
        current:
            The latest observed value.
        previous:
            The immediately prior observed value.

        Returns
        -------
        (breached, delta)
            ``breached`` is True when ``abs(current - previous) > max_delta``;
            ``delta`` is the computed absolute change, or None.
        """
        if self.max_delta is None:
            return False, None
        if current is None or previous is None:
            return False, None

        delta = abs(current - previous)
        if delta > self.max_delta:
            return True, delta

        return False, None


# ---------------------------------------------------------------------------
# Default thresholds
# ---------------------------------------------------------------------------

METRIC_THRESHOLDS: list[MetricThreshold] = [
    MetricThreshold(
        metric_id="met_ci_coverage",
        name="CI Coverage",
        severity="warning",
        min_value=20.0,
        description_template=(
            "{name} below threshold for {entity_id}: {value:.1f}% "
            "(minimum {threshold:.1f}%)"
        ),
    ),
    MetricThreshold(
        metric_id="met_test_coverage",
        name="Test Coverage",
        severity="warning",
        min_value=30.0,
        description_template=(
            "{name} below threshold for {entity_id}: {value:.1f}% "
            "(minimum {threshold:.1f}%)"
        ),
    ),
    MetricThreshold(
        metric_id="met_total_repos",
        name="Repo Count Delta",
        severity="info",
        max_delta=10.0,
        description_template=(
            "{name} changed rapidly for {entity_id}: delta {value:.0f} "
            "(maximum allowed {threshold:.0f})"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _make_metric_advisory_id(metric_id: str, entity_id: str) -> str:
    """Deterministic advisory ID keyed to date so it refreshes daily."""
    now = datetime.now(timezone.utc).isoformat()
    raw = f"metric:{metric_id}:{entity_id}:{now[:10]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def evaluate_metric_thresholds(
    observations: list[Any],
    prev_observations: list[Any] | None = None,
    thresholds: list[MetricThreshold] | None = None,
) -> list[Any]:
    """Evaluate metric thresholds against a list of ontologia Observations.

    Parameters
    ----------
    observations:
        List of ``ontologia.metrics.observations.Observation`` objects
        (or any object with ``metric_id``, ``entity_id``, ``value`` attrs).
    prev_observations:
        Optional prior snapshot for delta checks.  Matched by (metric_id,
        entity_id).
    thresholds:
        Threshold definitions.  Defaults to ``METRIC_THRESHOLDS``.

    Returns
    -------
    list[Advisory]
        Advisory objects (imported from ``advisories`` module) for every
        breached threshold.  Returns empty list on any error.
    """
    try:
        from organvm_engine.pulse.advisories import Advisory
    except ImportError:
        return []

    if thresholds is None:
        thresholds = METRIC_THRESHOLDS

    now = datetime.now(timezone.utc).isoformat()

    # Index observations by (metric_id, entity_id) for quick lookup
    obs_index: dict[tuple[str, str], float] = {}
    for obs in observations:
        key = (obs.metric_id, obs.entity_id)
        obs_index[key] = obs.value

    prev_index: dict[tuple[str, str], float] = {}
    if prev_observations:
        for obs in prev_observations:
            key = (obs.metric_id, obs.entity_id)
            prev_index[key] = obs.value

    advisories: list[Advisory] = []

    for threshold in thresholds:
        # Collect unique entity IDs for this metric_id
        entity_ids = {
            entity_id
            for (mid, entity_id) in obs_index
            if mid == threshold.metric_id
        }

        for entity_id in entity_ids:
            key = (threshold.metric_id, entity_id)
            current_value = obs_index.get(key)
            prev_value = prev_index.get(key)

            # Check min/max breach
            breached, threshold_value = threshold.evaluate(current_value)
            if not breached and prev_value is not None:
                # Check delta breach
                breached, delta = threshold.evaluate_delta(current_value, prev_value)
                if breached:
                    threshold_value = threshold.max_delta

            if breached and threshold_value is not None:
                adv_id = _make_metric_advisory_id(threshold.metric_id, entity_id)
                try:
                    description = threshold.description_template.format(
                        metric_id=threshold.metric_id,
                        name=threshold.name,
                        value=current_value if current_value is not None else 0.0,
                        threshold=threshold_value,
                        entity_id=entity_id,
                    )
                except (KeyError, ValueError):
                    description = (
                        f"{threshold.name} threshold breached for {entity_id}"
                    )

                evidence: dict[str, Any] = {
                    "metric_id": threshold.metric_id,
                    "value": current_value,
                    "threshold": threshold_value,
                }
                if prev_value is not None:
                    evidence["prev_value"] = prev_value

                advisories.append(
                    Advisory(
                        advisory_id=adv_id,
                        policy_id=f"metric-threshold:{threshold.metric_id}",
                        action="notify",
                        entity_id=entity_id,
                        entity_name=entity_id,
                        description=description,
                        severity=threshold.severity,
                        timestamp=now,
                        evidence=evidence,
                    ),
                )

    return advisories
