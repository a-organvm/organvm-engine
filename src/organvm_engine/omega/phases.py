"""Alpha-Omega phase map — 10-phase lifecycle diagnosis.

Implements: SPEC-010, PHASE-001 through PHASE-010

Five regimes, ten phases:
  Alpha (conceptual emergence):  A1 (vision seed), A2 (formal ontology)
  Beta  (formal design):         B1 (spec drafting), B2 (spec complete)
  Gamma (embodiment):            G1 (first code), G2 (coverage), G3 (integration)
  Delta (stabilization):         D1 (soak testing), D2 (hardening)
  Omega (completion/evolution):  O1 (self-governance operational)

diagnose_current_phase() determines where the system currently sits.
check_transition_condition() reports what is needed to advance.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass  # noqa: I001

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PhaseRegime(str, enum.Enum):
    """The five evolutionary regimes."""

    ALPHA = "ALPHA"
    BETA = "BETA"
    GAMMA = "GAMMA"
    DELTA = "DELTA"
    OMEGA = "OMEGA"


class Phase(str, enum.Enum):
    """The ten lifecycle phases."""

    A1 = "A1"  # Vision seed
    A2 = "A2"  # Formal ontology defined
    B1 = "B1"  # Spec drafting underway
    B2 = "B2"  # Spec set complete
    G1 = "G1"  # First code embodiment
    G2 = "G2"  # Test coverage threshold
    G3 = "G3"  # Integration complete
    D1 = "D1"  # Soak testing active
    D2 = "D2"  # Hardening complete
    O1 = "O1"  # Self-governance operational


# Ordered list for progression checks
_PHASE_ORDER: list[Phase] = [
    Phase.A1, Phase.A2, Phase.B1, Phase.B2,
    Phase.G1, Phase.G2, Phase.G3,
    Phase.D1, Phase.D2, Phase.O1,
]

_PHASE_TO_REGIME: dict[Phase, PhaseRegime] = {
    Phase.A1: PhaseRegime.ALPHA,
    Phase.A2: PhaseRegime.ALPHA,
    Phase.B1: PhaseRegime.BETA,
    Phase.B2: PhaseRegime.BETA,
    Phase.G1: PhaseRegime.GAMMA,
    Phase.G2: PhaseRegime.GAMMA,
    Phase.G3: PhaseRegime.GAMMA,
    Phase.D1: PhaseRegime.DELTA,
    Phase.D2: PhaseRegime.DELTA,
    Phase.O1: PhaseRegime.OMEGA,
}


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Minimum specs to enter each phase
_SPEC_THRESHOLDS: dict[Phase, int] = {
    Phase.A1: 0,
    Phase.A2: 1,
    Phase.B1: 3,
    Phase.B2: 8,
    Phase.G1: 8,
    Phase.G2: 8,
    Phase.G3: 8,
    Phase.D1: 8,
    Phase.D2: 8,
    Phase.O1: 8,
}

# Minimum tests for gamma+ phases
_TEST_THRESHOLDS: dict[Phase, int] = {
    Phase.G1: 1,
    Phase.G2: 500,
    Phase.G3: 1000,
    Phase.D1: 1500,
    Phase.D2: 2000,
    Phase.O1: 2500,
}

# Minimum omega criteria met for delta+ phases
_OMEGA_THRESHOLDS: dict[Phase, int] = {
    Phase.D1: 4,
    Phase.D2: 10,
    Phase.O1: 15,
}


# ---------------------------------------------------------------------------
# Phase result
# ---------------------------------------------------------------------------

@dataclass
class PhaseResult:
    """Result of phase diagnosis."""

    phase: Phase
    regime: PhaseRegime
    phase_index: int  # 0-based position in _PHASE_ORDER

    def to_dict(self) -> dict[str, str | int]:
        return {
            "phase": self.phase.value,
            "regime": self.regime.value,
            "phase_index": self.phase_index,
        }


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

def diagnose_current_phase(
    omega_met: int,
    spec_count: int,
    test_count: int,
) -> PhaseResult:
    """Determine the system's current lifecycle phase.

    Walks backward from O1 to A1, returning the highest phase whose
    thresholds are all satisfied.

    Args:
        omega_met: Number of omega criteria currently met.
        spec_count: Number of formal specifications written.
        test_count: Total test count across the system.

    Returns:
        PhaseResult with the diagnosed phase, regime, and index.
    """
    best_idx = 0  # default to A1

    for idx, phase in enumerate(_PHASE_ORDER):
        spec_req = _SPEC_THRESHOLDS.get(phase, 0)
        test_req = _TEST_THRESHOLDS.get(phase, 0)
        omega_req = _OMEGA_THRESHOLDS.get(phase, 0)

        if spec_count >= spec_req and test_count >= test_req and omega_met >= omega_req:
            best_idx = idx
        else:
            break  # phases are sequential — stop at first unmet

    best_phase = _PHASE_ORDER[best_idx]
    return PhaseResult(
        phase=best_phase,
        regime=_PHASE_TO_REGIME[best_phase],
        phase_index=best_idx,
    )


# ---------------------------------------------------------------------------
# Transition condition check
# ---------------------------------------------------------------------------

def check_transition_condition(
    current_phase: Phase,
    omega_met: int = 0,
    spec_count: int = 0,
    test_count: int = 0,
) -> tuple[bool, list[str]]:
    """Check what is needed to advance to the next phase.

    Args:
        current_phase: The current diagnosed phase.
        omega_met: Number of omega criteria met.
        spec_count: Number of formal specifications.
        test_count: Total test count.

    Returns:
        (ready, blockers) — ready is True if the next phase threshold is met.
        If current_phase is O1, returns (True, []) since there is no next phase.
    """
    idx = _PHASE_ORDER.index(current_phase)
    if idx >= len(_PHASE_ORDER) - 1:
        return True, []  # already at terminal phase

    next_phase = _PHASE_ORDER[idx + 1]
    blockers: list[str] = []

    spec_req = _SPEC_THRESHOLDS.get(next_phase, 0)
    if spec_count < spec_req:
        blockers.append(f"Need {spec_req} specs, have {spec_count}")

    test_req = _TEST_THRESHOLDS.get(next_phase, 0)
    if test_count < test_req:
        blockers.append(f"Need {test_req} tests, have {test_count}")

    omega_req = _OMEGA_THRESHOLDS.get(next_phase, 0)
    if omega_met < omega_req:
        blockers.append(f"Need {omega_req} omega criteria, have {omega_met}")

    return len(blockers) == 0, blockers


def get_regime(phase: Phase) -> PhaseRegime:
    """Return the regime for a given phase."""
    return _PHASE_TO_REGIME[phase]


def next_phase(phase: Phase) -> Phase | None:
    """Return the next phase in sequence, or None if at terminal."""
    idx = _PHASE_ORDER.index(phase)
    if idx >= len(_PHASE_ORDER) - 1:
        return None
    return _PHASE_ORDER[idx + 1]
