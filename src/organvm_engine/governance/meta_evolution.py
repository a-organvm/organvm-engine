"""Meta-evolution engine — 4-stratum evolutionary classification.

Implements: SPEC-011, META-001 through META-004

Four evolutionary strata (from the constitutional corpus):
  META-001  STATE           — data changes (metric values, status fields)
  META-002  STRUCTURE       — hierarchy, dependency, or module changes
  META-003  ONTOLOGY        — category, entity-type, or schema changes
  META-004  META_EVOLUTION  — changes to the evolution rules themselves

classify_evolution() determines which stratum a proposed change belongs to.
check_safety_constraints() verifies the change is safe at that stratum.

Safety mechanisms:
  - STATE changes are unrestricted (normal operation)
  - STRUCTURE changes require governance review
  - ONTOLOGY changes require migration plan
  - META_EVOLUTION changes require constitutional amendment
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Stratum enum
# ---------------------------------------------------------------------------


class EvolutionStratum(str, enum.Enum):
    """The four evolutionary strata, ordered by severity."""

    STATE = "STATE"
    STRUCTURE = "STRUCTURE"
    ONTOLOGY = "ONTOLOGY"
    META_EVOLUTION = "META_EVOLUTION"


# Severity ordering: higher = more dangerous
_STRATUM_SEVERITY: dict[EvolutionStratum, int] = {
    EvolutionStratum.STATE: 0,
    EvolutionStratum.STRUCTURE: 1,
    EvolutionStratum.ONTOLOGY: 2,
    EvolutionStratum.META_EVOLUTION: 3,
}

# Keywords that signal each stratum
_STATE_KEYWORDS = frozenset({
    "metric", "status", "count", "score", "value", "last_validated",
    "platinum_status", "implementation_status", "code_files", "test_files",
})
_STRUCTURE_KEYWORDS = frozenset({
    "dependency", "hierarchy", "module", "submodule", "merge", "split",
    "relocate", "rename", "tier", "organ", "repo", "formation",
})
_ONTOLOGY_KEYWORDS = frozenset({
    "entity_type", "schema", "category", "taxonomy", "ontology",
    "classification", "primitive", "invariant", "spec",
})
_META_KEYWORDS = frozenset({
    "evolution_rule", "governance_rule", "state_machine", "promotion_rule",
    "constitutional", "axiom", "dictum", "meta_evolution", "amendment",
})


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class EvolutionClassification:
    """Result of classifying a proposed change."""

    stratum: EvolutionStratum
    severity: int
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stratum": self.stratum.value,
            "severity": self.severity,
            "matched_keywords": self.matched_keywords,
        }


@dataclass
class SafetyCheck:
    """Result of a safety constraint check."""

    safe: bool
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"safe": self.safe, "constraints": self.constraints}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_evolution(change_description: str) -> EvolutionClassification:
    """Classify a change into its evolutionary stratum.

    Uses keyword matching against the change description to determine
    which stratum it belongs to. When keywords from multiple strata
    match, the highest-severity stratum wins.

    Args:
        change_description: Free-text description of the proposed change.

    Returns:
        EvolutionClassification with stratum, severity, and matched keywords.
    """
    desc_lower = change_description.lower()

    best_stratum = EvolutionStratum.STATE
    best_severity = 0
    all_matched: list[str] = []

    for keyword_set, stratum in [
        (_META_KEYWORDS, EvolutionStratum.META_EVOLUTION),
        (_ONTOLOGY_KEYWORDS, EvolutionStratum.ONTOLOGY),
        (_STRUCTURE_KEYWORDS, EvolutionStratum.STRUCTURE),
        (_STATE_KEYWORDS, EvolutionStratum.STATE),
    ]:
        matched = []
        for kw in keyword_set:
            if kw in desc_lower:
                matched.append(kw)
        if matched:
            sev = _STRATUM_SEVERITY[stratum]
            if sev > best_severity:
                best_stratum = stratum
                best_severity = sev
            all_matched.extend(matched)

    return EvolutionClassification(
        stratum=best_stratum,
        severity=best_severity,
        matched_keywords=sorted(set(all_matched)),
    )


# ---------------------------------------------------------------------------
# Safety constraints
# ---------------------------------------------------------------------------

_SAFETY_REQUIREMENTS: dict[EvolutionStratum, list[str]] = {
    EvolutionStratum.STATE: [],
    EvolutionStratum.STRUCTURE: [
        "Governance review required before structural changes",
        "Dependency graph must remain acyclic after change",
        "Affected repos must be re-validated",
    ],
    EvolutionStratum.ONTOLOGY: [
        "Migration plan must be drafted before ontological changes",
        "All affected schemas must be versioned",
        "Entity identity continuity must be preserved (SVSE)",
        "Governance review required",
    ],
    EvolutionStratum.META_EVOLUTION: [
        "Constitutional amendment process required",
        "All existing invariants must be re-verified post-change",
        "Simulation sandbox must validate new rules before deployment",
        "Migration plan must be drafted",
        "Governance review required",
    ],
}


def check_safety_constraints(
    stratum: EvolutionStratum,
    proposed_change: str = "",
) -> tuple[bool, list[str]]:
    """Check safety constraints for a change at the given stratum.

    STATE-level changes are always safe. Higher strata require
    progressively stricter review processes.

    Args:
        stratum: The evolutionary stratum of the change.
        proposed_change: Description of the change (for future use).

    Returns:
        (safe, constraints) — safe is True only for STATE changes.
        For higher strata, returns False with the list of required
        safety constraints that must be satisfied.
    """
    constraints = _SAFETY_REQUIREMENTS.get(stratum, [])
    is_safe = len(constraints) == 0
    return is_safe, list(constraints)


def stratum_severity(stratum: EvolutionStratum) -> int:
    """Return the numeric severity of a stratum (0=STATE, 3=META_EVOLUTION)."""
    return _STRATUM_SEVERITY[stratum]
