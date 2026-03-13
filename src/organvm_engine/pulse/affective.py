"""Affective layer — system mood derived from quantitative health signals.

Mood is a qualitative summary that collapses many health dimensions into
a single human-readable state.  It is NOT a precise metric — it's an
at-a-glance emotional read of how the system is doing, useful for
dashboards and session openers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Mood enumeration
# ---------------------------------------------------------------------------

class SystemMood(str, Enum):
    """Qualitative system health states, ordered worst-to-best."""

    FRAGILE = "fragile"
    STRESSED = "stressed"
    STAGNANT = "stagnant"
    STEADY = "steady"
    GROWING = "growing"
    THRIVING = "thriving"

    @property
    def glyph(self) -> str:
        _glyphs = {
            "thriving": "\u25c9",   # ◉
            "growing": "\u25ce",    # ◎
            "steady": "\u25cb",     # ○
            "stressed": "\u25c8",   # ◈
            "stagnant": "\u25c7",   # ◇
            "fragile": "\u25c6",    # ◆
        }
        return _glyphs.get(self.value, "?")

    @property
    def description(self) -> str:
        _descs = {
            "thriving": "High health, positive velocity, strong interconnection",
            "growing": "Positive velocity — the system is improving",
            "steady": "Stable health with no significant movement",
            "stressed": "Declining health or rising staleness",
            "stagnant": "Low velocity with significant staleness",
            "fragile": "Low health, low density, negative trajectory",
        }
        return _descs.get(self.value, "")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MoodFactors:
    """Quantitative inputs used to determine system mood."""

    health_pct: int = 0
    health_velocity: float = 0.0
    stale_ratio: float = 0.0
    stale_velocity: float = 0.0
    density_score: float = 0.0
    gate_pass_rate: float = 0.0
    promo_ready_ratio: float = 0.0
    session_frequency: float = 0.0

    def to_dict(self) -> dict:
        return {
            "health_pct": self.health_pct,
            "health_velocity": self.health_velocity,
            "stale_ratio": self.stale_ratio,
            "stale_velocity": self.stale_velocity,
            "density_score": self.density_score,
            "gate_pass_rate": self.gate_pass_rate,
            "promo_ready_ratio": self.promo_ready_ratio,
            "session_frequency": self.session_frequency,
        }


@dataclass
class MoodReading:
    """A mood determination with its supporting evidence."""

    mood: SystemMood
    factors: MoodFactors
    reasoning: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mood": self.mood.value,
            "glyph": self.mood.glyph,
            "description": self.mood.description,
            "factors": self.factors.to_dict(),
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def compute_mood(factors: MoodFactors) -> MoodReading:
    """Determine the system mood from quantitative factors.

    The cascade is ordered from most-severe to least-severe so that
    critical states take priority.  The default is STEADY.

    Args:
        factors: Quantitative health signals.

    Returns:
        MoodReading with the determined mood, factors, and reasoning.
    """
    reasoning: list[str] = []

    # --- FRAGILE: multiple critical signals simultaneously ---
    if (
        factors.health_pct < 30
        and factors.density_score < 30
        and factors.health_velocity < 0
    ):
        reasoning.append(f"Health critically low ({factors.health_pct}%)")
        reasoning.append(f"Density critically low ({factors.density_score:.0f})")
        reasoning.append(f"Negative trajectory (velocity={factors.health_velocity:.2f})")
        return MoodReading(mood=SystemMood.FRAGILE, factors=factors, reasoning=reasoning)

    # --- STRESSED: sharp decline or rising staleness ---
    if factors.health_velocity < -0.5:
        reasoning.append(f"Health declining rapidly (velocity={factors.health_velocity:.2f})")
        return MoodReading(mood=SystemMood.STRESSED, factors=factors, reasoning=reasoning)
    if factors.stale_velocity > 0.5:
        reasoning.append(f"Staleness increasing rapidly (velocity={factors.stale_velocity:.2f})")
        return MoodReading(mood=SystemMood.STRESSED, factors=factors, reasoning=reasoning)

    # --- STAGNANT: not moving and significant rot ---
    if abs(factors.health_velocity) < 0.1 and factors.stale_ratio > 0.3:
        reasoning.append(f"Near-zero velocity ({factors.health_velocity:.2f})")
        reasoning.append(f"High stale ratio ({factors.stale_ratio:.0%})")
        return MoodReading(mood=SystemMood.STAGNANT, factors=factors, reasoning=reasoning)

    # --- THRIVING: strong across multiple dimensions ---
    if (
        factors.health_pct >= 60
        and factors.health_velocity > 0.1
        and factors.density_score >= 50
    ):
        reasoning.append(f"Health strong ({factors.health_pct}%)")
        reasoning.append(f"Positive velocity ({factors.health_velocity:.2f})")
        reasoning.append(f"Good interconnection (density={factors.density_score:.0f})")
        return MoodReading(mood=SystemMood.THRIVING, factors=factors, reasoning=reasoning)

    # --- GROWING: positive velocity is the key signal ---
    if factors.health_velocity > 0.1:
        reasoning.append(f"Positive velocity ({factors.health_velocity:.2f})")
        return MoodReading(mood=SystemMood.GROWING, factors=factors, reasoning=reasoning)

    # --- STEADY: the default ---
    reasoning.append("No significant positive or negative signals")
    return MoodReading(mood=SystemMood.STEADY, factors=factors, reasoning=reasoning)
