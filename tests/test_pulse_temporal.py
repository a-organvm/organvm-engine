"""Tests for organvm_engine.pulse.temporal — velocity, acceleration, trend detection."""

from __future__ import annotations

from organvm_engine.pulse.temporal import (
    TemporalMetric,
    TemporalProfile,
    TrendDirection,
    build_temporal_metric,
    compute_acceleration,
    compute_temporal_profile,
    compute_velocity,
    detect_trend,
)


# ---------------------------------------------------------------------------
# Velocity
# ---------------------------------------------------------------------------

class TestVelocity:
    def test_velocity_constant(self):
        """Constant series [5, 5, 5] has velocity 0."""
        assert compute_velocity([5.0, 5.0, 5.0]) == 0.0

    def test_velocity_rising(self):
        """Ascending series has positive velocity."""
        v = compute_velocity([1.0, 2.0, 3.0, 4.0, 5.0])
        assert v > 0

    def test_velocity_falling(self):
        """Descending series has negative velocity."""
        v = compute_velocity([5.0, 4.0, 3.0, 2.0, 1.0])
        assert v < 0

    def test_velocity_short_series_single(self):
        """Single-element series returns 0."""
        assert compute_velocity([1.0]) == 0.0

    def test_velocity_short_series_empty(self):
        """Empty series returns 0."""
        assert compute_velocity([]) == 0.0

    def test_velocity_linear(self):
        """Linear series [0, 1, 2, 3] has velocity exactly 1.0."""
        v = compute_velocity([0.0, 1.0, 2.0, 3.0])
        assert abs(v - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Acceleration
# ---------------------------------------------------------------------------

class TestAcceleration:
    def test_acceleration_constant_velocity(self):
        """Linear series (constant velocity) has acceleration ~0."""
        a = compute_acceleration([0.0, 1.0, 2.0, 3.0, 4.0])
        assert abs(a) < 0.01

    def test_acceleration_increasing(self):
        """Quadratic series (increasing velocity) has positive acceleration."""
        # 1, 4, 9, 16, 25 — diffs are 3, 5, 7, 9 — increasing
        a = compute_acceleration([1.0, 4.0, 9.0, 16.0, 25.0])
        assert a > 0

    def test_acceleration_short_series(self):
        """Series with fewer than 3 elements returns 0."""
        assert compute_acceleration([1.0, 2.0]) == 0.0
        assert compute_acceleration([1.0]) == 0.0
        assert compute_acceleration([]) == 0.0


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------

class TestTrend:
    def test_trend_stable(self):
        """Flat series is classified as STABLE."""
        trend = detect_trend([5.0, 5.0, 5.0, 5.0, 5.0])
        assert trend == TrendDirection.STABLE

    def test_trend_rising(self):
        """Ascending series is classified as RISING (or ACCELERATING)."""
        trend = detect_trend([1.0, 2.0, 3.0, 4.0, 5.0])
        assert trend in (TrendDirection.RISING, TrendDirection.ACCELERATING)

    def test_trend_falling(self):
        """Descending series is classified as FALLING (or DECELERATING)."""
        trend = detect_trend([5.0, 4.0, 3.0, 2.0, 1.0])
        assert trend in (TrendDirection.FALLING, TrendDirection.DECELERATING)

    def test_trend_oscillating(self):
        """Alternating series is classified as OSCILLATING."""
        trend = detect_trend([1.0, 5.0, 1.0, 5.0, 1.0, 5.0])
        assert trend == TrendDirection.OSCILLATING

    def test_trend_short_series(self):
        """Single element defaults to STABLE."""
        assert detect_trend([3.0]) == TrendDirection.STABLE

    def test_trend_two_elements_rising(self):
        """Two elements with positive diff can be RISING."""
        trend = detect_trend([1.0, 10.0])
        assert trend in (TrendDirection.RISING, TrendDirection.ACCELERATING)


# ---------------------------------------------------------------------------
# Build temporal metric
# ---------------------------------------------------------------------------

class TestBuildTemporalMetric:
    def test_temporal_metric(self):
        """build_temporal_metric creates a metric with correct fields."""
        m = build_temporal_metric("sys_pct", [40.0, 42.0, 45.0, 50.0])
        assert isinstance(m, TemporalMetric)
        assert m.name == "sys_pct"
        assert m.current == 50.0
        assert isinstance(m.velocity, float)
        assert isinstance(m.acceleration, float)
        assert isinstance(m.trend, TrendDirection)
        assert m.window_size == 7  # default

    def test_temporal_metric_empty(self):
        """Empty series produces current=0 and velocity=0."""
        m = build_temporal_metric("empty", [])
        assert m.current == 0.0
        assert m.velocity == 0.0

    def test_temporal_metric_to_dict(self):
        """to_dict includes all expected keys."""
        m = build_temporal_metric("health", [50.0, 55.0, 60.0])
        d = m.to_dict()
        assert "name" in d
        assert "current" in d
        assert "velocity" in d
        assert "acceleration" in d
        assert "trend" in d
        assert "momentum" in d

    def test_temporal_metric_momentum(self):
        """Momentum is current * velocity."""
        m = build_temporal_metric("test", [0.0, 10.0, 20.0])
        assert abs(m.momentum - m.current * m.velocity) < 0.001


# ---------------------------------------------------------------------------
# Temporal profile
# ---------------------------------------------------------------------------

class TestTemporalProfile:
    def test_temporal_profile(self):
        """compute_temporal_profile builds metrics for each named series."""
        data = {
            "health": [40.0, 45.0, 50.0],
            "stale": [10.0, 8.0, 6.0],
        }
        profile = compute_temporal_profile(data)
        assert isinstance(profile, TemporalProfile)
        assert len(profile.metrics) == 2
        names = {m.name for m in profile.metrics}
        assert names == {"health", "stale"}

    def test_temporal_profile_empty_series_skipped(self):
        """Empty series in the input are skipped."""
        data = {
            "health": [40.0, 50.0],
            "empty": [],
        }
        profile = compute_temporal_profile(data)
        assert len(profile.metrics) == 1

    def test_temporal_profile_dominant_trend(self):
        """dominant_trend reflects the most common trend among metrics."""
        data = {
            "rising_1": [1.0, 2.0, 3.0, 4.0, 5.0],
            "rising_2": [10.0, 20.0, 30.0, 40.0, 50.0],
            "flat": [5.0, 5.0, 5.0, 5.0, 5.0],
        }
        profile = compute_temporal_profile(data)
        # Two rising, one stable — dominant should be a rising-family trend
        assert profile.dominant_trend in (
            TrendDirection.RISING, TrendDirection.ACCELERATING,
        )

    def test_temporal_profile_to_dict(self):
        """to_dict includes dominant_trend and metrics list."""
        data = {"health": [50.0, 55.0]}
        profile = compute_temporal_profile(data)
        d = profile.to_dict()
        assert "dominant_trend" in d
        assert "total_momentum" in d
        assert "metrics" in d
