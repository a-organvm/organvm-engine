"""Structural correspondence detection between organs.

Scans organ pairs for naming parallels, structural similarities,
functional correspondences, and semantic resonance. Each detection
yields a Correspondence with type, strength, and evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import Any


@unique
class CorrespondenceType(Enum):
    """Kind of structural correspondence detected."""

    NAMING = "naming"            # parallel repo/module names across organs
    STRUCTURAL = "structural"    # similar counts, depths, formation patterns
    FUNCTIONAL = "functional"    # parallel produces/consumes signal types
    SEMANTIC = "semantic"        # description similarity


@dataclass(frozen=True)
class Correspondence:
    """A single detected structural correspondence between two organs."""

    correspondence_type: CorrespondenceType
    source_organ: str
    target_organ: str
    source_entity: str
    target_entity: str
    evidence: str
    strength: float  # 0.0–1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be 0.0–1.0, got {self.strength}")


def detect_naming_isomorphisms(
    organ_a_repos: list[dict[str, Any]],
    organ_b_repos: list[dict[str, Any]],
) -> list[Correspondence]:
    """Detect repos with parallel naming patterns across two organs.

    Looks for shared stems in double-hyphen names (e.g., "recursive-engine"
    in ORGAN-I parallels "recursive-tool" in ORGAN-III).
    """
    if not organ_a_repos or not organ_b_repos:
        return []

    correspondences: list[Correspondence] = []

    for a in organ_a_repos:
        a_name = a.get("name", "")
        a_stems = _extract_stems(a_name)
        if not a_stems:
            continue

        for b in organ_b_repos:
            b_name = b.get("name", "")
            b_stems = _extract_stems(b_name)
            if not b_stems:
                continue

            shared = a_stems & b_stems
            if shared:
                strength = len(shared) / max(len(a_stems), len(b_stems))
                correspondences.append(Correspondence(
                    correspondence_type=CorrespondenceType.NAMING,
                    source_organ=a.get("org", ""),
                    target_organ=b.get("org", ""),
                    source_entity=a_name,
                    target_entity=b_name,
                    evidence=f"Shared stems: {', '.join(sorted(shared))}",
                    strength=min(strength, 1.0),
                ))

    return correspondences


def detect_structural_correspondences(
    organ_a_repos: list[dict[str, Any]],
    organ_b_repos: list[dict[str, Any]],
) -> list[Correspondence]:
    """Detect structural parallels: similar repo counts, tier distributions."""
    if not organ_a_repos or not organ_b_repos:
        return []

    correspondences: list[Correspondence] = []

    # Compare tier distributions
    a_tiers = _tier_distribution(organ_a_repos)
    b_tiers = _tier_distribution(organ_b_repos)
    all_tiers = set(a_tiers) | set(b_tiers)

    if all_tiers:
        match_count = sum(
            1 for t in all_tiers
            if a_tiers.get(t, 0) > 0 and b_tiers.get(t, 0) > 0
        )
        strength = match_count / len(all_tiers)
        if strength > 0:
            correspondences.append(Correspondence(
                correspondence_type=CorrespondenceType.STRUCTURAL,
                source_organ=organ_a_repos[0].get("org", ""),
                target_organ=organ_b_repos[0].get("org", ""),
                source_entity="tier_distribution",
                target_entity="tier_distribution",
                evidence=(
                    f"Shared tier categories: {match_count}/{len(all_tiers)}"
                ),
                strength=strength,
            ))

    # Compare repo count similarity (closer counts = higher strength)
    a_count = len(organ_a_repos)
    b_count = len(organ_b_repos)
    if a_count > 0 and b_count > 0:
        ratio = min(a_count, b_count) / max(a_count, b_count)
        if ratio > 0.3:
            correspondences.append(Correspondence(
                correspondence_type=CorrespondenceType.STRUCTURAL,
                source_organ=organ_a_repos[0].get("org", ""),
                target_organ=organ_b_repos[0].get("org", ""),
                source_entity=f"count:{a_count}",
                target_entity=f"count:{b_count}",
                evidence=f"Repo count ratio: {ratio:.2f}",
                strength=ratio,
            ))

    return correspondences


def detect_functional_correspondences(
    organ_a_repos: list[dict[str, Any]],
    organ_b_repos: list[dict[str, Any]],
) -> list[Correspondence]:
    """Detect repos with parallel dependency patterns."""
    if not organ_a_repos or not organ_b_repos:
        return []

    correspondences: list[Correspondence] = []

    # Look for dependency-linked pairs
    a_names = {r.get("name", "") for r in organ_a_repos}
    for b in organ_b_repos:
        deps = b.get("dependencies", [])
        for dep in deps:
            if dep in a_names:
                correspondences.append(Correspondence(
                    correspondence_type=CorrespondenceType.FUNCTIONAL,
                    source_organ=organ_a_repos[0].get("org", ""),
                    target_organ=b.get("org", ""),
                    source_entity=dep,
                    target_entity=b.get("name", ""),
                    evidence=f"Direct dependency: {b.get('name', '')} → {dep}",
                    strength=0.9,
                ))

    return correspondences


def detect_semantic_correspondences(
    organ_a_repos: list[dict[str, Any]],
    organ_b_repos: list[dict[str, Any]],
) -> list[Correspondence]:
    """Detect repos with similar descriptions (keyword overlap)."""
    if not organ_a_repos or not organ_b_repos:
        return []

    correspondences: list[Correspondence] = []

    for a in organ_a_repos:
        a_words = _description_keywords(a.get("description", ""))
        if not a_words:
            continue

        for b in organ_b_repos:
            b_words = _description_keywords(b.get("description", ""))
            if not b_words:
                continue

            shared = a_words & b_words
            if len(shared) >= 2:
                strength = len(shared) / max(len(a_words), len(b_words))
                correspondences.append(Correspondence(
                    correspondence_type=CorrespondenceType.SEMANTIC,
                    source_organ=a.get("org", ""),
                    target_organ=b.get("org", ""),
                    source_entity=a.get("name", ""),
                    target_entity=b.get("name", ""),
                    evidence=f"Shared keywords: {', '.join(sorted(shared))}",
                    strength=min(strength, 1.0),
                ))

    return correspondences


def scan_organ_pair(
    organ_a_key: str,
    organ_b_key: str,
    registry: dict[str, Any] | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Full scan of structural correspondences between two organs.

    Either pass a pre-loaded registry dict, or a registry_path to load.
    Returns structured report with all detected correspondences.
    """
    if registry is None and registry_path is not None:
        import json
        with registry_path.open() as f:
            registry = json.load(f)
    if registry is None:
        return {
            "organ_a": organ_a_key,
            "organ_b": organ_b_key,
            "correspondences": [],
            "summary": "No registry data available",
        }

    a_repos = _repos_for_organ(organ_a_key, registry)
    b_repos = _repos_for_organ(organ_b_key, registry)

    all_corr: list[Correspondence] = []
    all_corr.extend(detect_naming_isomorphisms(a_repos, b_repos))
    all_corr.extend(detect_structural_correspondences(a_repos, b_repos))
    all_corr.extend(detect_functional_correspondences(a_repos, b_repos))
    all_corr.extend(detect_semantic_correspondences(a_repos, b_repos))

    by_type: dict[str, int] = {}
    for c in all_corr:
        by_type[c.correspondence_type.value] = (
            by_type.get(c.correspondence_type.value, 0) + 1
        )

    avg_strength = (
        sum(c.strength for c in all_corr) / len(all_corr)
        if all_corr else 0.0
    )

    return {
        "organ_a": organ_a_key,
        "organ_b": organ_b_key,
        "correspondences": [
            {
                "type": c.correspondence_type.value,
                "source_entity": c.source_entity,
                "target_entity": c.target_entity,
                "evidence": c.evidence,
                "strength": c.strength,
            }
            for c in all_corr
        ],
        "by_type": by_type,
        "count": len(all_corr),
        "avg_strength": round(avg_strength, 3),
        "summary": (
            f"{len(all_corr)} correspondences detected "
            f"(avg strength {avg_strength:.2f})"
        ),
    }


