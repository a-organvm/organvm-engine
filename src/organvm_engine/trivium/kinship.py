"""Network testament kinship lens integration.

Connects trivium dialect correspondences to the network testament's
kinship lens. Each organ's strongest translation partners generate
kinship mirror entries for network-map.yaml.
"""

from __future__ import annotations

from organvm_engine.trivium.dialects import (
    dialect_for_organ,
    dialect_profile,
    organ_for_dialect,
)
from organvm_engine.trivium.taxonomy import (
    TranslationTier,
    pairs_for_organ,
)


def kinship_from_dialect(organ_key: str) -> list[dict]:
    """Generate kinship mirror entries from dialect correspondences.

    Returns entries suitable for the kinship lens in network-map.yaml.
    Only includes Tier 1-3 pairs (formal, structural, analogical).
    """
    dialect = dialect_for_organ(organ_key)
    pairs = pairs_for_organ(dialect)

    entries: list[dict] = []
    for p in pairs:
        if p.tier == TranslationTier.EMERGENT:
            continue

        # The "other" organ in this pair
        other = p.target if p.source == dialect else p.source
        other_key = organ_for_dialect(other)
        other_prof = dialect_profile(other)

        entries.append({
            "project": f"ORGANVM ORGAN-{other_key} ({other_prof.organ_name})",
            "platform": "internal",
            "relevance": (
                f"Trivium {p.tier.value} translation: {p.description}"
            ),
            "engagement": ["presence"],
            "tags": [
                "trivium",
                f"tier-{p.tier.value}",
                f"preservation-{p.preservation.name.lower()}",
            ],
        })

    return entries


def enrich_kinship_lens(
    existing_kinship: list[dict],
    organ_key: str,
) -> list[dict]:
    """Add trivium-derived kinship entries to existing kinship list.

    Deduplicates by project name. Existing entries take precedence.
    """
    existing_projects = {e.get("project", "") for e in existing_kinship}
    new_entries = kinship_from_dialect(organ_key)

    merged = list(existing_kinship)
    for entry in new_entries:
        if entry["project"] not in existing_projects:
            merged.append(entry)
            existing_projects.add(entry["project"])

    return merged
