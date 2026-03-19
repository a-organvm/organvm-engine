"""Repo fusion protocol.

Implements: SPEC-012, FUSE-001 through FUSE-003

Implements the third-location synthesis ("fusion chamber") protocol for
merging repos of equal value.  When two repos are candidates for
consolidation, each component is classified as RETAIN_A (keep from repo A),
RETAIN_B (keep from repo B), SYNTHESIZE (merge both into something new),
or INVENT (create an entirely new artifact that neither repo had).

The protocol enforces the principle that fusion must produce *elevation*
(emergent capability beyond what either repo had alone), not mere
consolidation (rearranging existing pieces without gain).

Ref: ``post-flood/Top-Down-Refinement-Pipeline/Fusion-and-Evolution/``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FusionClassification(str, Enum):
    """How a component is handled during repo fusion."""

    RETAIN_A = "retain_a"      # Keep from repo A as-is
    RETAIN_B = "retain_b"      # Keep from repo B as-is
    SYNTHESIZE = "synthesize"  # Merge from both repos into something new
    INVENT = "invent"          # Create an entirely new artifact


@dataclass
class FusionComponent:
    """A single component being classified for fusion."""

    name: str
    classification: FusionClassification
    source_a: str = ""  # path or identifier in repo A
    source_b: str = ""  # path or identifier in repo B
    rationale: str = ""


@dataclass
class FusionPlan:
    """A complete fusion plan for merging two repos."""

    repo_a: str
    repo_b: str
    target_name: str
    components: list[FusionComponent] = field(default_factory=list)
    elevation_rationale: str = ""

    @property
    def classification_counts(self) -> dict[str, int]:
        """Count components by classification type."""
        counts: dict[str, int] = {}
        for c in self.components:
            key = c.classification.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    @property
    def has_elevation(self) -> bool:
        """Check whether the fusion plan demonstrates elevation.

        Elevation requires at least one SYNTHESIZE or INVENT component.
        A plan with only RETAIN_A and RETAIN_B is mere consolidation.
        """
        return any(
            c.classification in (FusionClassification.SYNTHESIZE, FusionClassification.INVENT)
            for c in self.components
        )


def classify_fusion_component(
    name: str,
    *,
    in_a: bool = False,
    in_b: bool = False,
    mergeable: bool = False,
    novel: bool = False,
    source_a: str = "",
    source_b: str = "",
    rationale: str = "",
) -> FusionComponent:
    """Classify a component for the fusion protocol.

    Decision logic:
    - ``novel=True`` overrides everything: the component is INVENT.
    - Present in both repos and ``mergeable=True``: SYNTHESIZE.
    - Present only in repo A: RETAIN_A.
    - Present only in repo B: RETAIN_B.
    - Present in both but not mergeable: RETAIN_A (prefer A by convention).

    Args:
        name: Component identifier.
        in_a: Whether the component exists in repo A.
        in_b: Whether the component exists in repo B.
        mergeable: Whether A and B versions can be meaningfully merged.
        novel: Whether this is an entirely new artifact to be invented.
        source_a: Path or identifier in repo A.
        source_b: Path or identifier in repo B.
        rationale: Free-text justification for the classification.

    Returns:
        A ``FusionComponent`` with the appropriate classification.
    """
    if novel:
        classification = FusionClassification.INVENT
    elif in_a and in_b and mergeable:
        classification = FusionClassification.SYNTHESIZE
    elif in_a and not in_b:
        classification = FusionClassification.RETAIN_A
    elif in_b and not in_a:
        classification = FusionClassification.RETAIN_B
    elif in_a and in_b:
        # Both have it but not mergeable — prefer A by convention
        classification = FusionClassification.RETAIN_A
    else:
        # Neither repo has it — must be novel
        classification = FusionClassification.INVENT

    return FusionComponent(
        name=name,
        classification=classification,
        source_a=source_a,
        source_b=source_b,
        rationale=rationale,
    )


def validate_fusion_plan(plan: FusionPlan) -> list[str]:
    """Validate a fusion plan and return a list of warnings.

    Checks:
    - Plan must have at least one component.
    - Plan must demonstrate elevation (at least one SYNTHESIZE or INVENT).
    - Target name must differ from both source repos.
    - No duplicate component names.

    Returns:
        A list of warning strings.  Empty list means the plan is valid.
    """
    warnings: list[str] = []

    if not plan.components:
        warnings.append("Fusion plan has no components")

    if not plan.has_elevation:
        warnings.append(
            "Fusion plan has no SYNTHESIZE or INVENT components — "
            "this is consolidation, not elevation"
        )

    if plan.target_name == plan.repo_a:
        warnings.append(f"Target name '{plan.target_name}' is the same as repo A")
    if plan.target_name == plan.repo_b:
        warnings.append(f"Target name '{plan.target_name}' is the same as repo B")

    names = [c.name for c in plan.components]
    if len(names) != len(set(names)):
        warnings.append("Duplicate component names in fusion plan")

    if not plan.elevation_rationale and plan.has_elevation:
        warnings.append("Fusion plan has elevation components but no rationale")

    return warnings


def is_elevation(fusion_result: dict, source_a: dict, source_b: dict) -> bool:
    """Determine if fusion is elevation (emergent gain) vs consolidation.

    Compares the resulting capabilities against the union of source
    capabilities.  If the result has capabilities that neither source
    had, it's elevation.

    Args:
        fusion_result: Dict with a ``capabilities`` list for the merged repo.
        source_a: Dict with a ``capabilities`` list for repo A.
        source_b: Dict with a ``capabilities`` list for repo B.

    Returns:
        ``True`` if the fusion introduces emergent capabilities.
    """
    result_caps = set(fusion_result.get("capabilities", []))
    combined = set(source_a.get("capabilities", [])) | set(source_b.get("capabilities", []))
    return len(result_caps - combined) > 0
