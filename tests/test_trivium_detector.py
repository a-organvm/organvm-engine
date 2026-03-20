"""Tests for structural correspondence detection between organs."""

import json
from pathlib import Path

from organvm_engine.trivium.detector import (
    Correspondence,
    CorrespondenceType,
    detect_functional_correspondences,
    detect_naming_isomorphisms,
    detect_semantic_correspondences,
    detect_structural_correspondences,
    scan_organ_pair,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "registry-trivium.json"


def _load_fixture() -> dict:
    with FIXTURE_PATH.open() as f:
        return json.load(f)


def test_correspondence_type_enum():
    assert len(CorrespondenceType) == 4


def test_correspondence_strength_range():
    c = Correspondence(
        correspondence_type=CorrespondenceType.NAMING,
        source_organ="a", target_organ="b",
        source_entity="x", target_entity="y",
        evidence="test", strength=0.5,
    )
    assert c.strength == 0.5


def test_correspondence_strength_validation():
    import pytest
    with pytest.raises(ValueError):
        Correspondence(
            correspondence_type=CorrespondenceType.NAMING,
            source_organ="a", target_organ="b",
            source_entity="x", target_entity="y",
            evidence="test", strength=1.5,
        )


def test_detect_naming_isomorphisms_empty():
    result = detect_naming_isomorphisms([], [])
    assert result == []


def test_detect_naming_isomorphisms_finds_parallel_repos():
    organ_a_repos = [
        {"name": "recursive-engine--generative-entity", "org": "org-a",
         "description": "Recursive computation"},
    ]
    organ_b_repos = [
        {"name": "recursive-tool--generative-util", "org": "org-b",
         "description": "Recursive tool for generation"},
    ]
    result = detect_naming_isomorphisms(organ_a_repos, organ_b_repos)
    assert len(result) >= 1
    assert any(c.correspondence_type == CorrespondenceType.NAMING for c in result)
    # "recursive" and "generative" should be shared stems
    assert any("recursive" in c.evidence for c in result)


def test_detect_naming_no_match():
    organ_a_repos = [
        {"name": "alpha-beta", "org": "org-a", "description": ""},
    ]
    organ_b_repos = [
        {"name": "gamma-delta", "org": "org-b", "description": ""},
    ]
    result = detect_naming_isomorphisms(organ_a_repos, organ_b_repos)
    assert result == []


def test_detect_structural_empty():
    result = detect_structural_correspondences([], [])
    assert result == []


def test_detect_structural_similar_counts():
    a = [{"org": "a", "tier": "standard"} for _ in range(3)]
    b = [{"org": "b", "tier": "standard"} for _ in range(3)]
    result = detect_structural_correspondences(a, b)
    assert len(result) >= 1
    assert any(c.correspondence_type == CorrespondenceType.STRUCTURAL for c in result)


def test_detect_functional_empty():
    result = detect_functional_correspondences([], [])
    assert result == []


def test_detect_functional_finds_dependency():
    a = [{"name": "upstream-lib", "org": "org-a"}]
    b = [{"name": "downstream-app", "org": "org-b",
          "dependencies": ["upstream-lib"]}]
    result = detect_functional_correspondences(a, b)
    assert len(result) == 1
    assert result[0].correspondence_type == CorrespondenceType.FUNCTIONAL
    assert result[0].strength == 0.9


def test_detect_semantic_empty():
    result = detect_semantic_correspondences([], [])
    assert result == []


def test_detect_semantic_shared_keywords():
    a = [{"name": "a", "org": "org-a",
          "description": "Recursive computation engine for generative entities"}]
    b = [{"name": "b", "org": "org-b",
          "description": "Recursive computation tool for generative utilities"}]
    result = detect_semantic_correspondences(a, b)
    assert len(result) >= 1
    assert any(c.correspondence_type == CorrespondenceType.SEMANTIC for c in result)


def test_scan_organ_pair_returns_report():
    report = scan_organ_pair("I", "III", registry_path=FIXTURE_PATH)
    assert "correspondences" in report
    assert "organ_a" in report
    assert report["organ_a"] == "I"
    assert "organ_b" in report
    assert report["organ_b"] == "III"
    assert isinstance(report["correspondences"], list)
    assert report["count"] >= 1


def test_scan_organ_pair_finds_naming():
    report = scan_organ_pair("I", "III", registry_path=FIXTURE_PATH)
    naming = [c for c in report["correspondences"] if c["type"] == "naming"]
    assert len(naming) >= 1


def test_scan_organ_pair_finds_functional():
    report = scan_organ_pair("I", "III", registry_path=FIXTURE_PATH)
    functional = [
        c for c in report["correspondences"] if c["type"] == "functional"
    ]
    assert len(functional) >= 1


def test_scan_organ_pair_no_registry():
    report = scan_organ_pair("I", "III")
    assert report["correspondences"] == []
    assert "No registry" in report["summary"]


def test_scan_organ_pair_meta():
    report = scan_organ_pair("I", "META", registry_path=FIXTURE_PATH)
    assert report["organ_a"] == "I"
    assert report["organ_b"] == "META"
