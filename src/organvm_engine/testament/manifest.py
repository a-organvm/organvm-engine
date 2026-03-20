"""Artifact manifest — declares every publishable output the system can produce.

Maps engine modules to the artifact types they generate, and organs to
their primary and secondary output modalities. This is the declaration
layer: what the system *can* produce, not how it produces it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ArtifactModality(Enum):
    """Sensory/intellectual channel an artifact occupies."""

    VISUAL = "visual"
    STATISTICAL = "statistical"
    SCHEMATIC = "schematic"
    MATHEMATICAL = "mathematical"
    THEORETICAL = "theoretical"
    ACADEMIC = "academic"
    SOCIAL = "social"
    PHILOSOPHICAL = "philosophical"
    SONIC = "sonic"
    ARCHIVAL = "archival"


class ArtifactFormat(Enum):
    """Output file format for a rendered artifact."""

    SVG = "svg"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    LATEX = "latex"
    TXT = "txt"
    PNG = "png"


@dataclass(frozen=True)
class ArtifactType:
    """A single artifact kind that a module can produce."""

    modality: ArtifactModality
    format: ArtifactFormat
    description: str
    source_module: str


@dataclass(frozen=True)
class OrganOutputProfile:
    """Declares an organ's natural output modalities."""

    organ_key: str
    primary_modalities: list[ArtifactModality] = field(default_factory=list)
    secondary_modalities: list[ArtifactModality] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# Organ output matrix — what each organ naturally produces
# ---------------------------------------------------------------------------

ORGAN_OUTPUT_MATRIX: dict[str, OrganOutputProfile] = {
    "META": OrganOutputProfile(
        organ_key="META",
        primary_modalities=list(ArtifactModality),
        secondary_modalities=[],
        description="Constitutional substrate — renders in every medium",
    ),
    "I": OrganOutputProfile(
        organ_key="I",
        primary_modalities=[ArtifactModality.MATHEMATICAL, ArtifactModality.THEORETICAL],
        secondary_modalities=[ArtifactModality.PHILOSOPHICAL],
        description="Foundational theory, recursive engines, symbolic computing",
    ),
    "II": OrganOutputProfile(
        organ_key="II",
        primary_modalities=[ArtifactModality.VISUAL, ArtifactModality.SONIC],
        secondary_modalities=[ArtifactModality.SCHEMATIC],
        description="Generative art, performance systems, creative coding",
    ),
    "III": OrganOutputProfile(
        organ_key="III",
        primary_modalities=[ArtifactModality.STATISTICAL, ArtifactModality.VISUAL],
        secondary_modalities=[ArtifactModality.SOCIAL],
        description="Commercial products, SaaS tools, developer utilities",
    ),
    "IV": OrganOutputProfile(
        organ_key="IV",
        primary_modalities=[ArtifactModality.SCHEMATIC, ArtifactModality.STATISTICAL],
        secondary_modalities=[ArtifactModality.VISUAL],
        description="Orchestration, governance, AI agents, skills",
    ),
    "V": OrganOutputProfile(
        organ_key="V",
        primary_modalities=[ArtifactModality.THEORETICAL, ArtifactModality.SOCIAL],
        secondary_modalities=[ArtifactModality.ACADEMIC],
        description="Public discourse, essays, editorial, analytics",
    ),
    "VI": OrganOutputProfile(
        organ_key="VI",
        primary_modalities=[ArtifactModality.SCHEMATIC, ArtifactModality.SOCIAL],
        secondary_modalities=[ArtifactModality.STATISTICAL],
        description="Community, reading groups, salons, learning",
    ),
    "VII": OrganOutputProfile(
        organ_key="VII",
        primary_modalities=[ArtifactModality.SOCIAL, ArtifactModality.STATISTICAL],
        secondary_modalities=[ArtifactModality.VISUAL],
        description="POSSE distribution, social automation, announcements",
    ),
}


# ---------------------------------------------------------------------------
# Module source matrix — what each engine module can render
# ---------------------------------------------------------------------------

MODULE_SOURCES: dict[str, list[ArtifactType]] = {
    "registry": [
        ArtifactType(
            ArtifactModality.SCHEMATIC,
            ArtifactFormat.SVG,
            "System topology constellation",
            "registry",
        ),
    ],
    "governance": [
        ArtifactType(
            ArtifactModality.SCHEMATIC,
            ArtifactFormat.SVG,
            "Dependency flow diagram",
            "governance",
        ),
        ArtifactType(
            ArtifactModality.MATHEMATICAL,
            ArtifactFormat.MARKDOWN,
            "State machine formal spec",
            "governance",
        ),
    ],
    "metrics": [
        ArtifactType(
            ArtifactModality.STATISTICAL,
            ArtifactFormat.SVG,
            "AMMOI density portrait",
            "metrics",
        ),
        ArtifactType(
            ArtifactModality.STATISTICAL,
            ArtifactFormat.HTML,
            "Temporal metrics timeline",
            "metrics",
        ),
    ],
    "omega": [
        ArtifactType(
            ArtifactModality.VISUAL,
            ArtifactFormat.SVG,
            "Omega scorecard mandala",
            "omega",
        ),
    ],
    "seed": [
        ArtifactType(
            ArtifactModality.SCHEMATIC,
            ArtifactFormat.SVG,
            "Produces/consumes flow diagram",
            "seed",
        ),
    ],
    "ontologia": [
        ArtifactType(
            ArtifactModality.SCHEMATIC,
            ArtifactFormat.SVG,
            "Entity hierarchy tree",
            "ontologia",
        ),
    ],
    "ecosystem": [
        ArtifactType(
            ArtifactModality.STATISTICAL,
            ArtifactFormat.SVG,
            "Competitive matrix radar",
            "ecosystem",
        ),
    ],
    "session": [
        ArtifactType(
            ArtifactModality.STATISTICAL,
            ArtifactFormat.SVG,
            "Session activity timeline",
            "session",
        ),
    ],
    "pitchdeck": [
        ArtifactType(
            ArtifactModality.VISUAL,
            ArtifactFormat.HTML,
            "Per-repo pitch deck",
            "pitchdeck",
        ),
    ],
    "content": [
        ArtifactType(
            ArtifactModality.SOCIAL,
            ArtifactFormat.MARKDOWN,
            "Content pipeline post",
            "content",
        ),
    ],
    "trivium": [
        ArtifactType(
            ArtifactModality.PHILOSOPHICAL,
            ArtifactFormat.MARKDOWN,
            "Dialectica Universalis — inter-organ isomorphism portrait",
            "trivium",
        ),
    ],
}


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def get_organ_profile(organ_key: str) -> OrganOutputProfile | None:
    """Return the output profile for an organ, or None if unknown."""
    return ORGAN_OUTPUT_MATRIX.get(organ_key)


def get_module_artifacts(module_name: str) -> list[ArtifactType]:
    """Return the artifact types a given engine module can produce."""
    return MODULE_SOURCES.get(module_name, [])


def all_artifact_types() -> list[ArtifactType]:
    """Return a flat list of every declared artifact type across all modules."""
    result: list[ArtifactType] = []
    for artifacts in MODULE_SOURCES.values():
        result.extend(artifacts)
    return result
