"""Tests for distill.coverage — SOP-to-pattern coverage analysis.

Covers _sop_matches_pattern, _partial_sop_match, analyze_coverage,
and coverage_summary with various matching scenarios.
"""

from __future__ import annotations

import re
from pathlib import Path

from organvm_engine.distill.coverage import (
    CoverageEntry,
    _partial_sop_match,
    _sop_matches_pattern,
    analyze_coverage,
    coverage_summary,
)
from organvm_engine.distill.taxonomy import OPERATIONAL_PATTERNS, OperationalPattern
from organvm_engine.prompts.clipboard.schema import ClipboardPrompt
from organvm_engine.sop.discover import SOPEntry


def _prompt(text: str, category: str = "General AI Usage") -> ClipboardPrompt:
    """Build a minimal ClipboardPrompt."""
    return ClipboardPrompt(
        id=1,
        content_hash="h",
        date="2026-01-01",
        time="12:00",
        timestamp="2026-01-01T12:00:00",
        source_app="Test",
        bundle_id="com.test",
        category=category,
        confidence="high",
        signals=[],
        word_count=len(text.split()),
        char_count=len(text),
        multi_turn=False,
        file_refs=[],
        tech_mentions=[],
        text=text,
    )


def _sop(
    name: str | None = None,
    title: str | None = None,
    filename: str = "SOP--test.md",
) -> SOPEntry:
    """Build a minimal SOPEntry."""
    return SOPEntry(
        path=Path(f"/fake/{filename}"),
        org="meta-organvm",
        repo="praxis-perpetua",
        filename=filename,
        title=title,
        doc_type="SOP",
        canonical=True,
        has_canonical_header=False,
        sop_name=name,
    )


def _pattern(
    pid: str = "test",
    hint: str = "",
    aliases: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
    categories: tuple[str, ...] = (),
    regex: tuple[str, ...] = (),
) -> OperationalPattern:
    """Build a minimal OperationalPattern."""
    return OperationalPattern(
        id=pid,
        label="Test Pattern",
        tier="T1",
        phase="any",
        scope="system",
        regex_signals=tuple(re.compile(r, re.IGNORECASE) for r in regex),
        keyword_signals=keywords,
        category_affinity=categories,
        sop_name_hint=hint,
        sop_name_aliases=aliases,
    )


# ── _sop_matches_pattern ─────────────────────────────────────────


class TestSopMatchesPattern:
    def test_hint_in_sop_name(self):
        sop = _sop(name="project-scaffolding")
        pat = _pattern(hint="project-scaffolding")
        assert _sop_matches_pattern(sop, pat) is True

    def test_hint_in_sop_title(self):
        """Hint uses substring matching — hyphenated hint must appear in title."""
        sop = _sop(name="unrelated", title="The project-scaffolding guide")
        pat = _pattern(hint="project-scaffolding")
        assert _sop_matches_pattern(sop, pat) is True

    def test_hint_not_in_title_with_spaces(self):
        """Hyphenated hint does NOT match space-separated title."""
        sop = _sop(name="unrelated", title="Project Scaffolding Guide")
        pat = _pattern(hint="project-scaffolding")
        assert _sop_matches_pattern(sop, pat) is False

    def test_hint_partial_match(self):
        """Hint uses substring 'in' matching."""
        sop = _sop(name="full-project-scaffolding-v2")
        pat = _pattern(hint="project-scaffolding")
        assert _sop_matches_pattern(sop, pat) is True

    def test_hint_no_match(self):
        sop = _sop(name="deployment-guide")
        pat = _pattern(hint="project-scaffolding")
        assert _sop_matches_pattern(sop, pat) is False

    def test_alias_in_sop_name(self):
        sop = _sop(name="repo-onboarding")
        pat = _pattern(hint="xxx", aliases=("repo-onboarding", "habitat-creation"))
        assert _sop_matches_pattern(sop, pat) is True

    def test_alias_in_sop_title(self):
        """Alias uses substring matching — hyphenated alias must appear in title."""
        sop = _sop(name="unrelated", title="The habitat-creation protocol")
        pat = _pattern(hint="xxx", aliases=("habitat-creation",))
        assert _sop_matches_pattern(sop, pat) is True

    def test_alias_not_in_title_with_spaces(self):
        """Hyphenated alias does NOT match space-separated title."""
        sop = _sop(name="unrelated", title="Habitat Creation Protocol")
        pat = _pattern(hint="xxx", aliases=("habitat-creation",))
        assert _sop_matches_pattern(sop, pat) is False

    def test_alias_case_insensitive(self):
        sop = _sop(name="REPO-ONBOARDING")
        pat = _pattern(hint="xxx", aliases=("repo-onboarding",))
        assert _sop_matches_pattern(sop, pat) is True

    def test_keyword_threshold_two(self):
        """Needs >= 2 keyword hits in combined name+title."""
        sop = _sop(name="scaffold bootstrap guide")
        pat = _pattern(hint="xxx", keywords=("scaffold", "bootstrap", "init"))
        assert _sop_matches_pattern(sop, pat) is True

    def test_keyword_single_not_enough(self):
        """A single keyword hit is not enough for keyword-only matching."""
        sop = _sop(name="scaffold guide")
        pat = _pattern(hint="xxx", keywords=("scaffold",))
        assert _sop_matches_pattern(sop, pat) is False

    def test_empty_hint_skipped(self):
        """Empty hint should not match everything."""
        sop = _sop(name="anything")
        pat = _pattern(hint="")
        assert _sop_matches_pattern(sop, pat) is False

    def test_none_sop_name_handled(self):
        sop = _sop(name=None, title=None)
        pat = _pattern(hint="scaffolding")
        assert _sop_matches_pattern(sop, pat) is False

    def test_combined_name_title_for_keywords(self):
        """Keywords check both name and title combined."""
        sop = _sop(name="scaffold", title="bootstrap guide")
        pat = _pattern(hint="xxx", keywords=("scaffold", "bootstrap"))
        assert _sop_matches_pattern(sop, pat) is True


