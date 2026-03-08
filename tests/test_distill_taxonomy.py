"""Tests for distill.taxonomy — pattern definitions and regex matching."""

from organvm_engine.distill.taxonomy import (
    OPERATIONAL_PATTERNS,
    all_pattern_ids,
    get_pattern,
)


def test_all_15_patterns_defined():
    assert len(OPERATIONAL_PATTERNS) == 15


def test_all_pattern_ids_returns_list():
    ids = all_pattern_ids()
    assert isinstance(ids, list)
    assert len(ids) == 15
    assert "scaffold" in ids
    assert "biz-organism" in ids


def test_get_pattern_found():
    p = get_pattern("scaffold")
    assert p is not None
    assert p.id == "scaffold"
    assert p.tier == "T2"
    assert p.phase == "genesis"
    assert p.scope == "system"
    assert p.sop_name_hint == "project-scaffolding"


def test_get_pattern_not_found():
    assert get_pattern("nonexistent") is None


def test_pattern_fields_complete():
    """Every pattern must have required fields populated."""
    for pid, p in OPERATIONAL_PATTERNS.items():
        assert p.id == pid, f"Pattern key {pid} != id {p.id}"
        assert p.label, f"Pattern {pid} missing label"
        assert p.tier in ("T1", "T2", "T3", "T4"), f"Pattern {pid} bad tier: {p.tier}"
        assert p.scope in ("system", "organ", "repo"), f"Pattern {pid} bad scope: {p.scope}"
        assert len(p.regex_signals) > 0, f"Pattern {pid} has no regex signals"
        assert len(p.keyword_signals) > 0, f"Pattern {pid} has no keyword signals"
        assert p.sop_name_hint, f"Pattern {pid} missing sop_name_hint"
        assert p.description, f"Pattern {pid} missing description"


def test_regex_signals_match():
    """Spot-check regex signals actually match expected text."""
    scaffold = get_pattern("scaffold")
    assert scaffold is not None
    matched = any(rx.search("scaffold this project") for rx in scaffold.regex_signals)
    assert matched

    plan = get_pattern("plan-roadmap")
    assert plan is not None
    matched = any(rx.search("devise an extensive plan") for rx in plan.regex_signals)
    assert matched

    completeness = get_pattern("completeness")
    assert completeness is not None
    matched = any(rx.search("wrapped with a beautiful bow") for rx in completeness.regex_signals)
    assert matched


def test_regex_signals_case_insensitive():
    scaffold = get_pattern("scaffold")
    assert scaffold is not None
    matched = any(rx.search("SCAFFOLD THIS") for rx in scaffold.regex_signals)
    assert matched


def test_tier_distribution():
    """Verify expected tier distribution."""
    tiers = [p.tier for p in OPERATIONAL_PATTERNS.values()]
    assert tiers.count("T1") >= 4
    assert tiers.count("T2") >= 5
    assert tiers.count("T3") >= 3
