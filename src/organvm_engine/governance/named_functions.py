"""Named functions — the hydra's heads.

Replaces numbered organs with named physiological functions.
Functions are attractors, not containers. Formations participate in functions.

SPEC-019 foundation: the liquid constitutional model dissolves rigid organ
boundaries. A formation's primary participation is its strongest gravitational
pull, but it may participate in multiple functions simultaneously.

The 8 named functions + genome:
  theoria   — Knowledge production and symbolic systems
  poiesis   — Creative formation and generative art
  ergon     — Practical realization and functional artifacts
  taxis     — Systemic coordination and orchestration
  logos     — Discourse, interpretation, and articulation
  koinonia  — Community, learning, and shared participation
  kerygma   — Distribution and outward broadcast
  mneme     — Memory — accumulated experience across all domains
  meta      — Constitutional substrate (the genome)
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Named functions registry
# ---------------------------------------------------------------------------

NAMED_FUNCTIONS: dict[str, dict[str, Any]] = {
    "theoria": {
        "display_name": "Theoria",
        "physiological_role": "Knowledge production and symbolic systems",
        "greek": "Θεωρία",
    },
    "poiesis": {
        "display_name": "Poiesis",
        "physiological_role": "Creative formation and generative art",
        "greek": "Ποίησις",
    },
    "ergon": {
        "display_name": "Ergon",
        "physiological_role": "Practical realization and functional artifacts",
        "greek": "Ἔργον",
    },
    "taxis": {
        "display_name": "Taxis",
        "physiological_role": "Systemic coordination and orchestration",
        "greek": "Τάξις",
    },
    "logos": {
        "display_name": "Logos",
        "physiological_role": "Discourse, interpretation, and articulation",
        "greek": "Λόγος",
    },
    "koinonia": {
        "display_name": "Koinonia",
        "physiological_role": "Community, learning, and shared participation",
        "greek": "Κοινωνία",
    },
    "kerygma": {
        "display_name": "Kerygma",
        "physiological_role": "Distribution and outward broadcast",
        "greek": "Κήρυγμα",
    },
    "mneme": {
        "display_name": "Mneme",
        "physiological_role": "Memory — accumulated experience across all domains",
        "greek": "Μνήμη",
    },
    "meta": {
        "display_name": "Genome",
        "physiological_role": "Constitutional substrate — law, registry, schema, migration",
        "greek": "Μετά",
        "is_genome": True,
    },
}

# All valid function names (for validation)
VALID_FUNCTION_NAMES: frozenset[str] = frozenset(NAMED_FUNCTIONS.keys())

# ---------------------------------------------------------------------------
# Organ ↔ function bridge (backward compatibility)
# ---------------------------------------------------------------------------

# Maps old organ CLI keys (I, II, ... META) to named functions.
_ORGAN_TO_FUNCTION: dict[str, str] = {
    "I": "theoria",
    "II": "poiesis",
    "III": "ergon",
    "IV": "taxis",
    "V": "logos",
    "VI": "koinonia",
    "VII": "kerygma",
    "META": "meta",
    # mneme is new — no legacy organ maps to it
}

_FUNCTION_TO_ORGAN: dict[str, str] = {v: k for k, v in _ORGAN_TO_FUNCTION.items()}


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------


def get_function(name: str) -> dict[str, Any]:
    """Look up a named function by key.

    Args:
        name: Function key (e.g., 'theoria', 'poiesis').

    Returns:
        The function's metadata dict.

    Raises:
        KeyError: If the function name is not recognized.
    """
    if name not in NAMED_FUNCTIONS:
        raise KeyError(
            f"Unknown function: {name!r}. "
            f"Valid: {sorted(VALID_FUNCTION_NAMES)}",
        )
    return {**NAMED_FUNCTIONS[name], "key": name}


def list_functions() -> list[dict[str, Any]]:
    """Return all named functions as a list of dicts (each includes 'key')."""
    return [
        {**meta, "key": key}
        for key, meta in NAMED_FUNCTIONS.items()
    ]


def validate_participation(
    participates_in: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate that participation declarations reference real function names.

    Args:
        participates_in: Dict with 'primary' (str) and optional 'secondary' (list[str]).

    Returns:
        (is_valid, list of error messages).
    """
    errors: list[str] = []

    primary = participates_in.get("primary")
    if not primary:
        errors.append("Missing required 'primary' function")
    elif primary not in VALID_FUNCTION_NAMES:
        errors.append(
            f"Unknown primary function: {primary!r}. "
            f"Valid: {sorted(VALID_FUNCTION_NAMES)}",
        )

    secondary = participates_in.get("secondary", [])
    if not isinstance(secondary, list):
        errors.append(f"'secondary' must be a list, got {type(secondary).__name__}")
    else:
        for name in secondary:
            if name not in VALID_FUNCTION_NAMES:
                errors.append(
                    f"Unknown secondary function: {name!r}. "
                    f"Valid: {sorted(VALID_FUNCTION_NAMES)}",
                )
        if primary and primary in secondary:
            errors.append(
                f"Primary function {primary!r} should not also appear in secondary",
            )

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Organ ↔ function bridge
# ---------------------------------------------------------------------------


def organ_to_function(organ_key: str) -> str | None:
    """Map a legacy organ key (e.g., 'I', 'III', 'META') to its named function.

    Returns None if the organ key has no function mapping (e.g., LIMINAL).
    """
    return _ORGAN_TO_FUNCTION.get(organ_key)


def function_to_organ(function_name: str) -> str | None:
    """Map a named function back to its legacy organ key.

    Returns None for functions without a legacy organ (e.g., 'mneme').
    """
    return _FUNCTION_TO_ORGAN.get(function_name)
