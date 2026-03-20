"""Dialect enumeration and organ-to-dialect mapping.

Each ORGANVM organ speaks a distinct dialect. This module defines the eight
dialects, maps them to organs, and provides metadata about each dialect's
translation role in the universal logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique


@unique
class Dialect(Enum):
    """The eight dialects of universal logic, one per organ."""

    FORMAL_LOGIC = "formal_logic"                    # I — Theoria
    AESTHETIC_FORM = "aesthetic_form"                  # II — Poiesis
    EXECUTABLE_ALGORITHM = "executable_algorithm"      # III — Ergon
    GOVERNANCE_LOGIC = "governance_logic"              # IV — Taxis
    NATURAL_RHETORIC = "natural_rhetoric"              # V — Logos
    PEDAGOGICAL_DIALECTIC = "pedagogical_dialectic"    # VI — Koinonia
    SIGNAL_PROPAGATION = "signal_propagation"          # VII — Kerygma
    SELF_WITNESSING = "self_witnessing"                # META


@dataclass(frozen=True)
class DialectProfile:
    """Metadata for a single dialect."""

    dialect: Dialect
    organ_key: str
    organ_name: str
    translation_role: str
    formal_basis: str
    classical_parallel: str
    description: str


# Canonical mapping: organ key → dialect
_ORGAN_TO_DIALECT: dict[str, Dialect] = {
    "I": Dialect.FORMAL_LOGIC,
    "II": Dialect.AESTHETIC_FORM,
    "III": Dialect.EXECUTABLE_ALGORITHM,
    "IV": Dialect.GOVERNANCE_LOGIC,
    "V": Dialect.NATURAL_RHETORIC,
    "VI": Dialect.PEDAGOGICAL_DIALECTIC,
    "VII": Dialect.SIGNAL_PROPAGATION,
    "META": Dialect.SELF_WITNESSING,
}

_DIALECT_TO_ORGAN: dict[Dialect, str] = {v: k for k, v in _ORGAN_TO_DIALECT.items()}

# Dialect profiles with metadata
_PROFILES: dict[Dialect, DialectProfile] = {
    Dialect.FORMAL_LOGIC: DialectProfile(
        dialect=Dialect.FORMAL_LOGIC,
        organ_key="I", organ_name="Theoria",
        translation_role="The Grammar — defines well-formedness in any dialect",
        formal_basis="Martin-Löf 1984, dependent type theory",
        classical_parallel="Logic",
        description="Formal logic, type theory, recursive engines, symbolic computing",
    ),
    Dialect.AESTHETIC_FORM: DialectProfile(
        dialect=Dialect.AESTHETIC_FORM,
        organ_key="II", organ_name="Poiesis",
        translation_role="The Poetry — proves formal structures have sensory form",
        formal_basis="Generative grammar, algorithmic composition",
        classical_parallel="Music",
        description="Aesthetic form, generative art, performance systems, creative coding",
    ),
    Dialect.EXECUTABLE_ALGORITHM: DialectProfile(
        dialect=Dialect.EXECUTABLE_ALGORITHM,
        organ_key="III", organ_name="Ergon",
        translation_role="The Engineering — proves that proofs compute",
        formal_basis="Curry-Howard correspondence (programs are proofs)",
        classical_parallel="Arithmetic",
        description="Executable algorithms, commercial products, developer utilities",
    ),
    Dialect.GOVERNANCE_LOGIC: DialectProfile(
        dialect=Dialect.GOVERNANCE_LOGIC,
        organ_key="IV", organ_name="Taxis",
        translation_role="The Meta-Logic — governance rules ARE propositions",
        formal_basis="ADICO institutional grammar (Crawford & Ostrom 1995)",
        classical_parallel="Rhetoric",
        description="Governance logic, orchestration, AI agents, coordination",
    ),
    Dialect.NATURAL_RHETORIC: DialectProfile(
        dialect=Dialect.NATURAL_RHETORIC,
        organ_key="V", organ_name="Logos",
        translation_role=(
            "The Hermeneutics — translates formal ↔ natural language"
        ),
        formal_basis="Pragmatics, speech act theory (Austin 1962)",
        classical_parallel="Grammar",
        description="Natural rhetoric, public discourse, essays, editorial",
    ),
    Dialect.PEDAGOGICAL_DIALECTIC: DialectProfile(
        dialect=Dialect.PEDAGOGICAL_DIALECTIC,
        organ_key="VI", organ_name="Koinonia",
        translation_role="The Dialectic — teaching IS inter-dialect translation",
        formal_basis=(
            "Socratic method, constructivism, zone of proximal development"
        ),
        classical_parallel="Geometry",
        description="Pedagogical dialectic, community learning, salons",
    ),
    Dialect.SIGNAL_PROPAGATION: DialectProfile(
        dialect=Dialect.SIGNAL_PROPAGATION,
        organ_key="VII", organ_name="Kerygma",
        translation_role=(
            "The Broadcast — structure-preserving projection to external"
        ),
        formal_basis="Information theory (Shannon 1948)",
        classical_parallel="Astronomy",
        description="Signal propagation, POSSE distribution, social syndication",
    ),
    Dialect.SELF_WITNESSING: DialectProfile(
        dialect=Dialect.SELF_WITNESSING,
        organ_key="META", organ_name="Meta",
        translation_role=(
            "The Witness — proves all translations compose without loss"
        ),
        formal_basis="Gödel 1931, fixed-point theorems, self-referential systems",
        classical_parallel="The Eighth Art",
        description="Self-witnessing, constitutional proof, testament of unity",
    ),
}


def dialect_for_organ(organ_key: str) -> Dialect:
    """Return the dialect for an organ key. Raises KeyError if unknown."""
    return _ORGAN_TO_DIALECT[organ_key]


def organ_for_dialect(dialect: Dialect) -> str:
    """Return the organ key for a dialect."""
    return _DIALECT_TO_ORGAN[dialect]


def dialect_profile(dialect: Dialect) -> DialectProfile:
    """Return the full profile for a dialect."""
    return _PROFILES[dialect]


def classical_parallel(dialect: Dialect) -> str:
    """Return the classical liberal arts parallel for a dialect."""
    return _PROFILES[dialect].classical_parallel


def all_dialects() -> list[Dialect]:
    """Return all eight dialects in organ order."""
    return [
        _ORGAN_TO_DIALECT[k]
        for k in ["I", "II", "III", "IV", "V", "VI", "VII", "META"]
    ]