def scan_all_pairs(
    registry: dict[str, Any] | None = None,
    registry_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Scan all 28 organ pairs for structural correspondences."""
    from itertools import combinations

    organ_keys = ["I", "II", "III", "IV", "V", "VI", "VII", "META"]
    results: list[dict[str, Any]] = []
    for a, b in combinations(organ_keys, 2):
        report = scan_organ_pair(
            a, b, registry=registry, registry_path=registry_path,
        )
        results.append(report)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "for", "in", "of", "to", "with", "is",
    "are", "was", "were", "be", "been", "being", "at", "by", "from", "as",
})


def _extract_stems(name: str) -> set[str]:
    """Extract meaningful word stems from a repo name."""
    parts = re.split(r"--|[-_]", name)
    return {p.lower() for p in parts if len(p) > 2 and p.lower() not in _STOP_WORDS}


def _tier_distribution(repos: list[dict[str, Any]]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for r in repos:
        tier = r.get("tier", "unknown")
        dist[tier] = dist.get(tier, 0) + 1
    return dist


def _description_keywords(desc: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]+", desc.lower())
    return {w for w in words if len(w) > 3 and w not in _STOP_WORDS}


def _repos_for_organ(organ_key: str, registry: dict[str, Any]) -> list[dict]:
    """Extract repos for an organ from registry, handling key formats."""
    organs = registry.get("organs", {})

    # Try direct key formats
    for key_format in [
        organ_key,
        f"ORGAN-{organ_key}",
        "META-ORGANVM" if organ_key == "META" else None,
    ]:
        if key_format and key_format in organs:
            return organs[key_format].get("repositories", [])

    return []
