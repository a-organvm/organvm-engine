"""Dependency flow visualization — annotate the seed graph with activity levels.

For each edge in the seed graph, this module checks recent events and
coordination claims to determine whether the edge is actively carrying
work, merely warm, or fully dormant.  The result is a FlowProfile that
gives an at-a-glance view of where energy is flowing in the system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EdgeActivity:
    """Activity annotation for a single edge in the seed graph."""

    source: str
    target: str
    edge_type: str
    activity_level: str  # "active" / "warm" / "dormant"
    recent_events: int = 0
    last_event_age_days: float | None = None
    sessions_touching_both: int = 0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
            "activity_level": self.activity_level,
            "recent_events": self.recent_events,
            "last_event_age_days": self.last_event_age_days,
            "sessions_touching_both": self.sessions_touching_both,
        }


@dataclass
class FlowProfile:
    """Aggregate flow analysis of the entire seed graph."""

    edges: list[EdgeActivity] = field(default_factory=list)
    active_count: int = 0
    warm_count: int = 0
    dormant_count: int = 0
    flow_score: float = 0.0
    hotspots: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "edges": [e.to_dict() for e in self.edges],
            "active_count": self.active_count,
            "warm_count": self.warm_count,
            "dormant_count": self.dormant_count,
            "flow_score": self.flow_score,
            "hotspots": self.hotspots,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _claims_path() -> Path:
    return Path.home() / ".organvm" / "claims.jsonl"


def _read_claims(hours: int) -> list[dict]:
    """Read claims from the last *hours* hours."""
    path = _claims_path()
    if not path.is_file():
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    claims: list[dict] = []

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("timestamp", "") > cutoff:
            claims.append(entry)

    return claims


def _node_matches_event(node: str, event_source: str) -> bool:
    """Check if a graph node identity matches an event source.

    Node format: "org/repo" or bare org name.
    Event source: typically "org/repo" or "engine" or similar.
    """
    if not event_source:
        return False
    # Direct match
    if node == event_source:
        return True
    # Node "orgA/repo1" matches source "repo1"
    if "/" in node:
        repo_part = node.split("/", maxsplit=1)[1]
        if repo_part == event_source:
            return True
    # Source "orgA/repo1" matches node "repo1"
    if "/" in event_source:
        repo_part = event_source.split("/", maxsplit=1)[1]
        if node == repo_part:
            return True
    return False


def _node_matches_claim(node: str, claim: dict) -> bool:
    """Check if a graph node matches a coordination claim."""
    organ = claim.get("organ", "")
    repo = claim.get("repo", "")
    if not organ and not repo:
        return False

    claim_identity = f"{organ}/{repo}" if organ and repo else organ or repo

    if node == claim_identity:
        return True
    if "/" in node:
        repo_part = node.split("/", maxsplit=1)[1]
        if repo_part == repo:
            return True
    return False


def _event_age_days(event_ts: str) -> float | None:
    """Compute the age of an event timestamp in days."""
    try:
        # Handle both Z-suffix and +00:00 timezone formats
        ts_str = event_ts.replace("Z", "+00:00")
        evt_dt = datetime.fromisoformat(ts_str)
        now = datetime.now(timezone.utc)
        delta = now - evt_dt
        return delta.total_seconds() / 86400.0
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_flow(graph: object, hours: int = 168) -> FlowProfile:
    """Annotate seed graph edges with activity levels.

    For each edge, checks:
        - Recent events mentioning source or target repos
        - Coordination claims for sessions touching repos on both sides

    Classification:
        - active: event in last 24h or claim in last 48h
        - warm: event in last 7d (168h)
        - dormant: no recent activity

    Args:
        graph: A SeedGraph instance with .edges (list of (src, tgt, type) tuples).
        hours: Total lookback window in hours (default 168 = 7 days).

    Returns:
        FlowProfile with annotated edges and aggregate metrics.
    """
    from organvm_engine.pulse.events import replay

    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    events = replay(since=since, limit=1000)
    claims = _read_claims(hours)

    edge_activities: list[EdgeActivity] = []
    active_edges_per_node: dict[str, int] = {}

    for src, tgt, edge_type in graph.edges:
        # Count events mentioning source or target
        relevant_events: list = []
        for e in events:
            # Match on event source
            if _node_matches_event(src, e.source) or _node_matches_event(
                tgt, e.source,
            ):
                relevant_events.append(e)
                continue
            # Also match on payload subject_entity or consumers (events use
            # module names like "pulse"/"metrics" as source, but may reference
            # specific repos in their payload)
            payload = e.payload if hasattr(e, "payload") and isinstance(e.payload, dict) else {}
            subject = payload.get("subject_entity", "")
            if subject and (
                _node_matches_event(src, subject) or _node_matches_event(tgt, subject)
            ):
                relevant_events.append(e)

        # Count claims touching both sides
        src_claims = [c for c in claims if _node_matches_claim(src, c)]
        tgt_claims = [c for c in claims if _node_matches_claim(tgt, c)]
        # Sessions that touched both = agent IDs that appear in both sets
        src_agents = {c.get("agent_id") for c in src_claims}
        tgt_agents = {c.get("agent_id") for c in tgt_claims}
        both_count = len(src_agents & tgt_agents)

        # Find the most recent event age
        last_age: float | None = None
        for e in reversed(relevant_events):
            age = _event_age_days(e.timestamp)
            if age is not None:
                last_age = age
                break

        # Classify activity level
        has_recent_event = any(
            (_event_age_days(e.timestamp) or 999) < 1.0
            for e in relevant_events
        )
        has_recent_claim = any(
            (_event_age_days(c.get("timestamp", "")) or 999) < 2.0
            for c in src_claims + tgt_claims
        )

        if has_recent_event or has_recent_claim:
            level = "active"
        elif relevant_events:
            level = "warm"
        else:
            level = "dormant"

        ea = EdgeActivity(
            source=src,
            target=tgt,
            edge_type=edge_type,
            activity_level=level,
            recent_events=len(relevant_events),
            last_event_age_days=round(last_age, 2) if last_age is not None else None,
            sessions_touching_both=both_count,
        )
        edge_activities.append(ea)

        # Track active edges per node for hotspot detection
        if level == "active":
            active_edges_per_node[src] = active_edges_per_node.get(src, 0) + 1
            active_edges_per_node[tgt] = active_edges_per_node.get(tgt, 0) + 1

    # Aggregate counts
    active_count = sum(1 for e in edge_activities if e.activity_level == "active")
    warm_count = sum(1 for e in edge_activities if e.activity_level == "warm")
    dormant_count = sum(1 for e in edge_activities if e.activity_level == "dormant")
    total = len(edge_activities)

    # Flow score: weighted activity ratio
    if total > 0:
        flow_score = round(
            (active_count * 1.0 + warm_count * 0.3) / total * 100, 1,
        )
    else:
        flow_score = 0.0

    # Hotspots: top 5 nodes by active edge count
    sorted_nodes = sorted(
        active_edges_per_node.items(), key=lambda x: x[1], reverse=True,
    )
    hotspots = [node for node, _count in sorted_nodes[:5]]

    return FlowProfile(
        edges=edge_activities,
        active_count=active_count,
        warm_count=warm_count,
        dormant_count=dormant_count,
        flow_score=flow_score,
        hotspots=hotspots,
    )


def flow_to_dict(profile: FlowProfile) -> dict:
    """Serialize a FlowProfile to a plain dict.

    Args:
        profile: The FlowProfile to serialize.

    Returns:
        Dictionary representation suitable for JSON output.
    """
    return profile.to_dict()
