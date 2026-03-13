"""Cross-agent shared memory — a knowledge store any agent can write to and read.

Provides a lightweight, agent-agnostic store for decisions, findings,
patterns, warnings, and todos.  All agents (Claude, Gemini, Codex, human)
can record insights and query the store.  The backing store is an
append-only JSONL file at ~/.organvm/shared-memory.jsonl, following the
same pattern as the event bus.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Valid categories
# ---------------------------------------------------------------------------

VALID_CATEGORIES = ("decision", "finding", "pattern", "warning", "todo")


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Insight:
    """A single knowledge entry in the shared memory store."""

    agent: str
    category: str
    content: str
    tags: list[str] = field(default_factory=list)
    organ: str = ""
    repo: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "category": self.category,
            "content": self.content,
            "tags": self.tags,
            "organ": self.organ,
            "repo": self.repo,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _memory_path() -> Path:
    return Path.home() / ".organvm" / "shared-memory.jsonl"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_insight(
    agent: str,
    category: str,
    content: str,
    tags: list[str] | None = None,
    organ: str = "",
    repo: str = "",
) -> Insight:
    """Record an insight to the shared memory store.

    Args:
        agent: Identifier for the recording agent (e.g. "claude", "gemini").
        category: One of "decision", "finding", "pattern", "warning", "todo".
        content: Free-text description of the insight.
        tags: Optional list of keyword tags.
        organ: Optional organ scope (e.g. "ORGAN-I", "META-ORGANVM").
        repo: Optional repo scope.

    Returns:
        The recorded Insight.
    """
    insight = Insight(
        agent=agent,
        category=category,
        content=content,
        tags=tags or [],
        organ=organ,
        repo=repo,
    )
    path = _memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(insight.to_json() + "\n")
    return insight


def _load_all() -> list[Insight]:
    """Read all insights from the store."""
    path = _memory_path()
    if not path.is_file():
        return []

    insights: list[Insight] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        insights.append(Insight(
            agent=data.get("agent", ""),
            category=data.get("category", ""),
            content=data.get("content", ""),
            tags=data.get("tags", []),
            organ=data.get("organ", ""),
            repo=data.get("repo", ""),
            timestamp=data.get("timestamp", ""),
        ))
    return insights


def query_insights(
    category: str | None = None,
    organ: str | None = None,
    agent: str | None = None,
    since: str | None = None,
    limit: int = 50,
) -> list[Insight]:
    """Query insights with optional filters.

    Args:
        category: Filter by category (e.g. "decision", "warning").
        organ: Filter by organ scope.
        agent: Filter by recording agent.
        since: ISO timestamp — only return insights after this time.
        limit: Maximum number of results (from the tail).

    Returns:
        List of matching insights, most recent last.
    """
    all_insights = _load_all()
    filtered: list[Insight] = []

    for ins in all_insights:
        if category and ins.category != category:
            continue
        if organ and ins.organ != organ:
            continue
        if agent and ins.agent != agent:
            continue
        if since and ins.timestamp <= since:
            continue
        filtered.append(ins)

    return filtered[-limit:]


def recent_insights(limit: int = 10) -> list[Insight]:
    """Return the last *limit* insights from the store.

    Args:
        limit: Number of recent insights to return.

    Returns:
        List of the most recent insights.
    """
    all_insights = _load_all()
    return all_insights[-limit:]


def insight_summary() -> dict:
    """Aggregate summary of the shared memory store.

    Returns:
        Dict with counts by category, by agent, by organ, and total.
    """
    all_insights = _load_all()

    by_category: dict[str, int] = {}
    by_agent: dict[str, int] = {}
    by_organ: dict[str, int] = {}

    for ins in all_insights:
        by_category[ins.category] = by_category.get(ins.category, 0) + 1
        by_agent[ins.agent] = by_agent.get(ins.agent, 0) + 1
        if ins.organ:
            by_organ[ins.organ] = by_organ.get(ins.organ, 0) + 1

    return {
        "total": len(all_insights),
        "by_category": by_category,
        "by_agent": by_agent,
        "by_organ": by_organ,
    }
