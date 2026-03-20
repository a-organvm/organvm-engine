"""Inter-dialect translation evidence collector.

Combines detector correspondences with taxonomy pair metadata to produce
translation evidence records. Each record aggregates the raw correspondences
into a scored assessment with prose summary suitable for testament rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.trivium.detector import (
    scan_organ_pair,
)
from organvm_engine.trivium.dialects import (
    Dialect,
    dialect_for_organ,
    dialect_profile,
    organ_for_dialect,
)
from organvm_engine.trivium.taxonomy import (
    TranslationPair,
    all_pairs,
)


@dataclass
class TranslationEvidence:
    """Aggregate evidence for a single inter-dialect translation."""

    source: Dialect
    target: Dialect
    correspondences: list[dict] = field(default_factory=list)
    aggregate_strength: float = 0.0
    preservation_assessment: str = "untested"
    summary: str = ""

    @property
    def source_organ(self) -> str:
        return organ_for_dialect(self.source)

    @property
    def target_organ(self) -> str:
        return organ_for_dialect(self.target)


def collect_evidence(
    organ_a: str,
    organ_b: str,
    registry_path: Path | None = None,
    registry: dict | None = None,
) -> TranslationEvidence:
    """Collect translation evidence between two organs.

    Runs the detector scan, then enriches with taxonomy metadata.
    """
    dialect_a = dialect_for_organ(organ_a)
    dialect_b = dialect_for_organ(organ_b)

    # Run the detector
    report = scan_organ_pair(
        organ_a, organ_b,
        registry=registry,
        registry_path=registry_path,
    )

    correspondences = report.get("correspondences", [])
    avg_strength = report.get("avg_strength", 0.0)

    # Find the taxonomy pair for context
    pair = _find_taxonomy_pair(dialect_a, dialect_b)
    preservation = _assess_preservation(correspondences, pair)

    summary = _build_summary(
        organ_a, organ_b, correspondences, avg_strength, pair,
    )

    return TranslationEvidence(
        source=dialect_a,
        target=dialect_b,
        correspondences=correspondences,
        aggregate_strength=avg_strength,
        preservation_assessment=preservation,
        summary=summary,
    )


def translation_matrix(
    registry_path: Path | None = None,
    registry: dict | None = None,
) -> dict[tuple[Dialect, Dialect], TranslationEvidence]:
    """Compute the full 28-pair translation evidence matrix."""
    from itertools import combinations

    organ_keys = ["I", "II", "III", "IV", "V", "VI", "VII", "META"]

    # Load registry once if path given
    if registry is None and registry_path is not None:
        import json
        with registry_path.open() as f:
            registry = json.load(f)

    matrix: dict[tuple[Dialect, Dialect], TranslationEvidence] = {}
    for a, b in combinations(organ_keys, 2):
        ev = collect_evidence(a, b, registry=registry)
        matrix[(dialect_for_organ(a), dialect_for_organ(b))] = ev

    return matrix


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_taxonomy_pair(a: Dialect, b: Dialect) -> TranslationPair | None:
    """Find the taxonomy pair for two dialects."""
    key = frozenset([a, b])
    for p in all_pairs():
        if frozenset([p.source, p.target]) == key:
            return p
    return None


def _assess_preservation(
    correspondences: list[dict],
    pair: TranslationPair | None,
) -> str:
    """Assess the preservation degree from evidence + taxonomy."""
    if pair is None:
        return "untested"

    # Start with the taxonomy's declared preservation
    declared = pair.preservation.name.lower()

    # If we have strong empirical evidence, note it
    if not correspondences:
        return f"{declared} (declared, no empirical data)"

    avg = sum(c.get("strength", 0) for c in correspondences) / len(correspondences)
    if avg >= 0.7:
        return f"{declared} (confirmed: avg_strength={avg:.2f})"
    if avg >= 0.3:
        return f"{declared} (partial: avg_strength={avg:.2f})"
    return f"{declared} (weak: avg_strength={avg:.2f})"


def _build_summary(
    organ_a: str,
    organ_b: str,
    correspondences: list[dict],
    avg_strength: float,
    pair: TranslationPair | None,
) -> str:
    """Build a prose summary for testament rendering."""
    prof_a = dialect_profile(dialect_for_organ(organ_a))
    prof_b = dialect_profile(dialect_for_organ(organ_b))

    parts: list[str] = []
    parts.append(
        f"**{prof_a.organ_name} ({organ_a}) ↔ "
        f"{prof_b.organ_name} ({organ_b})**",
    )

    if pair:
        parts.append(f"Tier: {pair.tier.value}. {pair.description}")

    if correspondences:
        by_type: dict[str, int] = {}
        for c in correspondences:
            t = c.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        type_str = ", ".join(
            f"{count} {t}" for t, count in sorted(by_type.items())
        )
        parts.append(
            f"Evidence: {len(correspondences)} correspondences "
            f"({type_str}), avg strength {avg_strength:.2f}.",
        )
    else:
        parts.append("No empirical correspondences detected yet.")

    return " ".join(parts)
