"""Tests for organvm_engine.pulse.affective — system mood detection."""

from __future__ import annotations

from organvm_engine.pulse.affective import (
    MoodFactors,
    MoodReading,
    SystemMood,
    compute_mood,
)


# ---------------------------------------------------------------------------
# Mood determination
# ---------------------------------------------------------------------------

class TestMoodAssessment:
    def test_mood_fragile(self):
        """health<30, density<30, velocity<0 produces FRAGILE."""
        factors = MoodFactors(
            health_pct=20,
            health_velocity=-0.3,
            density_score=15.0,
            stale_ratio=0.5,
        )
        reading = compute_mood(factors)
        assert reading.mood == SystemMood.FRAGILE

    def test_mood_stressed_declining(self):
        """velocity < -0.5 produces STRESSED."""
        factors = MoodFactors(
            health_pct=60,
            health_velocity=-0.8,
            density_score=50.0,
        )
        reading = compute_mood(factors)
        assert reading.mood == SystemMood.STRESSED

    def test_mood_stressed_stale(self):
        """stale_velocity > 0.5 produces STRESSED."""
        factors = MoodFactors(
            health_pct=60,
            health_velocity=0.0,
            stale_velocity=0.8,
            density_score=50.0,
        )
        reading = compute_mood(factors)
        assert reading.mood == SystemMood.STRESSED

    def test_mood_stagnant(self):
        """Low velocity + high stale_ratio produces STAGNANT."""
        factors = MoodFactors(
            health_pct=45,
            health_velocity=0.05,
            stale_ratio=0.5,
            density_score=40.0,
        )
        reading = compute_mood(factors)
        assert reading.mood == SystemMood.STAGNANT

    def test_mood_thriving(self):
        """health>=60, velocity>0.1, density>=50 produces THRIVING."""
        factors = MoodFactors(
            health_pct=70,
            health_velocity=0.5,
            density_score=60.0,
            stale_ratio=0.05,
        )
        reading = compute_mood(factors)
        assert reading.mood == SystemMood.THRIVING

    def test_mood_growing(self):
        """velocity>0.1 but health<60 produces GROWING."""
        factors = MoodFactors(
            health_pct=40,
            health_velocity=0.3,
            density_score=30.0,
        )
        reading = compute_mood(factors)
        assert reading.mood == SystemMood.GROWING

    def test_mood_steady(self):
        """Default case with no strong signals produces STEADY."""
        factors = MoodFactors(
            health_pct=50,
            health_velocity=0.05,
            density_score=40.0,
            stale_ratio=0.1,
        )
        reading = compute_mood(factors)
        assert reading.mood == SystemMood.STEADY


# ---------------------------------------------------------------------------
# Mood metadata
# ---------------------------------------------------------------------------

class TestMoodMetadata:
    def test_mood_glyphs(self):
        """Each mood has a unique, non-empty glyph."""
        glyphs = set()
        for mood in SystemMood:
            g = mood.glyph
            assert g, f"{mood} has empty glyph"
            glyphs.add(g)
        assert len(glyphs) == len(SystemMood)

    def test_mood_descriptions(self):
        """Each mood has a non-empty description."""
        for mood in SystemMood:
            desc = mood.description
            assert desc, f"{mood} has empty description"
            assert len(desc) > 10


# ---------------------------------------------------------------------------
# MoodReading
# ---------------------------------------------------------------------------

class TestMoodReading:
    def test_mood_reading_to_dict(self):
        """to_dict serializes with all expected fields."""
        factors = MoodFactors(
            health_pct=50,
            health_velocity=0.0,
            density_score=40.0,
        )
        reading = compute_mood(factors)
        d = reading.to_dict()
        assert "mood" in d
        assert "glyph" in d
        assert "description" in d
        assert "factors" in d
        assert "reasoning" in d
        assert isinstance(d["reasoning"], list)
        assert len(d["reasoning"]) >= 1

    def test_mood_reading_reasoning_populated(self):
        """Every mood reading has at least one reasoning string."""
        for mood_factors in [
            MoodFactors(health_pct=10, health_velocity=-1, density_score=5),
            MoodFactors(health_pct=70, health_velocity=0.5, density_score=60),
            MoodFactors(health_pct=50, health_velocity=0.0, density_score=40),
        ]:
            reading = compute_mood(mood_factors)
            assert reading.reasoning, f"No reasoning for {reading.mood}"
