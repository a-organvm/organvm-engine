"""Tests for alpha-omega phase map (SPEC-010)."""

import pytest

from organvm_engine.omega.phases import (
    Phase,
    PhaseRegime,
    PhaseResult,
    check_transition_condition,
    diagnose_current_phase,
    get_regime,
    next_phase,
)

# ---------------------------------------------------------------------------
# Regime mapping
# ---------------------------------------------------------------------------


class TestPhaseRegime:
    def test_alpha_phases(self):
        assert get_regime(Phase.A1) == PhaseRegime.ALPHA
        assert get_regime(Phase.A2) == PhaseRegime.ALPHA

    def test_beta_phases(self):
        assert get_regime(Phase.B1) == PhaseRegime.BETA
        assert get_regime(Phase.B2) == PhaseRegime.BETA

    def test_gamma_phases(self):
        assert get_regime(Phase.G1) == PhaseRegime.GAMMA
        assert get_regime(Phase.G2) == PhaseRegime.GAMMA
        assert get_regime(Phase.G3) == PhaseRegime.GAMMA

    def test_delta_phases(self):
        assert get_regime(Phase.D1) == PhaseRegime.DELTA
        assert get_regime(Phase.D2) == PhaseRegime.DELTA

    def test_omega_phase(self):
        assert get_regime(Phase.O1) == PhaseRegime.OMEGA


# ---------------------------------------------------------------------------
# Phase progression
# ---------------------------------------------------------------------------


class TestNextPhase:
    def test_a1_to_a2(self):
        assert next_phase(Phase.A1) == Phase.A2

    def test_g3_to_d1(self):
        assert next_phase(Phase.G3) == Phase.D1

    def test_o1_terminal(self):
        assert next_phase(Phase.O1) is None

    def test_full_chain(self):
        expected = [
            Phase.A2, Phase.B1, Phase.B2, Phase.G1,
            Phase.G2, Phase.G3, Phase.D1, Phase.D2, Phase.O1, None,
        ]
        current = Phase.A1
        for exp in expected:
            current = next_phase(current)
            assert current == exp


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------


class TestDiagnoseCurrentPhase:
    def test_zero_everything_is_a1(self):
        result = diagnose_current_phase(omega_met=0, spec_count=0, test_count=0)
        assert result.phase == Phase.A1
        assert result.regime == PhaseRegime.ALPHA

    def test_one_spec_is_a2(self):
        result = diagnose_current_phase(omega_met=0, spec_count=1, test_count=0)
        assert result.phase == Phase.A2

    def test_three_specs_is_b1(self):
        result = diagnose_current_phase(omega_met=0, spec_count=3, test_count=0)
        assert result.phase == Phase.B1

    def test_eight_specs_is_b2(self):
        result = diagnose_current_phase(omega_met=0, spec_count=8, test_count=0)
        assert result.phase == Phase.B2

    def test_first_code_g1(self):
        result = diagnose_current_phase(omega_met=0, spec_count=8, test_count=1)
        assert result.phase == Phase.G1

    def test_coverage_g2(self):
        result = diagnose_current_phase(omega_met=0, spec_count=8, test_count=500)
        assert result.phase == Phase.G2

    def test_integration_g3(self):
        result = diagnose_current_phase(omega_met=0, spec_count=8, test_count=1000)
        assert result.phase == Phase.G3

    def test_soak_d1(self):
        result = diagnose_current_phase(omega_met=4, spec_count=8, test_count=1500)
        assert result.phase == Phase.D1

    def test_hardening_d2(self):
        result = diagnose_current_phase(omega_met=10, spec_count=8, test_count=2000)
        assert result.phase == Phase.D2

    def test_omega_o1(self):
        result = diagnose_current_phase(omega_met=15, spec_count=8, test_count=2500)
        assert result.phase == Phase.O1

    def test_result_has_index(self):
        result = diagnose_current_phase(omega_met=0, spec_count=3, test_count=0)
        assert result.phase_index == 2  # B1 is index 2

    def test_result_to_dict(self):
        result = diagnose_current_phase(omega_met=0, spec_count=0, test_count=0)
        d = result.to_dict()
        assert d["phase"] == "A1"
        assert d["regime"] == "ALPHA"
        assert "phase_index" in d


# ---------------------------------------------------------------------------
# Transition condition
# ---------------------------------------------------------------------------


class TestCheckTransitionCondition:
    def test_a1_needs_spec(self):
        ready, blockers = check_transition_condition(Phase.A1, spec_count=0)
        assert not ready
        assert any("spec" in b.lower() for b in blockers)

    def test_a1_ready(self):
        ready, blockers = check_transition_condition(Phase.A1, spec_count=1)
        assert ready
        assert blockers == []

    def test_g2_needs_tests(self):
        ready, blockers = check_transition_condition(
            Phase.G2, spec_count=8, test_count=500,
        )
        assert not ready
        assert any("test" in b.lower() for b in blockers)

    def test_d1_needs_omega(self):
        ready, blockers = check_transition_condition(
            Phase.D1, spec_count=8, test_count=2000, omega_met=5,
        )
        assert not ready
        assert any("omega" in b.lower() for b in blockers)

    def test_o1_always_ready(self):
        ready, blockers = check_transition_condition(Phase.O1)
        assert ready
        assert blockers == []
