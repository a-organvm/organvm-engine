"""Tests for distill.matcher — prompt-to-pattern scoring and batch matching.

Covers _score_prompt internals, match_prompt edge cases, match_batch
grouping/sorting, custom pattern dicts, and PatternMatch serialization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from organvm_engine.distill.matcher import (
    MATCH_THRESHOLD,
    SCORE_CATEGORY,
    SCORE_KEYWORD,
    SCORE_REGEX,
    PatternMatch,
    _score_prompt,
    match_batch,
    match_prompt,
)
from organvm_engine.distill.taxonomy import OperationalPattern
from organvm_engine.prompts.clipboard.schema import ClipboardPrompt


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


def _pattern(
    pid: str = "test-pat",
    regex: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
    categories: tuple[str, ...] = (),
) -> OperationalPattern:
    """Build a minimal OperationalPattern with compiled regex."""
    return OperationalPattern(
        id=pid,
        label="Test Pattern",
        tier="T1",
        phase="any",
        scope="system",
        regex_signals=tuple(re.compile(r, re.IGNORECASE) for r in regex),
        keyword_signals=keywords,
        category_affinity=categories,
        sop_name_hint="test-hint",
    )


# ── Score constants ───────────────────────────────────────────────


class TestScoreConstants:
    def test_regex_score(self):
        assert SCORE_REGEX == 0.3

    def test_keyword_score(self):
        assert SCORE_KEYWORD == 0.1

    def test_category_score(self):
        assert SCORE_CATEGORY == 0.2

    def test_match_threshold(self):
        assert MATCH_THRESHOLD == 0.3


# ── _score_prompt ─────────────────────────────────────────────────


class TestScorePrompt:
    def test_zero_score_on_no_signals(self):
        pat = _pattern(regex=(), keywords=(), categories=())
        m = _score_prompt("hello world", "General", pat)
        assert m.score == 0.0
        assert m.regex_hits == []
        assert m.keyword_hits == []
        assert m.category_match is False

    def test_regex_hit_adds_score(self):
        pat = _pattern(regex=(r"hello",))
        m = _score_prompt("hello world", "General", pat)
        assert m.score == SCORE_REGEX
        assert len(m.regex_hits) == 1
        assert m.regex_hits[0] == "hello"

    def test_multiple_regex_hits_accumulate(self):
        pat = _pattern(regex=(r"hello", r"world"))
        m = _score_prompt("hello world", "General", pat)
        assert m.score == 2 * SCORE_REGEX
        assert len(m.regex_hits) == 2

    def test_keyword_hit_case_insensitive(self):
        pat = _pattern(keywords=("HELLO",))
        m = _score_prompt("hello world", "General", pat)
        assert m.score == SCORE_KEYWORD
        assert "HELLO" in m.keyword_hits

    def test_keyword_substring_match(self):
        """Keywords use 'in' matching, so substring matches count."""
        pat = _pattern(keywords=("llo",))
        m = _score_prompt("hello", "General", pat)
        assert m.score == SCORE_KEYWORD

    def test_category_affinity_match(self):
        pat = _pattern(categories=("GitHub/CI/CD",))
        m = _score_prompt("anything", "GitHub/CI/CD", pat)
        assert m.score == SCORE_CATEGORY
        assert m.category_match is True

    def test_category_no_match(self):
        pat = _pattern(categories=("GitHub/CI/CD",))
        m = _score_prompt("anything", "Data/Research", pat)
        assert m.score == 0.0
        assert m.category_match is False

    def test_combined_scores(self):
        pat = _pattern(
            regex=(r"scaffold",),
            keywords=("bootstrap",),
            categories=("ORGANVM System",),
        )
        m = _score_prompt("scaffold bootstrap", "ORGANVM System", pat)
        expected = SCORE_REGEX + SCORE_KEYWORD + SCORE_CATEGORY
        assert abs(m.score - expected) < 1e-9
        assert m.category_match is True
        assert len(m.regex_hits) == 1
        assert len(m.keyword_hits) == 1

    def test_regex_no_match(self):
        pat = _pattern(regex=(r"^xyz$",))
        m = _score_prompt("hello", "General", pat)
        assert m.score == 0.0
        assert m.regex_hits == []

    def test_pattern_id_carried_through(self):
        pat = _pattern(pid="my-id", regex=(r"hi",))
        m = _score_prompt("hi", "General", pat)
        assert m.pattern_id == "my-id"


# ── match_prompt ──────────────────────────────────────────────────


class TestMatchPrompt:
    def test_returns_empty_for_unrelated_text(self):
        p = _prompt("the sky is blue")
        matches = match_prompt(p)
        assert matches == []

    def test_custom_patterns_dict(self):
        custom = {
            "p1": _pattern(pid="p1", regex=(r"magic",)),
        }
        p = _prompt("magic spell")
        matches = match_prompt(p, patterns=custom)
        assert len(matches) == 1
        assert matches[0].pattern_id == "p1"

    def test_custom_threshold(self):
        custom = {
            "p1": _pattern(pid="p1", regex=(r"magic",)),
        }
        p = _prompt("magic")
        # Threshold below the regex score => match
        matches = match_prompt(p, patterns=custom, threshold=0.1)
        assert len(matches) == 1
        # Threshold above the regex score => no match
        matches = match_prompt(p, patterns=custom, threshold=0.5)
        assert len(matches) == 0

    def test_sorted_descending(self):
        custom = {
            "weak": _pattern(pid="weak", keywords=("one",)),
            "strong": _pattern(pid="strong", regex=(r"one",), keywords=("one",)),
        }
        p = _prompt("one word")
        matches = match_prompt(p, patterns=custom, threshold=0.0)
        if len(matches) >= 2:
            assert matches[0].score >= matches[1].score

    def test_multiple_patterns_matched(self):
        custom = {
            "a": _pattern(pid="a", regex=(r"alpha",)),
            "b": _pattern(pid="b", regex=(r"alpha",)),
        }
        p = _prompt("alpha text")
        matches = match_prompt(p, patterns=custom)
        assert len(matches) == 2

    def test_default_patterns_used(self):
        """When patterns=None, should use OPERATIONAL_PATTERNS."""
        p = _prompt("scaffold this project with boilerplate")
        matches = match_prompt(p)
        ids = [m.pattern_id for m in matches]
        assert "scaffold" in ids

    def test_research_pattern_matches(self):
        p = _prompt("analyze the competitive landscape and market gap")
        matches = match_prompt(p)
        ids = [m.pattern_id for m in matches]
        assert "research" in ids

    def test_commit_push_matches(self):
        p = _prompt("stage all changes and git push origin main")
        matches = match_prompt(p)
        ids = [m.pattern_id for m in matches]
        assert "commit-push" in ids


# ── match_batch ───────────────────────────────────────────────────


class TestMatchBatch:
    def test_empty_input(self):
        assert match_batch([]) == {}

    def test_groups_by_pattern_id(self):
        custom = {
            "a": _pattern(pid="a", regex=(r"alpha",)),
            "b": _pattern(pid="b", regex=(r"beta",)),
        }
        prompts = [_prompt("alpha text"), _prompt("beta text")]
        result = match_batch(prompts, patterns=custom)
        assert "a" in result
        assert "b" in result
        assert len(result["a"]) == 1
        assert len(result["b"]) == 1

    def test_multiple_prompts_same_pattern(self):
        custom = {"a": _pattern(pid="a", regex=(r"hello",))}
        prompts = [_prompt("hello one"), _prompt("hello two")]
        result = match_batch(prompts, patterns=custom)
        assert len(result["a"]) == 2

    def test_sorted_by_score_within_group(self):
        custom = {
            "a": _pattern(pid="a", regex=(r"hello",), keywords=("world",)),
        }
        prompts = [
            _prompt("hello"),  # regex only: 0.3
            _prompt("hello world"),  # regex + keyword: 0.4
        ]
        result = match_batch(prompts, patterns=custom)
        entries = result["a"]
        assert entries[0][1].score >= entries[1][1].score

    def test_prompt_object_preserved_in_result(self):
        custom = {"a": _pattern(pid="a", regex=(r"test",))}
        p = _prompt("test input")
        result = match_batch([p], patterns=custom)
        prompt_out, match_out = result["a"][0]
        assert prompt_out is p
        assert isinstance(match_out, PatternMatch)

    def test_threshold_applied(self):
        custom = {"a": _pattern(pid="a", regex=(r"hello",))}
        prompts = [_prompt("hello")]
        # Threshold above possible score
        result = match_batch(prompts, patterns=custom, threshold=5.0)
        assert result == {}

    def test_unmatched_prompt_excluded(self):
        custom = {"a": _pattern(pid="a", regex=(r"hello",))}
        prompts = [_prompt("goodbye world")]
        result = match_batch(prompts, patterns=custom)
        assert result == {}

    def test_prompt_matches_multiple_patterns(self):
        custom = {
            "a": _pattern(pid="a", regex=(r"scaffold",)),
            "b": _pattern(pid="b", regex=(r"scaffold",)),
        }
        prompts = [_prompt("scaffold project")]
        result = match_batch(prompts, patterns=custom)
        assert "a" in result
        assert "b" in result


# ── PatternMatch.to_dict ──────────────────────────────────────────


class TestPatternMatchToDict:
    def test_basic_serialization(self):
        m = PatternMatch(
            pattern_id="test",
            score=0.333333333,
            regex_hits=["rx1"],
            keyword_hits=["kw1"],
            category_match=True,
        )
        d = m.to_dict()
        assert d["pattern_id"] == "test"
        assert d["score"] == 0.333
        assert d["regex_hits"] == ["rx1"]
        assert d["keyword_hits"] == ["kw1"]
        assert d["category_match"] is True

    def test_score_rounding(self):
        m = PatternMatch(pattern_id="x", score=0.1 + 0.2)
        d = m.to_dict()
        assert d["score"] == 0.3

    def test_default_fields(self):
        m = PatternMatch(pattern_id="x", score=0.0)
        d = m.to_dict()
        assert d["regex_hits"] == []
        assert d["keyword_hits"] == []
        assert d["category_match"] is False
