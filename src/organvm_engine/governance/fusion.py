"""Repo fusion protocol.

Implements: SPEC-012, FUSE-001 through FUSE-003
"""
from __future__ import annotations

from enum import Enum


class FusionClassification(str, Enum):
    RETAIN_A = "retain_a"
    RETAIN_B = "retain_b"
    SYNTHESIZE = "synthesize"
    INVENT = "invent"


def classify_fusion_component(
    component_name: str,
    exists_in_a: bool,
    exists_in_b: bool,
    equivalent: bool = False,
) -> FusionClassification:
    """Classify a component for third-location synthesis."""
    if exists_in_a and exists_in_b:
        return FusionClassification.SYNTHESIZE if not equivalent else FusionClassification.RETAIN_A
    if exists_in_a:
        return FusionClassification.RETAIN_A
    if exists_in_b:
        return FusionClassification.RETAIN_B
    return FusionClassification.INVENT


def is_elevation(fusion_result: dict, source_a: dict, source_b: dict) -> bool:
    """Determine if fusion is elevation (emergent gain) vs consolidation."""
    result_caps = set(fusion_result.get("capabilities", []))
    combined = set(source_a.get("capabilities", [])) | set(source_b.get("capabilities", []))
    return len(result_caps - combined) > 0
