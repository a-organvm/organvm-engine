"""Translation taxonomy — the 28 inter-dialect translation pairs.

Defines the complete graph K₈ of organ-to-organ translations, classifying
each by tier (formal evidence level) and preservation degree (how much
structure survives the translation). Provides composition and graph queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from itertools import combinations

from organvm_engine.trivium.dialects import Dialect, all_dialects, organ_for_dialect


@unique
class TranslationTier(Enum):
    """Evidence tier for an inter-dialect translation."""

    FORMAL = "formal"            # mathematical proof exists
    STRUCTURAL = "structural"    # empirical structural isomorphism
    ANALOGICAL = "analogical"    # strong structural parallel, no formal proof
    EMERGENT = "emergent"        # translation surface exists, not yet characterized


@unique
class PreservationDegree(Enum):
    """How much structure survives an inter-dialect translation."""

    ISOMORPHISM = 4    # bijective, invertible
    HOMOMORPHISM = 3   # structure-preserving, not necessarily invertible
    PROJECTION = 2     # information-reducing but content-preserving
    RESONANCE = 1      # structural similarity without formal mapping


@dataclass(frozen=True)
class TranslationPair:
    """A single inter-dialect translation with metadata."""

    source: Dialect
    target: Dialect
    tier: TranslationTier
    preservation: PreservationDegree
    evidence: str
    description: str


# ---------------------------------------------------------------------------
# The 28 translation pairs — K₈ complete graph
# ---------------------------------------------------------------------------

_TIER_1: list[TranslationPair] = [
    TranslationPair(
        Dialect.FORMAL_LOGIC, Dialect.EXECUTABLE_ALGORITHM,
        TranslationTier.FORMAL, PreservationDegree.ISOMORPHISM,
        "Curry-Howard correspondence (Howard 1969)",
        "Proofs ARE programs. The foundational isomorphism.",
    ),
    TranslationPair(
        Dialect.FORMAL_LOGIC, Dialect.GOVERNANCE_LOGIC,
        TranslationTier.FORMAL, PreservationDegree.ISOMORPHISM,
        "SPEC-002 propositions-as-types for governance (Martin-Löf 1984)",
        "Governance rules ARE type-theoretic propositions.",
    ),
    TranslationPair(
        Dialect.FORMAL_LOGIC, Dialect.SELF_WITNESSING,
        TranslationTier.FORMAL, PreservationDegree.HOMOMORPHISM,
        "Gödel numbering (Gödel 1931); fixed-point theorems",
        "A formal system encoding itself. Self-reference as structure.",
    ),
]

_TIER_2: list[TranslationPair] = [
    TranslationPair(
        Dialect.AESTHETIC_FORM, Dialect.EXECUTABLE_ALGORITHM,
        TranslationTier.STRUCTURAL, PreservationDegree.HOMOMORPHISM,
        "Generative art = algorithm + aesthetic constraint",
        "Art IS constrained computation. Algorithm IS structured expression.",
    ),
    TranslationPair(
        Dialect.EXECUTABLE_ALGORITHM, Dialect.SIGNAL_PROPAGATION,
        TranslationTier.STRUCTURAL, PreservationDegree.PROJECTION,
        "Serialization as structure-preserving projection (Shannon 1948)",
        "Syndication IS lossy compilation. Broadcast preserves intent.",
    ),
    TranslationPair(
        Dialect.GOVERNANCE_LOGIC, Dialect.NATURAL_RHETORIC,
        TranslationTier.STRUCTURAL, PreservationDegree.HOMOMORPHISM,
        "Governance rules as speech acts (Austin 1962, Searle 1969)",
        "Rules ARE performative utterances. Governance IS rhetoric formalized.",
    ),
    TranslationPair(
        Dialect.GOVERNANCE_LOGIC, Dialect.SELF_WITNESSING,
        TranslationTier.STRUCTURAL, PreservationDegree.HOMOMORPHISM,
        "Constitutional self-observation (SPEC-011 Meta-Evolution)",
        "The constitution observes its own enforcement.",
    ),
    TranslationPair(
        Dialect.NATURAL_RHETORIC, Dialect.PEDAGOGICAL_DIALECTIC,
        TranslationTier.STRUCTURAL, PreservationDegree.HOMOMORPHISM,
        "Teaching as bidirectional translation (Vygotsky 1978)",
        "Pedagogy IS the practice of inter-dialect translation.",
    ),
]

_TIER_3: list[TranslationPair] = [
    TranslationPair(
        Dialect.AESTHETIC_FORM, Dialect.NATURAL_RHETORIC,
        TranslationTier.ANALOGICAL, PreservationDegree.PROJECTION,
        "Both transform internal structure into communicable form",
        "Art and discourse share the act of externalization.",
    ),
    TranslationPair(
        Dialect.AESTHETIC_FORM, Dialect.PEDAGOGICAL_DIALECTIC,
        TranslationTier.ANALOGICAL, PreservationDegree.RESONANCE,
        "Performance IS communal experience (Schechner 2013)",
        "Art enacts community. Community enacts art.",
    ),
    TranslationPair(
        Dialect.EXECUTABLE_ALGORITHM, Dialect.PEDAGOGICAL_DIALECTIC,
        TranslationTier.ANALOGICAL, PreservationDegree.RESONANCE,
        "Open source IS community engineering",
        "Code shared is knowledge shared.",
    ),
    TranslationPair(
        Dialect.PEDAGOGICAL_DIALECTIC, Dialect.SIGNAL_PROPAGATION,
        TranslationTier.ANALOGICAL, PreservationDegree.PROJECTION,
        "Community generates its own broadcasts",
        "Learning communities naturally syndicate.",
    ),
]


def _build_emergent_pairs() -> list[TranslationPair]:
    """Generate Tier 4 pairs for all remaining combinations."""
    declared = set()
    for p in _TIER_1 + _TIER_2 + _TIER_3:
        declared.add(frozenset([p.source, p.target]))

    emergent: list[TranslationPair] = []
    for a, b in combinations(all_dialects(), 2):
        key = frozenset([a, b])
        if key not in declared:
            emergent.append(TranslationPair(
                a, b,
                TranslationTier.EMERGENT, PreservationDegree.RESONANCE,
                "Translation surface exists but not yet characterized",
                f"{organ_for_dialect(a)}↔{organ_for_dialect(b)}: emergent.",
            ))
    return emergent


_ALL_PAIRS: list[TranslationPair] | None = None


def _ensure_pairs() -> list[TranslationPair]:
    global _ALL_PAIRS  # noqa: PLW0603
    if _ALL_PAIRS is None:
        _ALL_PAIRS = _TIER_1 + _TIER_2 + _TIER_3 + _build_emergent_pairs()
    return _ALL_PAIRS


def all_pairs() -> list[TranslationPair]:
    """Return all 28 translation pairs (K₈ complete graph)."""
    return list(_ensure_pairs())


def tier_1_pairs() -> list[TranslationPair]:
    """Return only Tier 1 (formally grounded) pairs."""
    return list(_TIER_1)


def tier_2_pairs() -> list[TranslationPair]:
    """Return only Tier 2 (structurally grounded) pairs."""
    return list(_TIER_2)


def pairs_for_organ(dialect: Dialect) -> list[TranslationPair]:
    """Return all 7 pairs involving a given dialect."""
    return [
        p for p in _ensure_pairs()
        if dialect in (p.source, p.target)
    ]


def pairs_by_tier(tier: TranslationTier) -> list[TranslationPair]:
    """Return all pairs classified at a given tier."""
    return [p for p in _ensure_pairs() if p.tier == tier]


def compose_translation(
    a: Dialect, via: Dialect, b: Dialect,
) -> TranslationPair | None:
    """Compose two translations: a→via and via→b → a→b.

    Returns a synthetic TranslationPair with the weaker of the two
    preservation degrees, or None if either leg doesn't exist.
    """
    leg1 = _find_pair(a, via)
    leg2 = _find_pair(via, b)
    if leg1 is None or leg2 is None:
        return None

    # Composed preservation is the minimum of the two legs
    composed_preservation = min(
        leg1.preservation, leg2.preservation,
        key=lambda p: p.value,
    )
    # Composed tier is the weakest of the two legs
    tier_order = {
        TranslationTier.FORMAL: 0,
        TranslationTier.STRUCTURAL: 1,
        TranslationTier.ANALOGICAL: 2,
        TranslationTier.EMERGENT: 3,
    }
    composed_tier = max(
        leg1.tier, leg2.tier,
        key=lambda t: tier_order[t],
    )
    via_key = organ_for_dialect(via)
    return TranslationPair(
        a, b, composed_tier, composed_preservation,
        f"Composed via {via_key}: ({leg1.evidence}) + ({leg2.evidence})",
        f"Composition: {organ_for_dialect(a)}→{via_key}→{organ_for_dialect(b)}",
    )


def translation_graph() -> dict:
    """Return the full translation graph as a dict with nodes and edges."""
    pairs = _ensure_pairs()
    nodes = [
        {"dialect": d.value, "organ": organ_for_dialect(d)}
        for d in all_dialects()
    ]
    edges = [
        {
            "source": p.source.value,
            "target": p.target.value,
            "tier": p.tier.value,
            "preservation": p.preservation.name.lower(),
        }
        for p in pairs
    ]
    return {"nodes": nodes, "edges": edges}


def _find_pair(a: Dialect, b: Dialect) -> TranslationPair | None:
    """Find the pair connecting two dialects (order-independent)."""
    key = frozenset([a, b])
    for p in _ensure_pairs():
        if frozenset([p.source, p.target]) == key:
            return p
    return None
