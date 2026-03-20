"""Content generation from the translation matrix.

Each of the 28 translation pairs can produce a publishable artifact:
an essay, a visualization, or a testament narrative. This module
generates essay outlines, titles, and draft content from the
empirical correspondence data.
"""

from __future__ import annotations

from dataclasses import dataclass

from organvm_engine.trivium.dialects import (
    dialect_profile,
    organ_for_dialect,
)
from organvm_engine.trivium.taxonomy import (
    TranslationPair,
    TranslationTier,
    all_pairs,
)


@dataclass
class TranslationEssay:
    """A publishable essay derived from a translation pair."""

    pair: TranslationPair
    title: str
    subtitle: str
    thesis: str
    outline: list[str]
    evidence_summary: str
    target_words: int = 3000


def generate_essay_outline(pair: TranslationPair) -> TranslationEssay:
    """Generate a publishable essay outline from a translation pair."""
    src = dialect_profile(pair.source)
    tgt = dialect_profile(pair.target)
    src_key = organ_for_dialect(pair.source)
    tgt_key = organ_for_dialect(pair.target)

    title = _generate_title(src, tgt, pair)
    subtitle = (
        f"How {src.organ_name} ({src_key}) and "
        f"{tgt.organ_name} ({tgt_key}) speak the same language"
    )
    thesis = (
        f"The relationship between {src.dialect.value.replace('_', ' ')} "
        f"and {tgt.dialect.value.replace('_', ' ')} is not analogy but "
        f"structural isomorphism — a {pair.tier.value}-tier translation "
        f"with {pair.preservation.name.lower()} preservation."
    )

    outline = [
        f"1. Introduction: {pair.description}",
        f"2. {src.organ_name} speaks {src.classical_parallel} — {src.translation_role}",
        f"3. {tgt.organ_name} speaks {tgt.classical_parallel} — {tgt.translation_role}",
        f"4. The Translation: {pair.evidence}",
        "5. Empirical Evidence from ORGANVM (correspondences from live registry)",
        "6. Historical Precedent (from the 2,400-year genealogy)",
        f"7. What This Proves: the isomorphism is {pair.preservation.name.lower()}",
        "8. Implications for practice",
    ]

    return TranslationEssay(
        pair=pair,
        title=title,
        subtitle=subtitle,
        thesis=thesis,
        outline=outline,
        evidence_summary=pair.evidence,
    )


def generate_all_outlines(
    min_tier: TranslationTier = TranslationTier.ANALOGICAL,
) -> list[TranslationEssay]:
    """Generate essay outlines for all pairs at or above minimum tier."""
    tier_order = {
        TranslationTier.FORMAL: 0,
        TranslationTier.STRUCTURAL: 1,
        TranslationTier.ANALOGICAL: 2,
        TranslationTier.EMERGENT: 3,
    }
    threshold = tier_order[min_tier]

    essays = []
    for pair in all_pairs():
        if tier_order[pair.tier] <= threshold:
            essays.append(generate_essay_outline(pair))

    return sorted(essays, key=lambda e: tier_order[e.pair.tier])


def render_essay_catalog(essays: list[TranslationEssay]) -> str:
    """Render a markdown catalog of all essay outlines."""
    lines = [
        "# Trivium Essay Catalog — Dialectica Universalis",
        "",
        f"*{len(essays)} publishable essays derived from the translation matrix.*",
        "",
    ]

    current_tier = None
    for essay in essays:
        if essay.pair.tier != current_tier:
            current_tier = essay.pair.tier
            lines.append(f"## Tier: {current_tier.value.title()}")
            lines.append("")

        lines.append(f"### {essay.title}")
        lines.append(f"*{essay.subtitle}*")
        lines.append("")
        lines.append(f"**Thesis:** {essay.thesis}")
        lines.append("")
        lines.append("**Outline:**")
        for item in essay.outline:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_TITLE_PATTERNS = {
    TranslationTier.FORMAL: "The Proof That {a} IS {b}",
    TranslationTier.STRUCTURAL: "How {a} Becomes {b}",
    TranslationTier.ANALOGICAL: "Where {a} Meets {b}",
    TranslationTier.EMERGENT: "The Emerging Bridge: {a} and {b}",
}


def _generate_title(
    src: object, tgt: object, pair: TranslationPair,
) -> str:
    """Generate an essay title from the pair metadata."""
    pattern = _TITLE_PATTERNS.get(pair.tier, "{a} and {b}")
    # Use the classical parallels as the title elements
    src_name = getattr(src, "classical_parallel", "Source")
    tgt_name = getattr(tgt, "classical_parallel", "Target")
    return pattern.format(a=src_name, b=tgt_name)
