"""Tests for governance.signal_algebra — signal variable mapping and composability."""

from __future__ import annotations

import pytest

from organvm_engine.governance.signal_algebra import (
    SIGNAL_TO_VARIABLE,
    SIGNAL_VARIABLES,
    VALID_VARIABLES,
    VARIABLE_TO_SIGNAL,
    are_composable,
    compose_signature,
    parse_signature,
    render_signature,
    validate_reservoir_signature,
)

# ---------------------------------------------------------------------------
# Mapping integrity
# ---------------------------------------------------------------------------


class TestSignalVariables:
    def test_fourteen_variables(self):
        assert len(SIGNAL_VARIABLES) == 14

    def test_all_values_are_uppercase_signal_names(self):
        for var, name in SIGNAL_VARIABLES.items():
            assert name == name.upper(), f"{var} → {name} is not uppercase"
            assert "_" in name, f"{var} → {name} has no underscore separator"

    def test_reverse_mapping_is_complete(self):
        assert len(VARIABLE_TO_SIGNAL) == 14
        for name, var in VARIABLE_TO_SIGNAL.items():
            assert SIGNAL_VARIABLES[var] == name

    def test_forward_alias(self):
        assert SIGNAL_TO_VARIABLE is SIGNAL_VARIABLES

    def test_valid_variables_frozenset(self):
        assert isinstance(VALID_VARIABLES, frozenset)
        assert set(SIGNAL_VARIABLES.keys()) == VALID_VARIABLES


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class TestParseSignature:
    def test_basic_parse(self):
        inputs, outputs = parse_signature("(Σ,Π,Θ) → (Σ,Π,Ω)")
        assert inputs == {"Σ", "Π", "Θ"}
        assert outputs == {"Σ", "Π", "Ω"}

    def test_single_element(self):
        inputs, outputs = parse_signature("(Σ) → (Ω)")
        assert inputs == {"Σ"}
        assert outputs == {"Ω"}

    def test_whitespace_tolerance(self):
        inputs, outputs = parse_signature("( Σ , Π ) → ( Ω , Δ )")
        assert inputs == {"Σ", "Π"}
        assert outputs == {"Ω", "Δ"}

    def test_empty_inputs(self):
        inputs, outputs = parse_signature("() → (Σ)")
        assert inputs == set()
        assert outputs == {"Σ"}

    def test_empty_outputs(self):
        inputs, outputs = parse_signature("(Σ) → ()")
        assert inputs == {"Σ"}
        assert outputs == set()

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid signature format"):
            parse_signature("Σ → Ω")

    def test_invalid_variable_raises(self):
        with pytest.raises(ValueError, match="Invalid signal variables"):
            parse_signature("(X) → (Ω)")

    def test_all_fourteen(self):
        all_vars = ",".join(sorted(VALID_VARIABLES))
        sig = f"({all_vars}) → ({all_vars})"
        inputs, outputs = parse_signature(sig)
        assert inputs == VALID_VARIABLES
        assert outputs == VALID_VARIABLES


# ---------------------------------------------------------------------------
# Composability
# ---------------------------------------------------------------------------


class TestComposability:
    def test_composable_overlap(self):
        assert are_composable({"Σ", "Π"}, {"Π", "Θ"}) is True

    def test_not_composable_disjoint(self):
        assert are_composable({"Σ"}, {"Θ"}) is False

    def test_empty_outputs_not_composable(self):
        assert are_composable(set(), {"Σ"}) is False

    def test_empty_inputs_not_composable(self):
        assert are_composable({"Σ"}, set()) is False

    def test_identical_sets_composable(self):
        assert are_composable({"Σ", "Π"}, {"Σ", "Π"}) is True


class TestComposeSignature:
    def test_basic_composition(self):
        f = ({"Σ"}, {"Π", "Θ"})
        g = ({"Π"}, {"Ω"})
        result = compose_signature(f, g)
        # Composed input: f needs Σ, g needs Π (provided by f) → just Σ
        # Composed output: g produces Ω, f's Θ passes through (not consumed by g)
        assert result == ({"Σ"}, {"Ω", "Θ"})

    def test_full_consumption(self):
        f = ({"Σ"}, {"Π"})
        g = ({"Π"}, {"Ω"})
        result = compose_signature(f, g)
        assert result == ({"Σ"}, {"Ω"})

    def test_g_needs_extra_inputs(self):
        f = ({"Σ"}, {"Π"})
        g = ({"Π", "Δ"}, {"Ω"})
        result = compose_signature(f, g)
        # g needs Δ that f doesn't provide → composed input includes it
        assert result == ({"Σ", "Δ"}, {"Ω"})

    def test_not_composable_raises(self):
        f = ({"Σ"}, {"Π"})
        g = ({"Θ"}, {"Ω"})
        with pytest.raises(ValueError, match="not composable"):
            compose_signature(f, g)

    def test_identity_like(self):
        """A formation that passes through what it consumes."""
        f = ({"Σ"}, {"Σ", "Ω"})
        g = ({"Σ"}, {"Δ"})
        result = compose_signature(f, g)
        assert result == ({"Σ"}, {"Δ", "Ω"})


# ---------------------------------------------------------------------------
# Reservoir law
# ---------------------------------------------------------------------------


class TestReservoirLaw:
    def test_valid_reservoir(self):
        valid, errors = validate_reservoir_signature({"Σ", "Π", "Θ"})
        assert valid is True
        assert errors == []

    def test_phi_prohibited(self):
        valid, errors = validate_reservoir_signature({"Σ", "Φ"})
        assert valid is False
        assert len(errors) == 1
        assert "ONT_FRAGMENT" in errors[0]

    def test_lambda_prohibited(self):
        valid, errors = validate_reservoir_signature({"Λ"})
        assert valid is False
        assert len(errors) == 1
        assert "RULE_PROPOSAL" in errors[0]

    def test_both_prohibited(self):
        valid, errors = validate_reservoir_signature({"Φ", "Λ", "Σ"})
        assert valid is False
        assert len(errors) == 2

    def test_empty_outputs_valid(self):
        valid, errors = validate_reservoir_signature(set())
        assert valid is True
        assert errors == []


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


class TestRenderSignature:
    def test_basic_render(self):
        result = render_signature({"Σ", "Π"}, {"Ω", "Δ"})
        # Sorted: Greek letters in Unicode order
        assert "→" in result
        # Parse back to verify roundtrip
        inputs, outputs = parse_signature(result)
        assert inputs == {"Σ", "Π"}
        assert outputs == {"Ω", "Δ"}

    def test_empty_render(self):
        result = render_signature(set(), set())
        assert result == "() → ()"

    def test_roundtrip(self):
        original = "(Α,Σ,Ψ) → (Ι,Ξ)"
        inputs, outputs = parse_signature(original)
        rendered = render_signature(inputs, outputs)
        re_inputs, re_outputs = parse_signature(rendered)
        assert re_inputs == inputs
        assert re_outputs == outputs
