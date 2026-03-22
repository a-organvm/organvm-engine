"""The Mirror — compares intentions to actual reality.

Analyzes drift between what was intended (prompts/intentions) and what
actually happened (commits in the fossil record).  Classifies the
drift pattern by Jungian archetype.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

from organvm_engine.fossil.archivist import Intention
from organvm_engine.fossil.stratum import Archetype, FossilRecord

# ---------------------------------------------------------------------------
# Organ reference patterns
# ---------------------------------------------------------------------------

# Explicit "ORGAN-X" references
_ORGAN_PATTERN = re.compile(r"ORGAN[- ]([IVX]+|\d+)", re.IGNORECASE)

# Named organ references → organ short key
_ORGAN_NAMES: dict[str, str] = {
    "theoria": "I",
    "poiesis": "II",
    "ergon": "III",
    "taxis": "IV",
    "logos": "V",
    "koinonia": "VI",
    "kerygma": "VII",
    "meta": "META",
}

# Keyword → organ mapping (broader terms)
_KEYWORD_ORGANS: dict[str, str] = {
    "research": "I",
    "theory": "I",
    "formal": "I",
    "art": "II",
    "generative": "II",
    "creative": "II",
    "performance": "II",
    "product": "III",
    "saas": "III",
    "commercial": "III",
    "orchestration": "IV",
    "governance": "IV",
    "agent": "IV",
    "essay": "V",
    "editorial": "V",
    "discourse": "V",
    "community": "VI",
    "reading": "VI",
    "salon": "VI",
    "distribution": "VII",
    "syndication": "VII",
    "broadcast": "VII",
    "registry": "META",
    "dashboard": "META",
    "engine": "META",
}

# Pattern for repo-like names (contains double-hyphen or "organvm-")
_REPO_PATTERN = re.compile(r"\b[\w]+-[-\w]*--[-\w]+\b|\borganvm[-\w]+\b", re.IGNORECASE)


@dataclass
class DriftRecord:
    """Comparison between an intention and subsequent reality."""

    intention_id: str
    intended_scope: list[str]  # repos/organs mentioned in prompt
    actual_scope: list[str]  # repos/organs in commits after intention
    convergence: float  # Jaccard of intended & actual
    mutations: list[str]  # actual - intended (emerged, unplanned)
    shadows: list[str]  # intended - actual (avoided)
    drift_archetype: Archetype  # classification of the drift pattern


# ---------------------------------------------------------------------------
# Scope extraction
# ---------------------------------------------------------------------------


def extract_scope_from_text(text: str) -> list[str]:
    """Extract repo names and organ references from a prompt.

    Looks for:
    - Explicit organ references: "ORGAN-I", "organ I"
    - Named organs: "theoria", "poiesis", etc.
    - Repo-like patterns: double-hyphen names, "organvm-*"
    - Keywords that map to organs: "research" -> I, "art" -> II, etc.
    """
    scope: list[str] = []
    text_lower = text.lower()

    # Explicit ORGAN-N references
    for match in _ORGAN_PATTERN.finditer(text):
        organ_id = match.group(1).upper()
        if organ_id not in scope:
            scope.append(organ_id)

    # Named organ references
    for name, organ_key in _ORGAN_NAMES.items():
        if name in text_lower and organ_key not in scope:
            scope.append(organ_key)

    # Repo-like patterns
    for match in _REPO_PATTERN.finditer(text):
        repo_name = match.group(0)
        if repo_name not in scope:
            scope.append(repo_name)

    # Keyword -> organ mapping
    for keyword, organ_key in _KEYWORD_ORGANS.items():
        pattern = rf"\b{re.escape(keyword)}\b"
        if re.search(pattern, text_lower) and organ_key not in scope:
            scope.append(organ_key)

    return scope


# ---------------------------------------------------------------------------
# Commit window search
# ---------------------------------------------------------------------------


def find_following_commits(
    intention: Intention,
    records: list[FossilRecord],
    window_hours: int = 48,
) -> list[FossilRecord]:
    """Find commits within window_hours after the intention timestamp."""
    window = timedelta(hours=window_hours)
    start = intention.timestamp
    end = start + window
    return [
        r
        for r in records
        if start < r.timestamp <= end
    ]


# ---------------------------------------------------------------------------
# Drift computation
# ---------------------------------------------------------------------------


def _extract_scope_from_record(record: FossilRecord) -> list[str]:
    """Extract scope identifiers from a fossil record."""
    scope: list[str] = []
    if record.organ and record.organ not in scope:
        scope.append(record.organ)
    if record.repo and record.repo not in scope:
        scope.append(record.repo)
    return scope


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two sets."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def compute_drift(
    intention: Intention,
    following_commits: list[FossilRecord],
) -> DriftRecord:
    """Compute drift between an intention and subsequent commits.

    Classification rules:
    - Convergence > 0.8  -> Animus (plan held)
    - len(mutations) > len(shadows) -> Anima (creative emergence)
    - len(shadows) > len(mutations) -> Shadow (avoidance)
    - Convergence < 0.2  -> Trickster (went somewhere unexpected)
    - 1 intended, 5+ actual -> Individuation (small intent, big integration)
    """
    intended_scope = extract_scope_from_text(intention.raw_text)
    intended_set = {s.lower() for s in intended_scope}

    # Build actual scope from all following commits
    actual_scope: list[str] = []
    for record in following_commits:
        for item in _extract_scope_from_record(record):
            if item not in actual_scope:
                actual_scope.append(item)
    actual_set = {s.lower() for s in actual_scope}

    convergence = _jaccard(intended_set, actual_set)
    mutations = sorted(actual_set - intended_set)
    shadows = sorted(intended_set - actual_set)

    # Classify the drift pattern
    drift_archetype = _classify_drift(
        convergence=convergence,
        mutations=mutations,
        shadows=shadows,
        intended_count=len(intended_set),
        actual_count=len(actual_set),
        has_commits=len(following_commits) > 0,
    )

    return DriftRecord(
        intention_id=intention.id,
        intended_scope=intended_scope,
        actual_scope=actual_scope,
        convergence=convergence,
        mutations=mutations,
        shadows=shadows,
        drift_archetype=drift_archetype,
    )


def _classify_drift(
    *,
    convergence: float,
    mutations: list[str],
    shadows: list[str],
    intended_count: int,
    actual_count: int,
    has_commits: bool,
) -> Archetype:
    """Classify the drift pattern into a Jungian archetype."""
    if not has_commits:
        return Archetype.SHADOW  # nothing done = avoidance

    # Small intent, big integration
    if intended_count <= 1 and actual_count >= 5:
        return Archetype.INDIVIDUATION

    # Plan held tightly
    if convergence > 0.8:
        return Archetype.ANIMUS

    # Went somewhere completely unexpected
    if convergence < 0.2:
        return Archetype.TRICKSTER

    # Creative emergence — more unplanned than avoided
    if len(mutations) > len(shadows):
        return Archetype.ANIMA

    # Avoidance — more intended than done
    if len(shadows) > len(mutations):
        return Archetype.SHADOW

    # Default: moderate drift is Anima (creative adaptation)
    return Archetype.ANIMA


# ---------------------------------------------------------------------------
# Batch analysis
# ---------------------------------------------------------------------------


def analyze_all_drift(
    intentions: list[Intention],
    records: list[FossilRecord],
    window_hours: int = 48,
) -> list[DriftRecord]:
    """Run drift analysis on all intentions against the fossil record."""
    results: list[DriftRecord] = []
    for intention in intentions:
        following = find_following_commits(intention, records, window_hours)
        drift = compute_drift(intention, following)
        results.append(drift)
    return results