# ── _partial_sop_match ────────────────────────────────────────────


class TestPartialSopMatch:
    def test_alias_single_hit_partial(self):
        sop = _sop(name="onboarding process")
        pat = _pattern(aliases=("onboarding",))
        assert _partial_sop_match(sop, pat) is True

    def test_single_keyword_partial(self):
        sop = _sop(name="scaffold guide")
        pat = _pattern(keywords=("scaffold",))
        assert _partial_sop_match(sop, pat) is True

    def test_no_match_partial(self):
        sop = _sop(name="unrelated topic")
        pat = _pattern(aliases=("xxx",), keywords=("yyy",))
        assert _partial_sop_match(sop, pat) is False

    def test_title_checked(self):
        sop = _sop(name="generic", title="Deployment pipeline overview")
        pat = _pattern(keywords=("deployment",))
        assert _partial_sop_match(sop, pat) is True

    def test_case_insensitive_alias(self):
        sop = _sop(name="HABITAT-CREATION")
        pat = _pattern(aliases=("habitat-creation",))
        assert _partial_sop_match(sop, pat) is True


# ── analyze_coverage ──────────────────────────────────────────────


class TestAnalyzeCoverage:
    def test_all_patterns_present(self):
        """Every pattern in the dict should appear in the output."""
        coverage = analyze_coverage({}, [], [])
        assert len(coverage) == len(OPERATIONAL_PATTERNS)

    def test_covered_via_sop_hint(self):
        custom = {"p1": _pattern(pid="p1", hint="my-sop", regex=(r"test",))}
        sops = [_sop(name="my-sop")]
        prompts = [_prompt("test")]
        from organvm_engine.distill.matcher import match_batch
        matched = match_batch(prompts, patterns=custom)
        coverage = analyze_coverage(matched, prompts, sops, patterns=custom)
        entry = coverage[0]
        assert entry.status == "covered"
        assert entry.matching_sops == ["my-sop"]

    def test_uncovered_no_sops(self):
        custom = {"p1": _pattern(pid="p1", hint="xxx", regex=(r"test",))}
        prompts = [_prompt("test")]
        from organvm_engine.distill.matcher import match_batch
        matched = match_batch(prompts, patterns=custom)
        coverage = analyze_coverage(matched, prompts, [], patterns=custom)
        entry = coverage[0]
        assert entry.status == "uncovered"

    def test_partial_status(self):
        """If no direct SOP match but a partial SOP match exists, status is 'partial'."""
        custom = {"p1": _pattern(
            pid="p1", hint="exact-name", keywords=("keyword",), regex=(r"test",),
        )}
        # SOP that matches only via partial (single keyword hit)
        sops = [_sop(name="keyword-guide")]
        prompts = [_prompt("test")]
        from organvm_engine.distill.matcher import match_batch
        matched = match_batch(prompts, patterns=custom)
        coverage = analyze_coverage(matched, prompts, sops, patterns=custom)
        entry = coverage[0]
        assert entry.status == "partial"

    def test_uncovered_when_no_prompts_no_sops(self):
        custom = {"p1": _pattern(pid="p1", hint="xxx")}
        coverage = analyze_coverage({}, [], [], patterns=custom)
        assert coverage[0].status == "uncovered"

    def test_prompt_count_tracked(self):
        custom = {"p1": _pattern(pid="p1", hint="xxx", regex=(r"test",))}
        prompts = [_prompt("test one"), _prompt("test two"), _prompt("test three")]
        from organvm_engine.distill.matcher import match_batch
        matched = match_batch(prompts, patterns=custom)
        coverage = analyze_coverage(matched, prompts, [], patterns=custom)
        assert coverage[0].prompt_count == 3

    def test_sample_prompts_capped_at_three(self):
        custom = {"p1": _pattern(pid="p1", hint="xxx", regex=(r"test",))}
        prompts = [_prompt(f"test prompt {i}") for i in range(10)]
        from organvm_engine.distill.matcher import match_batch
        matched = match_batch(prompts, patterns=custom)
        coverage = analyze_coverage(matched, prompts, [], patterns=custom)
        # sample_prompts truncated at 3
        assert len(coverage[0].sample_prompts) <= 3

    def test_long_sample_prompt_truncated(self):
        custom = {"p1": _pattern(pid="p1", hint="xxx", regex=(r"test",))}
        long_text = "test " + "x" * 300
        prompts = [_prompt(long_text)]
        from organvm_engine.distill.matcher import match_batch
        matched = match_batch(prompts, patterns=custom)
        coverage = analyze_coverage(matched, prompts, [], patterns=custom)
        sample = coverage[0].sample_prompts[0]
        assert sample.endswith("...")
        assert len(sample) <= 204  # 200 chars + "..."

    def test_pattern_label_and_tier_carried(self):
        custom = {"p1": OperationalPattern(
            id="p1", label="My Label", tier="T3", phase="genesis", scope="organ",
            sop_name_hint="hint",
        )}
        coverage = analyze_coverage({}, [], [], patterns=custom)
        entry = coverage[0]
        assert entry.pattern_label == "My Label"
        assert entry.tier == "T3"

    def test_sop_name_hint_carried(self):
        custom = {"p1": _pattern(pid="p1", hint="planning-and-roadmapping")}
        coverage = analyze_coverage({}, [], [], patterns=custom)
        assert coverage[0].sop_name_hint == "planning-and-roadmapping"


