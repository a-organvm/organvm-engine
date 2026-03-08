"""Tests for the distill pipeline — matcher, coverage, and scaffold modules."""

from pathlib import Path

from organvm_engine.distill.coverage import CoverageEntry, analyze_coverage, coverage_summary
from organvm_engine.distill.matcher import (
    MATCH_THRESHOLD,
    PatternMatch,
    match_batch,
    match_prompt,
)
from organvm_engine.distill.scaffold import generate_sop_scaffold, generate_scaffolds
from organvm_engine.distill.taxonomy import OPERATIONAL_PATTERNS, get_pattern
from organvm_engine.prompts.clipboard.schema import ClipboardPrompt
from organvm_engine.sop.discover import SOPEntry


def _make_prompt(text: str, category: str = "General AI Usage") -> ClipboardPrompt:
    """Helper to create a minimal ClipboardPrompt for testing."""
    return ClipboardPrompt(
        id=1,
        content_hash="abc123",
        date="2026-01-01",
        time="12:00",
        timestamp="2026-01-01T12:00:00",
        source_app="Claude",
        bundle_id="com.anthropic.claude",
        category=category,
        confidence="high",
        signals=["imperative_opener"],
        word_count=len(text.split()),
        char_count=len(text),
        multi_turn=False,
        file_refs=[],
        tech_mentions=[],
        text=text,
    )


def _make_sop(name: str, title: str = "") -> SOPEntry:
    """Helper to create a minimal SOPEntry for testing."""
    return SOPEntry(
        path=Path(f"/fake/{name}.md"),
        org="meta-organvm",
        repo="praxis-perpetua",
        filename=f"SOP--{name}.md",
        title=title or name.replace("-", " ").title(),
        doc_type="SOP",
        canonical=True,
        has_canonical_header=False,
        sop_name=name,
    )


# ── Matcher tests ──────────────────────────────────────────────────────


class TestMatchPrompt:
    def test_scaffold_prompt_matches(self):
        prompt = _make_prompt("scaffold this project with boilerplate")
        matches = match_prompt(prompt)
        pattern_ids = [m.pattern_id for m in matches]
        assert "scaffold" in pattern_ids

    def test_plan_roadmap_prompt_matches(self):
        prompt = _make_prompt("devise an extensive plan from alpha to omega")
        matches = match_prompt(prompt)
        pattern_ids = [m.pattern_id for m in matches]
        assert "plan-roadmap" in pattern_ids

    def test_completeness_prompt_matches(self):
        prompt = _make_prompt("wrapped with a beautiful bow, eat off the floor")
        matches = match_prompt(prompt)
        pattern_ids = [m.pattern_id for m in matches]
        assert "completeness" in pattern_ids

    def test_no_match_for_unrelated_text(self):
        prompt = _make_prompt("the weather is nice today")
        matches = match_prompt(prompt)
        assert len(matches) == 0

    def test_category_affinity_boosts_score(self):
        prompt = _make_prompt("scaffold new project", category="ORGANVM System")
        matches = match_prompt(prompt)
        scaffold_match = next((m for m in matches if m.pattern_id == "scaffold"), None)
        assert scaffold_match is not None
        assert scaffold_match.category_match is True
        assert scaffold_match.score >= 0.5  # regex + keyword + category

    def test_sorted_by_score_descending(self):
        prompt = _make_prompt("scaffold bootstrap boilerplate project")
        matches = match_prompt(prompt)
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_threshold_filtering(self):
        prompt = _make_prompt("scaffold this project")
        # High threshold should filter out weak matches
        matches = match_prompt(prompt, threshold=5.0)
        assert len(matches) == 0

    def test_match_result_has_hits(self):
        prompt = _make_prompt("devise an extensive plan for the roadmap")
        matches = match_prompt(prompt)
        plan_match = next((m for m in matches if m.pattern_id == "plan-roadmap"), None)
        assert plan_match is not None
        assert len(plan_match.regex_hits) > 0 or len(plan_match.keyword_hits) > 0


class TestMatchBatch:
    def test_groups_by_pattern(self):
        prompts = [
            _make_prompt("scaffold this project with bootstrap"),
            _make_prompt("devise an extensive plan from alpha to omega"),
            _make_prompt("wrapped with a beautiful bow"),
        ]
        result = match_batch(prompts)
        assert "scaffold" in result
        assert "plan-roadmap" in result
        assert "completeness" in result

    def test_empty_batch(self):
        result = match_batch([])
        assert result == {}

    def test_multiple_prompts_same_pattern(self):
        prompts = [
            _make_prompt("scaffold project A with boilerplate"),
            _make_prompt("bootstrap scaffold project B"),
        ]
        result = match_batch(prompts)
        assert "scaffold" in result
        assert len(result["scaffold"]) == 2


