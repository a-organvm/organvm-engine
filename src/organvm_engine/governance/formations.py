"""Formation engine — 7 formation types for the signal-flow architecture.

Implements: INST-FORMATION, FORM-001 through FORM-007

Seven formation types from the constitutional corpus:
  FORM-001  GENERATOR    — produces primary artifacts (code, schemas, docs)
  FORM-002  TRANSFORMER  — converts one artifact type to another
  FORM-003  ROUTER       — directs signals between formations without mutation
  FORM-004  RESERVOIR    — accumulates and preserves state
  FORM-005  INTERFACE    — mediates between system interior and exterior
  FORM-006  LABORATORY   — experimental sandbox with governed promotion
  FORM-007  SYNTHESIZER  — fuses inputs from multiple formations

Each formation declares signal inputs/outputs, maturity level, and
exit modes. validate_formation() checks structural completeness.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FormationType(str, enum.Enum):
    """The seven canonical formation types."""

    GENERATOR = "GENERATOR"
    TRANSFORMER = "TRANSFORMER"
    ROUTER = "ROUTER"
    RESERVOIR = "RESERVOIR"
    INTERFACE = "INTERFACE"
    LABORATORY = "LABORATORY"
    SYNTHESIZER = "SYNTHESIZER"


class SignalClass(str, enum.Enum):
    """Canonical signal classes — Formation Protocol §8.1 (post-flood)."""

    RESEARCH_QUESTION = "RESEARCH_QUESTION"
    ONT_FRAGMENT = "ONT_FRAGMENT"
    RULE_PROPOSAL = "RULE_PROPOSAL"
    STATE_MODEL = "STATE_MODEL"
    ARCHIVE_PACKET = "ARCHIVE_PACKET"
    ANNOTATED_CORPUS = "ANNOTATED_CORPUS"
    PEDAGOGICAL_UNIT = "PEDAGOGICAL_UNIT"
    EXECUTION_TRACE = "EXECUTION_TRACE"
    FAILURE_REPORT = "FAILURE_REPORT"
    MIGRATION_CANDIDATE = "MIGRATION_CANDIDATE"
    AESTHETIC_PROFILE = "AESTHETIC_PROFILE"
    INTERFACE_CONTRACT = "INTERFACE_CONTRACT"
    SYNTHESIS_PACKET = "SYNTHESIS_PACKET"
    VALIDATION_RECORD = "VALIDATION_RECORD"


# Signals each formation type is expected to produce
_EXPECTED_OUTPUTS: dict[FormationType, set[str]] = {
    FormationType.GENERATOR: {"ONT_FRAGMENT", "RULE_PROPOSAL", "STATE_MODEL"},
    FormationType.TRANSFORMER: {"ANNOTATED_CORPUS", "STATE_MODEL"},
    FormationType.ROUTER: {"EXECUTION_TRACE"},
    FormationType.RESERVOIR: {"ARCHIVE_PACKET", "PEDAGOGICAL_UNIT", "ANNOTATED_CORPUS", "FAILURE_REPORT"},
    FormationType.INTERFACE: {"INTERFACE_CONTRACT", "EXECUTION_TRACE"},
    FormationType.LABORATORY: {"FAILURE_REPORT", "VALIDATION_RECORD"},
    FormationType.SYNTHESIZER: {"SYNTHESIS_PACKET", "MIGRATION_CANDIDATE"},
}

RESERVOIR_ALLOWED_OUTPUTS = _EXPECTED_OUTPUTS[FormationType.RESERVOIR]

# Prohibited couplings: (from_type, to_type) pairs that are not allowed
_PROHIBITED_COUPLINGS: set[tuple[str, str]] = {
    ("ROUTER", "ONT_FRAGMENT"),      # routers must not invent theory (§10.3)
    ("RESERVOIR", "RULE_PROPOSAL"),   # archives must not propose rules (§15)
    ("RESERVOIR", "ONT_FRAGMENT"),    # archives must not redefine ontology (§15)
}


# ---------------------------------------------------------------------------
# Formation dataclass
# ---------------------------------------------------------------------------

@dataclass
class Formation:
    """A single formation declaration.

    Fields:
        formation_type: One of the 7 FormationType values.
        host_organ: The organ key hosting this formation (e.g., "ORGAN-I").
        host_repo: The repository hosting this formation.
        signals_in: List of signal class names this formation consumes.
        signals_out: List of signal class names this formation produces.
        maturity: Maturity level (0.0 to 1.0).
        exit_modes: How this formation can be retired/transitioned.
    """

    formation_type: str = ""
    host_organ: str = ""
    host_repo: str = ""
    signals_in: list[str] = field(default_factory=list)
    signals_out: list[str] = field(default_factory=list)
    maturity: float = 0.0
    exit_modes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "formation_type": self.formation_type,
            "host_organ": self.host_organ,
            "host_repo": self.host_repo,
            "signals_in": self.signals_in,
            "signals_out": self.signals_out,
            "maturity": self.maturity,
            "exit_modes": self.exit_modes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Formation:
        return cls(
            formation_type=data.get("formation_type", ""),
            host_organ=data.get("host_organ", ""),
            host_repo=data.get("host_repo", ""),
            signals_in=data.get("signals_in", []),
            signals_out=data.get("signals_out", []),
            maturity=data.get("maturity", 0.0),
            exit_modes=data.get("exit_modes", []),
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_formation(formation_data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a formation declaration for structural completeness.

    Checks:
    - formation_type is a valid FormationType
    - host_organ is present
    - host_repo is present
    - signals_out is non-empty
    - No prohibited couplings
    - maturity is in [0.0, 1.0]

    Args:
        formation_data: Dict with formation fields.

    Returns:
        (valid, errors) — valid is True when all checks pass.
    """
    errors: list[str] = []

    # Type check
    ftype = formation_data.get("formation_type", "")
    valid_types = {t.value for t in FormationType}
    if ftype not in valid_types:
        errors.append(f"Invalid formation_type: '{ftype}' (valid: {sorted(valid_types)})")

    # Host fields
    if not formation_data.get("host_organ"):
        errors.append("Missing host_organ")
    if not formation_data.get("host_repo"):
        errors.append("Missing host_repo")

    # Signal outputs
    signals_out = formation_data.get("signals_out", [])
    if not signals_out:
        errors.append("No signals_out declared (formations must produce signals)")

    # Prohibited couplings
    for sig in signals_out:
        if (ftype, sig) in _PROHIBITED_COUPLINGS:
            errors.append(f"Prohibited coupling: {ftype} -> {sig}")

    # Maturity range
    maturity = formation_data.get("maturity", 0.0)
    if not isinstance(maturity, (int, float)):
        errors.append(f"maturity must be numeric, got {type(maturity).__name__}")
    elif maturity < 0.0 or maturity > 1.0:
        errors.append(f"maturity out of range [0.0, 1.0]: {maturity}")

    # Validate signal class names
    valid_signals = {s.value for s in SignalClass}
    for sig in signals_out:
        if sig not in valid_signals:
            errors.append(f"Unknown signal class in signals_out: '{sig}'")
    for sig in formation_data.get("signals_in", []):
        if sig not in valid_signals:
            errors.append(f"Unknown signal class in signals_in: '{sig}'")

    return len(errors) == 0, errors