# ── coverage_summary ──────────────────────────────────────────────


class TestCoverageSummary:
    def test_basic_counts(self):
        entries = [
            CoverageEntry("a", "A", "T1", "covered"),
            CoverageEntry("b", "B", "T1", "covered"),
            CoverageEntry("c", "C", "T2", "partial"),
            CoverageEntry("d", "D", "T3", "uncovered"),
        ]
        s = coverage_summary(entries)
        assert s["total_patterns"] == 4
        assert s["covered"] == 2
        assert s["partial"] == 1
        assert s["uncovered"] == 1
        assert s["uncovered_patterns"] == ["d"]

    def test_coverage_percentage(self):
        entries = [
            CoverageEntry("a", "A", "T1", "covered"),
            CoverageEntry("b", "B", "T1", "uncovered"),
        ]
        s = coverage_summary(entries)
        assert s["coverage_pct"] == 50.0

    def test_empty_list(self):
        s = coverage_summary([])
        assert s["total_patterns"] == 0
        assert s["covered"] == 0
        assert s["coverage_pct"] == 0.0
        assert s["uncovered_patterns"] == []

    def test_all_covered(self):
        entries = [
            CoverageEntry("a", "A", "T1", "covered"),
            CoverageEntry("b", "B", "T2", "covered"),
        ]
        s = coverage_summary(entries)
        assert s["coverage_pct"] == 100.0
        assert s["uncovered_patterns"] == []

    def test_all_uncovered(self):
        entries = [
            CoverageEntry("x", "X", "T1", "uncovered"),
            CoverageEntry("y", "Y", "T2", "uncovered"),
        ]
        s = coverage_summary(entries)
        assert s["coverage_pct"] == 0.0
        assert s["uncovered_patterns"] == ["x", "y"]


# ── CoverageEntry.to_dict ────────────────────────────────────────


class TestCoverageEntryToDict:
    def test_basic_fields(self):
        e = CoverageEntry(
            pattern_id="p1",
            pattern_label="My Pattern",
            tier="T2",
            status="covered",
            matching_sops=["sop-a"],
            prompt_count=5,
            sample_prompts=["a", "b", "c", "d", "e"],
            sop_name_hint="my-hint",
        )
        d = e.to_dict()
        assert d["pattern_id"] == "p1"
        assert d["pattern_label"] == "My Pattern"
        assert d["tier"] == "T2"
        assert d["status"] == "covered"
        assert d["matching_sops"] == ["sop-a"]
        assert d["prompt_count"] == 5
        # sample_prompts capped at 3 in to_dict
        assert len(d["sample_prompts"]) == 3
        assert d["sop_name_hint"] == "my-hint"

    def test_sample_prompts_truncated_in_dict(self):
        e = CoverageEntry("x", "X", "T1", "uncovered",
                          sample_prompts=["a", "b", "c", "d"])
        d = e.to_dict()
        assert len(d["sample_prompts"]) == 3

    def test_empty_defaults(self):
        e = CoverageEntry("x", "X", "T1", "uncovered")
        d = e.to_dict()
        assert d["matching_sops"] == []
        assert d["prompt_count"] == 0
        assert d["sample_prompts"] == []
        assert d["sop_name_hint"] == ""
