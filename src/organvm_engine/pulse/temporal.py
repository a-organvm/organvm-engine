"""Time-awareness layer — velocity, acceleration, and trend detection.

Converts raw time-series data (lists of floats sampled over time) into
TemporalMetric objects that carry velocity, acceleration, and a trend
classification.  A TemporalProfile aggregates multiple metrics to give
the system a sense of overall momentum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Trend enumeration
# ---------------------------------------------------------------------------

class TrendDirection(str, Enum):
    """Classification of a metric's trajectory over a time window."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    OSCILLATING = "oscillating"
    ACCELERATING = "accelerating"
    DECELERATING = "decelerating"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TemporalMetric:
    """A single metric with its temporal derivatives."""

    name: str
    current: float
    velocity: float
    acceleration: float
    trend: TrendDirection
    window_size: int

    @property
    def momentum(self) -> float:
        """Momentum = current value * rate of change."""
        return self.current * self.velocity

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "current": self.current,
            "velocity": self.velocity,
            "acceleration": self.acceleration,
            "trend": self.trend.value,
            "window_size": self.window_size,
            "momentum": self.momentum,
        }


@dataclass
class TemporalProfile:
    """Aggregate temporal state across multiple metrics."""

    metrics: list[TemporalMetric] = field(default_factory=list)

    @property
    def dominant_trend(self) -> TrendDirection:
        """Most frequently occurring trend across all metrics."""
        if not self.metrics:
            return TrendDirection.STABLE
        counts: dict[TrendDirection, int] = {}
        for m in self.metrics:
            counts[m.trend] = counts.get(m.trend, 0) + 1
        return max(counts, key=lambda t: counts[t])

    @property
    def total_momentum(self) -> float:
        """Sum of momentum across all tracked metrics."""
        return sum(m.momentum for m in self.metrics)

    def to_dict(self) -> dict:
        return {
            "dominant_trend": self.dominant_trend.value,
            "total_momentum": self.total_momentum,
            "metrics": [m.to_dict() for m in self.metrics],
        }


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def compute_velocity(series: list[float], window: int = 7) -> float:
    """Average rate of change over the last *window* samples.

    Uses the mean of successive differences within the window.
    Returns 0.0 if the series is too short.
    """
    if len(series) < 2:
        return 0.0
    tail = series[-window:] if len(series) >= window else series
    diffs = [tail[i + 1] - tail[i] for i in range(len(tail) - 1)]
    return sum(diffs) / len(diffs)


def compute_acceleration(series: list[float], window: int = 7) -> float:
    """Rate of change of velocity — the velocity of velocities.

    Computes per-step velocity within the window, then takes the mean
    of successive velocity differences.
    """
    if len(series) < 3:
        return 0.0
    tail = series[-window:] if len(series) >= window else series
    diffs = [tail[i + 1] - tail[i] for i in range(len(tail) - 1)]
    if len(diffs) < 2:
        return 0.0
    accel = [diffs[i + 1] - diffs[i] for i in range(len(diffs) - 1)]
    return sum(accel) / len(accel)


def detect_trend(series: list[float], threshold: float = 0.01) -> TrendDirection:
    """Classify the trajectory of a series.

    Checks for oscillation first (frequent sign changes in the diffs),
    then uses velocity and acceleration to pick the right label.
    """
    if len(series) < 2:
        return TrendDirection.STABLE

    tail = series[-14:]  # use a wider window for oscillation detection
    diffs = [tail[i + 1] - tail[i] for i in range(len(tail) - 1)]

    # Oscillation: count sign changes among non-zero diffs
    signs = [1 if d > 0 else (-1 if d < 0 else 0) for d in diffs]
    sign_changes = sum(
        1 for i in range(len(signs) - 1)
        if signs[i] != 0 and signs[i + 1] != 0 and signs[i] != signs[i + 1]
    )
    if len(diffs) >= 4 and sign_changes >= len(diffs) * 0.5:
        return TrendDirection.OSCILLATING

    vel = compute_velocity(series)
    acc = compute_acceleration(series)

    # Accelerating/decelerating are refinements of rising/falling
    if abs(vel) > threshold:
        if vel > 0 and acc > threshold:
            return TrendDirection.ACCELERATING
        if vel < 0 and acc < -threshold:
            return TrendDirection.DECELERATING
        return TrendDirection.RISING if vel > 0 else TrendDirection.FALLING

    return TrendDirection.STABLE


def build_temporal_metric(
    name: str,
    series: list[float],
    window: int = 7,
) -> TemporalMetric:
    """Construct a TemporalMetric from a raw time series.

    Args:
        name: Human label for this metric (e.g. "sys_pct", "stale_count").
        series: Ordered float samples (oldest first).
        window: Lookback window for velocity/acceleration.

    Returns:
        TemporalMetric with computed derivatives and trend.
    """
    current = series[-1] if series else 0.0
    return TemporalMetric(
        name=name,
        current=current,
        velocity=compute_velocity(series, window),
        acceleration=compute_acceleration(series, window),
        trend=detect_trend(series),
        window_size=window,
    )


def compute_temporal_profile(
    timeseries_data: dict[str, list[float]],
    window: int = 7,
) -> TemporalProfile:
    """Build a full temporal profile from named time-series data.

    Args:
        timeseries_data: Mapping of metric name -> ordered float samples.
        window: Lookback window for derivative computation.

    Returns:
        TemporalProfile containing one TemporalMetric per input series.
    """
    metrics = [
        build_temporal_metric(name, series, window)
        for name, series in sorted(timeseries_data.items())
        if series  # skip empty series
    ]
    return TemporalProfile(metrics=metrics)