def classify_repo_formation(
    repo: dict[str, Any],
) -> FormationType | None:
    """Heuristic classification of a repo into a formation type.

    Uses tier, name patterns, and description to guess which formation
    type a repo most closely resembles. Returns None if no clear match.

    Args:
        repo: A repository dict from the registry.

    Returns:
        FormationType or None.
    """
    name = (repo.get("name") or "").lower()
    desc = (repo.get("description") or "").lower()
    tier = (repo.get("tier") or "").lower()
    combined = f"{name} {desc}"

    if tier == "infrastructure":
        return FormationType.ROUTER

    if any(w in combined for w in ("engine", "generator", "compiler", "builder")):
        return FormationType.GENERATOR

    if any(w in combined for w in ("transform", "convert", "pipeline", "ingest")):
        return FormationType.TRANSFORMER

    if any(w in combined for w in ("dashboard", "portal", "ui", "interface", "api")):
        return FormationType.INTERFACE

    if any(w in combined for w in ("corpus", "archive", "registry", "store")):
        return FormationType.RESERVOIR

    if any(w in combined for w in ("lab", "experiment", "sandbox", "prototype")):
        return FormationType.LABORATORY

    if any(w in combined for w in ("synth", "merge", "fusion", "collider")):
        return FormationType.SYNTHESIZER

    return None
