"""Seed graph edge declarations for isomorphism surfaces.

Generates edge declarations compatible with seed.yaml produces/consumes
format. Each edge represents a detected translation surface between
two organs, enriched with tier and preservation metadata.
"""

from __future__ import annotations

from organvm_engine.trivium.dialects import organ_for_dialect
from organvm_engine.trivium.taxonomy import (
    TranslationPair,
    TranslationTier,
    all_pairs,
    pairs_by_tier,
)


def isomorphism_edge(pair: TranslationPair) -> dict:
    """Generate a seed-graph-compatible edge for a translation pair.

    Returns a dict matching the seed.yaml produces/consumes format:
    {type, target_organ, description, metadata}.
    """
    return {
        "type": "isomorphism-surface",
        "source_organ": organ_for_dialect(pair.source),
        "target_organ": organ_for_dialect(pair.target),
        "description": pair.description,
        "metadata": {
            "tier": pair.tier.value,
            "preservation": pair.preservation.name.lower(),
            "evidence": pair.evidence,
        },
    }


def trivium_edges(
    min_tier: TranslationTier = TranslationTier.ANALOGICAL,
) -> list[dict]:
    """Generate all isomorphism edges at or above a minimum tier.

    Default includes Tier 1 (formal), Tier 2 (structural), and
    Tier 3 (analogical). Tier 4 (emergent) excluded by default
    since those translations are not yet characterized.
    """
    tier_order = {
        TranslationTier.FORMAL: 0,
        TranslationTier.STRUCTURAL: 1,
        TranslationTier.ANALOGICAL: 2,
        TranslationTier.EMERGENT: 3,
    }
    threshold = tier_order[min_tier]

    return [
        isomorphism_edge(p)
        for p in all_pairs()
        if tier_order[p.tier] <= threshold
    ]


def formal_edges() -> list[dict]:
    """Return only Tier 1 (formally proven) isomorphism edges."""
    return [isomorphism_edge(p) for p in pairs_by_tier(TranslationTier.FORMAL)]
