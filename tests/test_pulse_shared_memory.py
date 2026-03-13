"""Tests for organvm_engine.pulse.shared_memory — cross-agent knowledge store."""

from __future__ import annotations

import json
import time

import pytest

from organvm_engine.pulse.shared_memory import (
    Insight,
    insight_summary,
    query_insights,
    recent_insights,
    record_insight,
)


@pytest.fixture(autouse=True)
def _isolated_memory(tmp_path, monkeypatch):
    """Route the shared memory store to a temp directory."""
    memory_file = tmp_path / "shared-memory.jsonl"
    monkeypatch.setattr(
        "organvm_engine.pulse.shared_memory._memory_path",
        lambda: memory_file,
    )
    return memory_file


# ---------------------------------------------------------------------------
# Insight dataclass
# ---------------------------------------------------------------------------

class TestInsight:
    def test_insight_creation(self):
        """Insight populates all fields including auto-timestamp."""
        ins = Insight(agent="claude", category="finding", content="test")
        assert ins.agent == "claude"
        assert ins.category == "finding"
        assert ins.content == "test"
        assert ins.timestamp  # non-empty
        assert "T" in ins.timestamp

    def test_insight_defaults(self):
        """Optional fields default correctly."""
        ins = Insight(agent="claude", category="finding", content="x")
        assert ins.tags == []
        assert ins.organ == ""
        assert ins.repo == ""

    def test_insight_to_dict(self):
        """to_dict round-trips all fields."""
        ins = Insight(
            agent="gemini",
            category="decision",
            content="chose X over Y",
            tags=["architecture"],
            organ="ORGAN-I",
            repo="my-repo",
        )
        d = ins.to_dict()
        assert d["agent"] == "gemini"
        assert d["category"] == "decision"
        assert d["organ"] == "ORGAN-I"
        assert d["tags"] == ["architecture"]

    def test_insight_to_json(self):
        """to_json produces valid compact JSON."""
        ins = Insight(agent="codex", category="warning", content="w")
        raw = ins.to_json()
        data = json.loads(raw)
        assert data["agent"] == "codex"
        assert data["category"] == "warning"


# ---------------------------------------------------------------------------
# record_insight
# ---------------------------------------------------------------------------

class TestRecordInsight:
    def test_record_creates_file(self, _isolated_memory):
        """Recording creates the JSONL file."""
        record_insight("claude", "finding", "something interesting")
        path = _isolated_memory
        assert path.is_file()
        line = path.read_text().strip()
        data = json.loads(line)
        assert data["agent"] == "claude"
        assert data["content"] == "something interesting"

    def test_record_appends(self, _isolated_memory):
        """Multiple records append to the same file."""
        record_insight("claude", "finding", "one")
        record_insight("gemini", "decision", "two")
        record_insight("codex", "pattern", "three")
        lines = _isolated_memory.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_record_with_all_fields(self, _isolated_memory):
        """Record with all optional fields populates correctly."""
        ins = record_insight(
            agent="claude",
            category="warning",
            content="potential issue",
            tags=["security", "auth"],
            organ="ORGAN-III",
            repo="my-service",
        )
        assert isinstance(ins, Insight)
        assert ins.organ == "ORGAN-III"
        assert ins.tags == ["security", "auth"]

    def test_record_returns_insight(self):
        """record_insight returns the created Insight object."""
        ins = record_insight("claude", "todo", "fix the thing")
        assert isinstance(ins, Insight)
        assert ins.content == "fix the thing"


# ---------------------------------------------------------------------------
# query_insights
# ---------------------------------------------------------------------------

