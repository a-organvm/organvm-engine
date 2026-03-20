"""Tests for trivium content generation pipeline."""

from organvm_engine.trivium.content import (
    TranslationEssay,
    generate_all_outlines,
    generate_essay_outline,
    render_essay_catalog,
)
from organvm_engine.trivium.taxonomy import (
    TranslationTier,
    tier_1_pairs,
)


def test_generate_essay_outline():
    pair = tier_1_pairs()[0]  # I↔III Curry-Howard
    essay = generate_essay_outline(pair)
    assert isinstance(essay, TranslationEssay)
    assert essay.title
    assert essay.subtitle
    assert essay.thesis
    assert len(essay.outline) >= 5


def test_essay_title_formal_tier():
    pair = tier_1_pairs()[0]
    essay = generate_essay_outline(pair)
    assert "Proof" in essay.title or "IS" in essay.title


def test_essay_thesis_mentions_tier():
    pair = tier_1_pairs()[0]
    essay = generate_essay_outline(pair)
    assert "formal" in essay.thesis


def test_essay_outline_has_sections():
    pair = tier_1_pairs()[0]
    essay = generate_essay_outline(pair)
    assert any("Introduction" in s for s in essay.outline)
    assert any("Evidence" in s for s in essay.outline)
    assert any("Proves" in s or "proves" in s for s in essay.outline)


def test_generate_all_outlines_default():
    # Default: formal + structural + analogical = 19
    essays = generate_all_outlines()
    assert len(essays) == 19


def test_generate_all_outlines_formal_only():
    essays = generate_all_outlines(min_tier=TranslationTier.FORMAL)
    assert len(essays) == 3


def test_generate_all_outlines_all():
    essays = generate_all_outlines(min_tier=TranslationTier.EMERGENT)
    assert len(essays) == 28


def test_generate_all_sorted_by_tier():
    essays = generate_all_outlines()
    tier_order = {"formal": 0, "structural": 1, "analogical": 2, "emergent": 3}
    orders = [tier_order[e.pair.tier.value] for e in essays]
    assert orders == sorted(orders)


def test_render_essay_catalog():
    essays = generate_all_outlines(min_tier=TranslationTier.FORMAL)
    result = render_essay_catalog(essays)
    assert "# Trivium Essay Catalog" in result
    assert "Formal" in result
    assert len(result) > 200


def test_render_catalog_has_all_essays():
    essays = generate_all_outlines(min_tier=TranslationTier.FORMAL)
    result = render_essay_catalog(essays)
    for essay in essays:
        assert essay.title in result
