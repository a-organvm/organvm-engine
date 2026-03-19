"""Functional taxonomy engine — 10-class repo classification.

Implements: INST-TAXONOMY, TAXON-001 through TAXON-010

Ten functional classes (orthogonal to organ domain):
  TAXON-001  CHARTER         — constitutional/foundational documents
  TAXON-002  CORPUS          — curated knowledge collections
  TAXON-003  FRAMEWORK       — reusable libraries and patterns
  TAXON-004  ENGINE          — core computational machinery
  TAXON-005  APPLICATION     — user-facing products
  TAXON-006  INFRASTRUCTURE  — plumbing, CI, deployment
  TAXON-007  ASSURANCE       — testing, auditing, verification
  TAXON-008  ARCHIVE         — preserved historical material
  TAXON-009  EXPERIMENT      — sandbox/prototype explorations
  TAXON-010  OPERATIONS      — process governance, SOPs

classify_repo() uses heuristics on name, tier, and description.
validate_classification() checks for consistency with other fields.
"""

from __future__ import annotations

import enum
from typing import Any


class FunctionalClass(str, enum.Enum):
    """The 10 functional classes from the constitutional topology."""

    CHARTER = "CHARTER"
    CORPUS = "CORPUS"
    FRAMEWORK = "FRAMEWORK"
    ENGINE = "ENGINE"
    APPLICATION = "APPLICATION"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    ASSURANCE = "ASSURANCE"
    ARCHIVE = "ARCHIVE"
    EXPERIMENT = "EXPERIMENT"
    OPERATIONS = "OPERATIONS"


# ---------------------------------------------------------------------------
# Heuristic classification rules
# ---------------------------------------------------------------------------

# (keywords_in_name_or_desc, keywords_in_tier, candidate_class)
_CLASSIFICATION_RULES: list[tuple[frozenset[str], frozenset[str], FunctionalClass]] = [
    # Highest-specificity rules first
    (
        frozenset({"charter", "constitution", "manifesto", "foundational"}),
        frozenset(),
        FunctionalClass.CHARTER,
    ),
    (
        frozenset({"corpus", "corpvs", "knowledge-base", "knowledge base", "curated"}),
        frozenset(),
        FunctionalClass.CORPUS,
    ),
    (
        frozenset({"engine", "core", "runtime"}),
        frozenset({"flagship"}),
        FunctionalClass.ENGINE,
    ),
    (
        frozenset({"framework", "library", "sdk", "kit", "patterns"}),
        frozenset(),
        FunctionalClass.FRAMEWORK,
    ),
    (
        frozenset({"dashboard", "portal", "app", "application", "ui", "site", "web"}),
        frozenset(),
        FunctionalClass.APPLICATION,
    ),
    (
        frozenset({"infra", "ci", "deploy", "server", "mcp", "pipeline"}),
        frozenset({"infrastructure"}),
        FunctionalClass.INFRASTRUCTURE,
    ),
    (
        frozenset({"test", "audit", "verify", "assurance", "lint", "check"}),
        frozenset(),
        FunctionalClass.ASSURANCE,
    ),
    (
        frozenset({"sop", "praxis", "operations", "process", "governance", "standards"}),
        frozenset(),
        FunctionalClass.OPERATIONS,
    ),
    (
        frozenset({"experiment", "lab", "sandbox", "prototype", "spike"}),
        frozenset(),
        FunctionalClass.EXPERIMENT,
    ),
    (
        frozenset({"archive", "legacy", "deprecated", "historical", "dissolved"}),
        frozenset({"archive"}),
        FunctionalClass.ARCHIVE,
    ),
]


def classify_repo(repo: dict[str, Any]) -> FunctionalClass:
    """Classify a repo into one of the 10 functional classes.

    Uses heuristic matching on name, tier, and description.
    Falls back to APPLICATION if no rule matches.

    Args:
        repo: A repository dict from the registry.

    Returns:
        The best-matching FunctionalClass.
    """
    name = (repo.get("name") or "").lower()
    desc = (repo.get("description") or "").lower()
    tier = (repo.get("tier") or "").lower()
    combined = f"{name} {desc}"

    # Check tier-based rules first (high signal)
    if tier == "archive":
        return FunctionalClass.ARCHIVE
    if tier == "infrastructure":
        # Narrow: if name also matches something else, let name win
        pass

    # Walk rules in priority order
    for name_keywords, tier_keywords, fclass in _CLASSIFICATION_RULES:
        name_match = any(kw in combined for kw in name_keywords)
        tier_match = any(kw in tier for kw in tier_keywords) if tier_keywords else False

        if name_match or tier_match:
            return fclass

    return FunctionalClass.APPLICATION


def validate_classification(
    repo: dict[str, Any],
    assigned_class: FunctionalClass,
) -> tuple[bool, list[str]]:
    """Validate that an assigned classification is consistent with repo data.

    Checks for obvious mismatches between the assigned class and the
    repo's tier, status, and name.

    Args:
        repo: A repository dict from the registry.
        assigned_class: The FunctionalClass to validate.

    Returns:
        (valid, warnings) — valid is True if no critical mismatches found.
    """
    warnings: list[str] = []
    tier = (repo.get("tier") or "").lower()
    impl = (repo.get("implementation_status") or "").upper()
    promo = (repo.get("promotion_status") or "").upper()

    # ARCHIVE class should have ARCHIVED status
    if (
        assigned_class == FunctionalClass.ARCHIVE
        and promo not in ("ARCHIVED", "")
        and impl not in ("ARCHIVED", "")
    ):
        warnings.append(
            "ARCHIVE class but not ARCHIVED status — "
            "may need promotion to ARCHIVED",
        )

    # ENGINE class should be flagship or standard tier
    if (
        assigned_class == FunctionalClass.ENGINE
        and tier not in ("flagship", "standard", "")
    ):
        warnings.append(
            f"ENGINE class but tier is '{tier}' — expected flagship or standard",
        )

    # CHARTER class should not have active code
    if assigned_class == FunctionalClass.CHARTER:
        code_files = repo.get("code_files", 0) or 0
        if code_files > 10:
            warnings.append(
                f"CHARTER class but has {code_files} code files — "
                "may be misclassified (charters are theory)",
            )

    # EXPERIMENT class should not be GRADUATED
    if assigned_class == FunctionalClass.EXPERIMENT and promo == "GRADUATED":
        warnings.append(
            "EXPERIMENT class but GRADUATED — "
            "experiments should not graduate (promote to another class first)",
        )

    # INFRASTRUCTURE should have infrastructure tier
    if (
        assigned_class == FunctionalClass.INFRASTRUCTURE
        and tier
        and tier not in ("infrastructure", "standard")
    ):
        warnings.append(
            f"INFRASTRUCTURE class but tier is '{tier}'",
        )

    return len(warnings) == 0, warnings