class TestQueryInsights:
    def test_query_all(self):
        """Query with no filters returns all insights."""
        record_insight("claude", "finding", "one")
        record_insight("gemini", "decision", "two")
        record_insight("codex", "pattern", "three")
        results = query_insights(limit=100)
        assert len(results) == 3

    def test_query_by_category(self):
        """Filter by category returns only matching insights."""
        record_insight("claude", "finding", "f1")
        record_insight("claude", "decision", "d1")
        record_insight("claude", "finding", "f2")
        results = query_insights(category="finding", limit=100)
        assert len(results) == 2
        assert all(r.category == "finding" for r in results)

    def test_query_by_agent(self):
        """Filter by agent returns only that agent's insights."""
        record_insight("claude", "finding", "c1")
        record_insight("gemini", "finding", "g1")
        record_insight("claude", "finding", "c2")
        results = query_insights(agent="claude", limit=100)
        assert len(results) == 2
        assert all(r.agent == "claude" for r in results)

    def test_query_by_organ(self):
        """Filter by organ returns only matching insights."""
        record_insight("claude", "finding", "one", organ="ORGAN-I")
        record_insight("claude", "finding", "two", organ="ORGAN-III")
        record_insight("claude", "finding", "three", organ="ORGAN-I")
        results = query_insights(organ="ORGAN-I", limit=100)
        assert len(results) == 2
        assert all(r.organ == "ORGAN-I" for r in results)

    def test_query_by_since(self):
        """Filter by since timestamp excludes older insights."""
        record_insight("claude", "finding", "old")
        cutoff = Insight(agent="x", category="x", content="x").timestamp
        time.sleep(0.01)
        record_insight("claude", "finding", "new")
        results = query_insights(since=cutoff, limit=100)
        assert len(results) >= 1
        assert all(r.content == "new" for r in results)

    def test_query_limit(self):
        """Limit controls the maximum number of returned insights."""
        for i in range(10):
            record_insight("claude", "finding", f"item-{i}")
        results = query_insights(limit=3)
        assert len(results) == 3
        # Should be the last 3
        assert results[-1].content == "item-9"

    def test_query_combined_filters(self):
        """Multiple filters are AND-combined."""
        record_insight("claude", "finding", "cf")
        record_insight("gemini", "finding", "gf")
        record_insight("claude", "decision", "cd")
        record_insight("gemini", "decision", "gd")
        results = query_insights(agent="claude", category="finding", limit=100)
        assert len(results) == 1
        assert results[0].content == "cf"

    def test_query_empty_store(self):
        """Query on empty store returns empty list."""
        results = query_insights()
        assert results == []


# ---------------------------------------------------------------------------
# recent_insights
# ---------------------------------------------------------------------------

class TestRecentInsights:
    def test_recent_default(self):
        """recent_insights returns the last N insights."""
        for i in range(15):
            record_insight("claude", "finding", f"item-{i}")
        results = recent_insights(limit=5)
        assert len(results) == 5
        assert results[-1].content == "item-14"
        assert results[0].content == "item-10"

    def test_recent_empty(self):
        """recent_insights on empty store returns empty list."""
        results = recent_insights()
        assert results == []

    def test_recent_fewer_than_limit(self):
        """recent_insights returns all when fewer than limit."""
        record_insight("claude", "finding", "only-one")
        results = recent_insights(limit=10)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# insight_summary
# ---------------------------------------------------------------------------

class TestInsightSummary:
    def test_summary_empty(self):
        """Summary of empty store shows zero totals."""
        s = insight_summary()
        assert s["total"] == 0
        assert s["by_category"] == {}
        assert s["by_agent"] == {}
        assert s["by_organ"] == {}

    def test_summary_counts(self):
        """Summary correctly counts by category, agent, and organ."""
        record_insight("claude", "finding", "f1", organ="ORGAN-I")
        record_insight("claude", "finding", "f2", organ="ORGAN-I")
        record_insight("gemini", "decision", "d1", organ="ORGAN-III")
        record_insight("codex", "warning", "w1")

        s = insight_summary()
        assert s["total"] == 4
        assert s["by_category"]["finding"] == 2
        assert s["by_category"]["decision"] == 1
        assert s["by_category"]["warning"] == 1
        assert s["by_agent"]["claude"] == 2
        assert s["by_agent"]["gemini"] == 1
        assert s["by_agent"]["codex"] == 1
        assert s["by_organ"]["ORGAN-I"] == 2
        assert s["by_organ"]["ORGAN-III"] == 1

    def test_summary_excludes_empty_organ(self):
        """Insights with no organ are not counted in by_organ."""
        record_insight("claude", "finding", "no-organ")
        s = insight_summary()
        assert s["by_organ"] == {}
