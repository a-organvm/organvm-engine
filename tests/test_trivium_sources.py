"""Tests for trivium data source adapters."""

import json
from pathlib import Path

from organvm_engine.trivium.sources import dialect_data, isomorphism_data

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "registry-trivium.json"


def test_isomorphism_data_structure():
    result = isomorphism_data(registry_path=FIXTURE_PATH)
    assert "total_pairs" in result
    assert result["total_pairs"] == 28
    assert "pairs_with_evidence" in result
    assert "total_correspondences" in result
    assert "avg_strength" in result
    assert "tier_counts" in result
    assert "strongest_pairs" in result


def test_isomorphism_data_tier_counts():
    result = isomorphism_data(registry_path=FIXTURE_PATH)
    tiers = result["tier_counts"]
    assert "formal" in tiers
    assert "structural" in tiers
    assert "analogical" in tiers
    assert "emergent" in tiers
    assert tiers["formal"] == 3
    assert sum(tiers.values()) == 28


def test_isomorphism_data_strongest_pairs():
    result = isomorphism_data(registry_path=FIXTURE_PATH)
    strongest = result["strongest_pairs"]
    assert isinstance(strongest, list)
    assert len(strongest) <= 5
    for pair in strongest:
        assert "source_organ" in pair
        assert "target_organ" in pair
        assert "strength" in pair


def test_isomorphism_data_no_registry():
    result = isomorphism_data()
    assert result["total_pairs"] == 28
    assert result["pairs_with_evidence"] == 0


def test_dialect_data_structure():
    result = dialect_data()
    assert result["count"] == 8
    assert len(result["dialects"]) == 8


def test_dialect_data_fields():
    result = dialect_data()
    for d in result["dialects"]:
        assert "dialect" in d
        assert "organ_key" in d
        assert "organ_name" in d
        assert "translation_role" in d
        assert "formal_basis" in d
        assert "classical_parallel" in d
        assert "description" in d


def test_dialect_data_has_all_organs():
    result = dialect_data()
    organ_keys = {d["organ_key"] for d in result["dialects"]}
    assert organ_keys == {"I", "II", "III", "IV", "V", "VI", "VII", "META"}
