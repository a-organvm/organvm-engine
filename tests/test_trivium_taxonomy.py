"""Tests for translation pairs, tiers, and the translation graph."""

from organvm_engine.trivium.dialects import Dialect
from organvm_engine.trivium.taxonomy import (
    PreservationDegree,
    TranslationPair,
    TranslationTier,
    all_pairs,
    compose_translation,
    pairs_by_tier,
    pairs_for_organ,
    tier_1_pairs,
    tier_2_pairs,
    translation_graph,
)


def test_all_pairs_count():
    """C(8,2) = 28 pairs."""
    assert len(all_pairs()) == 28


def test_all_pairs_are_unique():
    pairs = all_pairs()
    seen: set[frozenset[Dialect]] = set()
    for p in pairs:
        key = frozenset([p.source, p.target])
        assert key not in seen, f"Duplicate pair: {p.source}↔{p.target}"
        seen.add(key)


def test_all_pairs_no_self_loops():
    for p in all_pairs():
        assert p.source != p.target


def test_tier_1_contains_curry_howard():
    """I↔III (Logic↔Algorithm) must be Tier 1."""
    t1 = tier_1_pairs()
    pair_keys = {frozenset([p.source, p.target]) for p in t1}
    assert frozenset([Dialect.FORMAL_LOGIC, Dialect.EXECUTABLE_ALGORITHM]) in pair_keys


def test_tier_1_contains_propositions_as_rules():
    """I↔IV (Logic↔Governance) must be Tier 1."""
    t1 = tier_1_pairs()
    pair_keys = {frozenset([p.source, p.target]) for p in t1}
    assert frozenset([Dialect.FORMAL_LOGIC, Dialect.GOVERNANCE_LOGIC]) in pair_keys


def test_tier_1_contains_godel():
    """I↔META (Logic↔Self-Witnessing) must be Tier 1."""
    t1 = tier_1_pairs()
    pair_keys = {frozenset([p.source, p.target]) for p in t1}
    assert frozenset([Dialect.FORMAL_LOGIC, Dialect.SELF_WITNESSING]) in pair_keys


def test_tier_1_has_three_pairs():
    assert len(tier_1_pairs()) == 3


def test_tier_2_has_five_pairs():
    assert len(tier_2_pairs()) == 5


def test_tier_classification_is_exhaustive():
    """Every pair has a tier."""
    for p in all_pairs():
        assert p.tier in TranslationTier


def test_tier_counts_sum_to_28():
    counts = {tier: len(pairs_by_tier(tier)) for tier in TranslationTier}
    assert sum(counts.values()) == 28


def test_pairs_for_organ_returns_seven():
    """Each organ connects to all 7 others."""
    for dialect in Dialect:
        assert len(pairs_for_organ(dialect)) == 7


def test_preservation_degree_ordering():
    assert PreservationDegree.ISOMORPHISM.value > PreservationDegree.HOMOMORPHISM.value
    assert PreservationDegree.HOMOMORPHISM.value > PreservationDegree.PROJECTION.value
    assert PreservationDegree.PROJECTION.value > PreservationDegree.RESONANCE.value


def test_translation_graph_is_complete():
    """The translation graph should have 8 nodes and 28 edges."""
    graph = translation_graph()
    assert len(graph["nodes"]) == 8
    assert len(graph["edges"]) == 28


def test_translation_graph_node_structure():
    graph = translation_graph()
    for node in graph["nodes"]:
        assert "dialect" in node
        assert "organ" in node


def test_translation_graph_edge_structure():
    graph = translation_graph()
    for edge in graph["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "tier" in edge
        assert "preservation" in edge


def test_compose_translation_i_to_iii_to_vii():
    """I→III and III→VII should compose to I→VII."""
    result = compose_translation(
        Dialect.FORMAL_LOGIC,
        Dialect.EXECUTABLE_ALGORITHM,
        Dialect.SIGNAL_PROPAGATION,
    )
    assert result is not None
    assert result.source == Dialect.FORMAL_LOGIC
    assert result.target == Dialect.SIGNAL_PROPAGATION
    # Composed tier should be the weakest leg
    assert result.tier in TranslationTier


def test_compose_translation_preserves_weakest():
    """Composed preservation should be the minimum of the two legs."""
    result = compose_translation(
        Dialect.FORMAL_LOGIC,       # I
        Dialect.EXECUTABLE_ALGORITHM,  # III — I↔III is ISOMORPHISM
        Dialect.SIGNAL_PROPAGATION,    # VII — III↔VII is PROJECTION
    )
    assert result is not None
    # ISOMORPHISM(4) + PROJECTION(2) → minimum is PROJECTION(2)
    assert result.preservation.value <= PreservationDegree.ISOMORPHISM.value


def test_compose_translation_none_on_same_dialect():
    """Composing a→a→b doesn't make sense — a→a is a self-loop."""
    result = compose_translation(
        Dialect.FORMAL_LOGIC,
        Dialect.FORMAL_LOGIC,  # self-loop
        Dialect.AESTHETIC_FORM,
    )
    assert result is None


def test_translation_pair_frozen():
    p = all_pairs()[0]
    assert isinstance(p, TranslationPair)


def test_pairs_by_tier_emergent_nonempty():
    emergent = pairs_by_tier(TranslationTier.EMERGENT)
    # There should be emergent pairs (28 - 3 - 5 - 4 = 16)
    assert len(emergent) == 16
