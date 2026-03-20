"""Data source adapters for trivium testament rendering.

Each function extracts structured data from the trivium module,
returning dicts suitable for passing to testament renderers.
All imports are deferred to avoid circular dependencies.
"""

from __future__ import annotations

from pathlib import Path


def isomorphism_data(
    registry_path: Path | None = None,
) -> dict:
    """Extract cross-organ isomorphism data for testament rendering.

    Returns dict with keys: matrix_summary, tier_counts, strongest_pairs,
    total_correspondences, total_pairs.
    """
    from organvm_engine.trivium.taxonomy import (
        TranslationTier,
        pairs_by_tier,
    )
    from organvm_engine.trivium.translator import translation_matrix

    matrix = translation_matrix(registry_path=registry_path)

    tier_counts = {
        tier.value: len(pairs_by_tier(tier))
        for tier in TranslationTier
    }

    total_corr = sum(
        len(ev.correspondences) for ev in matrix.values()
    )

    with_evidence = sum(
        1 for ev in matrix.values() if ev.correspondences
    )

    avg_strength = (
        sum(ev.aggregate_strength for ev in matrix.values()) / len(matrix)
        if matrix else 0.0
    )

    # Top 5 strongest pairs
    ranked = sorted(
        matrix.values(),
        key=lambda ev: ev.aggregate_strength,
        reverse=True,
    )
    strongest = [
        {
            "source_organ": ev.source_organ,
            "target_organ": ev.target_organ,
            "strength": ev.aggregate_strength,
            "correspondences": len(ev.correspondences),
            "preservation": ev.preservation_assessment,
        }
        for ev in ranked[:5]
    ]

    return {
        "total_pairs": len(matrix),
        "pairs_with_evidence": with_evidence,
        "total_correspondences": total_corr,
        "avg_strength": round(avg_strength, 3),
        "tier_counts": tier_counts,
        "strongest_pairs": strongest,
    }


def dialect_data() -> dict:
    """Extract dialect enumeration data for rendering.

    Returns dict with keys: dialects (list of profile dicts), count.
    """
    from organvm_engine.trivium.dialects import all_dialects, dialect_profile

    dialects = []
    for d in all_dialects():
        p = dialect_profile(d)
        dialects.append({
            "dialect": d.value,
            "organ_key": p.organ_key,
            "organ_name": p.organ_name,
            "translation_role": p.translation_role,
            "formal_basis": p.formal_basis,
            "classical_parallel": p.classical_parallel,
            "description": p.description,
        })

    return {"dialects": dialects, "count": len(dialects)}