class TestPatternMatchToDict:
    def test_serialization(self):
        m = PatternMatch(
            pattern_id="scaffold",
            score=0.7,
            regex_hits=["scaffold"],
            keyword_hits=["bootstrap"],
            category_match=True,
        )
        d = m.to_dict()
        assert d["pattern_id"] == "scaffold"
        assert d["score"] == 0.7
        assert d["category_match"] is True


# ── Coverage tests ──────────────────────────────────────────────────────


class TestCoverage:
    def test_covered_pattern(self):
        prompts = [_make_prompt("scaffold this project")]
        matched = match_batch(prompts)
        sops = [_make_sop("project-scaffolding", "Project Scaffolding")]
        coverage = analyze_coverage(matched, prompts, sops)
        scaffold_entry = next((e for e in coverage if e.pattern_id == "scaffold"), None)
        assert scaffold_entry is not None
        assert scaffold_entry.status == "covered"
        assert len(scaffold_entry.matching_sops) > 0

    def test_uncovered_pattern(self):
        prompts = [_make_prompt("scaffold this project")]
        matched = match_batch(prompts)
        coverage = analyze_coverage(matched, prompts, sop_entries=[])
        scaffold_entry = next((e for e in coverage if e.pattern_id == "scaffold"), None)
        assert scaffold_entry is not None
        assert scaffold_entry.status == "uncovered"

    def test_all_patterns_in_coverage(self):
        coverage = analyze_coverage({}, [], [])
        assert len(coverage) == len(OPERATIONAL_PATTERNS)

    def test_coverage_summary(self):
        entries = [
            CoverageEntry("a", "A", "T1", "covered", prompt_count=5),
            CoverageEntry("b", "B", "T2", "uncovered", prompt_count=3),
            CoverageEntry("c", "C", "T3", "partial", prompt_count=1),
        ]
        summary = coverage_summary(entries)
        assert summary["total_patterns"] == 3
        assert summary["covered"] == 1
        assert summary["uncovered"] == 1
        assert summary["partial"] == 1
        assert summary["uncovered_patterns"] == ["b"]

    def test_coverage_entry_to_dict(self):
        e = CoverageEntry("x", "X Pattern", "T2", "uncovered", prompt_count=2)
        d = e.to_dict()
        assert d["pattern_id"] == "x"
        assert d["status"] == "uncovered"


# ── Scaffold tests ──────────────────────────────────────────────────────


class TestScaffold:
    def test_generates_valid_frontmatter(self):
        pattern = get_pattern("plan-roadmap")
        assert pattern is not None
        content = generate_sop_scaffold(pattern)
        assert content.startswith("---\n")
        assert "sop: true" in content
        assert "name: planning-and-roadmapping" in content
        assert "scope: system" in content

    def test_includes_sample_prompts(self):
        pattern = get_pattern("scaffold")
        assert pattern is not None
        samples = ["scaffold this project", "bootstrap from template"]
        content = generate_sop_scaffold(pattern, sample_prompts=samples)
        assert "## 6. Prompt Examples" in content
        assert "scaffold this project" in content
        assert "### Example 1" in content

    def test_truncates_long_prompts(self):
        pattern = get_pattern("scaffold")
        assert pattern is not None
        long_text = "x" * 600
        content = generate_sop_scaffold(pattern, sample_prompts=[long_text])
        assert "..." in content

    def test_generate_scaffolds_dry_run(self, tmp_path: Path):
        coverage = [
            CoverageEntry(
                "plan-roadmap", "Planning", "T2", "uncovered",
                sop_name_hint="planning-and-roadmapping",
            ),
            CoverageEntry(
                "scaffold", "Scaffolding", "T2", "covered",
                sop_name_hint="project-scaffolding",
            ),
        ]
        written = generate_scaffolds(coverage, tmp_path, dry_run=True)
        assert len(written) == 1
        assert "planning-and-roadmapping" in written[0].name
        # Dry run: file should not exist
        assert not written[0].exists()

    def test_generate_scaffolds_write(self, tmp_path: Path):
        coverage = [
            CoverageEntry(
                "plan-roadmap", "Planning", "T2", "uncovered",
                sop_name_hint="planning-and-roadmapping",
            ),
        ]
        written = generate_scaffolds(coverage, tmp_path, dry_run=False)
        assert len(written) == 1
        assert written[0].exists()
        content = written[0].read_text()
        assert "sop: true" in content

    def test_skips_existing_files(self, tmp_path: Path):
        existing = tmp_path / "SOP--planning-and-roadmapping.md"
        existing.write_text("already here")
        coverage = [
            CoverageEntry(
                "plan-roadmap", "Planning", "T2", "uncovered",
                sop_name_hint="planning-and-roadmapping",
            ),
        ]
        written = generate_scaffolds(coverage, tmp_path, dry_run=False)
        assert len(written) == 0
