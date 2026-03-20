"""Tests for cross-organ edges and kinship lens integration."""

from organvm_engine.trivium.edges import (
    formal_edges,
    isomorphism_edge,
    trivium_edges,
)
from organvm_engine.trivium.kinship import (
    enrich_kinship_lens,
    kinship_from_dialect,
)
from organvm_engine.trivium.taxonomy import (
    TranslationTier,
    tier_1_pairs,
)


# ---------------------------------------------------------------------------
# Edge tests
# ---------------------------------------------------------------------------


def test_isomorphism_edge_structure():
    pair = tier_1_pairs()[0]
    edge = isomorphism_edge(pair)
    assert edge["type"] == "isomorphism-surface"
    assert "source_organ" in edge
    assert "target_organ" in edge
    assert "description" in edge
    assert "metadata" in edge
    assert "tier" in edge["metadata"]
    assert "preservation" in edge["metadata"]


def test_formal_edges_count():
    edges = formal_edges()
    assert len(edges) == 3


def test_formal_edges_all_tier_1():
    for edge in formal_edges():
        assert edge["metadata"]["tier"] == "formal"


def test_trivium_edges_default_excludes_emergent():
    edges = trivium_edges()
    for edge in edges:
        assert edge["metadata"]["tier"] != "emergent"


def test_trivium_edges_default_count():
    # 3 formal + 5 structural + 11 analogical = 19
    edges = trivium_edges()
    assert len(edges) == 19


def test_trivium_edges_formal_only():
    edges = trivium_edges(min_tier=TranslationTier.FORMAL)
    assert len(edges) == 3


def test_trivium_edges_structural():
    edges = trivium_edges(min_tier=TranslationTier.STRUCTURAL)
    # 3 formal + 5 structural = 8
    assert len(edges) == 8


def test_trivium_edges_all():
    edges = trivium_edges(min_tier=TranslationTier.EMERGENT)
    assert len(edges) == 28


# ---------------------------------------------------------------------------
# Kinship tests
# ---------------------------------------------------------------------------


def test_kinship_from_dialect_returns_list():
    entries = kinship_from_dialect("I")
    assert isinstance(entries, list)


def test_kinship_from_dialect_excludes_emergent():
    entries = kinship_from_dialect("I")
    for e in entries:
        assert "emergent" not in [t for t in e.get("tags", [])]


def test_kinship_from_dialect_has_required_fields():
    entries = kinship_from_dialect("I")
    for e in entries:
        assert "project" in e
        assert "platform" in e
        assert "relevance" in e
        assert "engagement" in e
        assert "tags" in e


def test_kinship_from_dialect_organ_i():
    entries = kinship_from_dialect("I")
    # I has 3 T1 (I↔III, I↔IV, I↔META) + 3 T3 (I↔V, I↔VI, I↔VII) = 6 non-emergent
    assert len(entries) == 6


def test_enrich_kinship_deduplicates():
    existing = [{"project": "ORGANVM ORGAN-III (Ergon)", "platform": "x"}]
    merged = enrich_kinship_lens(existing, "I")
    # Should not duplicate ORGAN-III
    projects = [e["project"] for e in merged]
    assert projects.count("ORGANVM ORGAN-III (Ergon)") == 1


def test_enrich_kinship_adds_new():
    merged = enrich_kinship_lens([], "I")
    assert len(merged) >= 1


def test_enrich_kinship_preserves_existing():
    existing = [{"project": "External Project", "platform": "github"}]
    merged = enrich_kinship_lens(existing, "I")
    assert any(e["project"] == "External Project" for e in merged)
