"""Signal algebra — Greek letter variables for the 14 post-flood signal classes.

Maps signal classes to mathematical variables and provides composability checking.
Two formations are composable iff output(g) ∩ input(f) ≠ ∅.

SPEC-019 foundation: the liquid constitutional model replaces rigid organ containers
with signal-typed formations that participate in named physiological functions.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Signal variable mapping — 14 canonical classes
# ---------------------------------------------------------------------------

SIGNAL_VARIABLES: dict[str, str] = {
    "Σ": "ANNOTATED_CORPUS",
    "Π": "ARCHIVE_PACKET",
    "Θ": "EXECUTION_TRACE",
    "Ω": "VALIDATION_RECORD",
    "Ψ": "RESEARCH_QUESTION",
    "Φ": "ONT_FRAGMENT",
    "Λ": "RULE_PROPOSAL",
    "Δ": "STATE_MODEL",
    "Ε": "FAILURE_REPORT",
    "Μ": "MIGRATION_CANDIDATE",
    "Α": "AESTHETIC_PROFILE",
    "Ι": "INTERFACE_CONTRACT",
    "Ξ": "SYNTHESIS_PACKET",
    "Ρ": "PEDAGOGICAL_UNIT",
}

# Reverse mapping: signal class name → Greek letter
VARIABLE_TO_SIGNAL: dict[str, str] = {v: k for k, v in SIGNAL_VARIABLES.items()}

# Forward alias for clarity
SIGNAL_TO_VARIABLE: dict[str, str] = SIGNAL_VARIABLES

# All valid Greek letters (for validation)
VALID_VARIABLES: frozenset[str] = frozenset(SIGNAL_VARIABLES.keys())

# Reservoir prohibition: reservoirs must not emit ontological or rule signals
_RESERVOIR_PROHIBITED_OUTPUTS: frozenset[str] = frozenset({"Φ", "Λ"})


# ---------------------------------------------------------------------------
# Signature parsing
# ---------------------------------------------------------------------------

_SIGNATURE_RE = re.compile(
    r"\(\s*([^)]*)\s*\)\s*→\s*\(\s*([^)]*)\s*\)",
)


def parse_signature(sig_str: str) -> tuple[set[str], set[str]]:
    """Parse a signature string like '(Σ,Π,Θ) → (Σ,Π,Ω)' into input/output sets.

    Returns:
        (inputs, outputs) as sets of Greek letter variables.

    Raises:
        ValueError: If the string does not match the expected format or
            contains invalid variables.
    """
    match = _SIGNATURE_RE.match(sig_str.strip())
    if not match:
        raise ValueError(
            f"Invalid signature format: {sig_str!r}. "
            "Expected '(X,Y,...) → (A,B,...)'",
        )

    def _parse_group(raw: str) -> set[str]:
        if not raw.strip():
            return set()
        items = {s.strip() for s in raw.split(",")}
        invalid = items - VALID_VARIABLES
        if invalid:
            raise ValueError(
                f"Invalid signal variables: {sorted(invalid)}. "
                f"Valid: {sorted(VALID_VARIABLES)}",
            )
        return items

    return _parse_group(match.group(1)), _parse_group(match.group(2))


# ---------------------------------------------------------------------------
# Composability
# ---------------------------------------------------------------------------


def are_composable(f_outputs: set[str], g_inputs: set[str]) -> bool:
    """Check if f can feed into g: True if output(f) ∩ input(g) ≠ ∅."""
    return bool(f_outputs & g_inputs)


def compose_signature(
    f_sig: tuple[set[str], set[str]],
    g_sig: tuple[set[str], set[str]],
) -> tuple[set[str], set[str]]:
    """Compose two signatures: f then g.

    The composed signature consumes f's inputs and produces g's outputs.
    Any of f's outputs not consumed by g are also emitted (pass-through).

    Args:
        f_sig: (inputs, outputs) of the first formation.
        g_sig: (inputs, outputs) of the second formation.

    Returns:
        (composed_inputs, composed_outputs).

    Raises:
        ValueError: If the formations are not composable.
    """
    f_inputs, f_outputs = f_sig
    g_inputs, g_outputs = g_sig

    if not are_composable(f_outputs, g_inputs):
        raise ValueError(
            "Formations are not composable: "
            f"output(f)={sorted(f_outputs)} ∩ input(g)={sorted(g_inputs)} = ∅",
        )

    # Composed input: everything f needs + anything g needs that f doesn't provide
    composed_inputs = f_inputs | (g_inputs - f_outputs)

    # Composed output: everything g produces + f outputs not consumed by g
    composed_outputs = g_outputs | (f_outputs - g_inputs)

    return composed_inputs, composed_outputs


# ---------------------------------------------------------------------------
# Reservoir law validation
# ---------------------------------------------------------------------------


def validate_reservoir_signature(
    outputs: set[str],
) -> tuple[bool, list[str]]:
    """Check reservoir law: reservoirs cannot emit Φ (ONT_FRAGMENT) or Λ (RULE_PROPOSAL).

    Reservoirs accumulate and preserve state — they must not generate theory
    or governance proposals. That is the province of generators and laboratories.

    Returns:
        (is_valid, list of violation messages).
    """
    violations: list[str] = []
    prohibited_found = outputs & _RESERVOIR_PROHIBITED_OUTPUTS
    for var in sorted(prohibited_found):
        signal_name = SIGNAL_VARIABLES[var]
        violations.append(
            f"Reservoir emits prohibited signal {var} ({signal_name})",
        )
    return len(violations) == 0, violations


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_signature(inputs: set[str], outputs: set[str]) -> str:
    """Render a signature back to canonical string form: '(Σ,Π) → (Ω,Δ)'.

    Variables are sorted for deterministic output.
    """
    in_str = ",".join(sorted(inputs))
    out_str = ",".join(sorted(outputs))
    return f"({in_str}) → ({out_str})"
