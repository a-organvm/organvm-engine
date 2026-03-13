"""Session continuity — briefing layer for new agent sessions.

When a new session starts, this module assembles a briefing of recent
system activity so that agents don't begin from scratch.  It pulls from
the event bus, the coordination claims log, and the affective layer to
give an immediate sense of where the system stands and what happened
since the last session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class SessionBriefing:
    """Summary of recent system activity for session onboarding."""

    recent_events: list = field(default_factory=list)  # list[Event]
    recent_claims: list[dict] = field(default_factory=list)
    active_agents: list[str] = field(default_factory=list)
    last_mood: object | None = None  # MoodReading | None
    system_delta: str = "stable"  # "improving" / "declining" / "stable"
    key_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        from dataclasses import asdict

        from organvm_engine.pulse.events import Event

        mood_dict = None
        if self.last_mood is not None:
            mood_dict = self.last_mood.to_dict()

        return {
            "recent_events": [
                asdict(e) if isinstance(e, Event) else e
                for e in self.recent_events
            ],
            "recent_claims": self.recent_claims,
            "active_agents": self.active_agents,
            "last_mood": mood_dict,
            "system_delta": self.system_delta,
            "key_changes": self.key_changes,
        }


# ---------------------------------------------------------------------------
# Claims reading
# ---------------------------------------------------------------------------

def _claims_path() -> Path:
    return Path.home() / ".organvm" / "claims.jsonl"


def _read_recent_claims(hours: int = 24) -> list[dict]:
    """Read claim entries from the last *hours* hours."""
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

        ts = entry.get("timestamp", "")
        if ts > cutoff:
            claims.append(entry)

    return claims


def _active_agents_from_claims(claims: list[dict]) -> list[str]:
    """Extract unique agent IDs that have punched in but not out."""
    punched_in: set[str] = set()
    punched_out: set[str] = set()

    for claim in claims:
        agent = claim.get("agent_id", "")
        if not agent:
            continue
        action = claim.get("action", "")
        if action == "punch_in":
            punched_in.add(agent)
        elif action == "punch_out":
            punched_out.add(agent)

    return sorted(punched_in - punched_out)


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------

def _compute_system_delta(events: list) -> str:
    """Derive a simple improving/declining/stable signal from recent events."""
    from organvm_engine.pulse.events import GATE_CHANGED, REPO_PROMOTED

    if not events:
        return "stable"

    promotions = sum(1 for e in events if e.event_type == REPO_PROMOTED)
    gate_ups = 0
    gate_downs = 0
    for e in events:
        if e.event_type == GATE_CHANGED:
            direction = e.payload.get("direction", "")
            if direction == "up":
                gate_ups += 1
            elif direction == "down":
                gate_downs += 1

    positive = promotions + gate_ups
    negative = gate_downs

    if positive > negative + 1:
        return "improving"
    if negative > positive + 1:
        return "declining"
    return "stable"


def _extract_key_changes(events: list) -> list[str]:
    """Build human-readable change descriptions from recent events."""
    from organvm_engine.pulse.events import (
        GATE_CHANGED,
        MOOD_SHIFTED,
        REPO_PROMOTED,
        SESSION_ENDED,
    )

    changes: list[str] = []
    for e in events:
        if e.event_type == REPO_PROMOTED:
            repo = e.payload.get("repo", e.source)
            new_status = e.payload.get("new_status", "?")
            changes.append(f"{repo} promoted to {new_status}")
        elif e.event_type == GATE_CHANGED:
            gate = e.payload.get("gate", "?")
            direction = e.payload.get("direction", "?")
            changes.append(f"Gate {gate} moved {direction}")
        elif e.event_type == MOOD_SHIFTED:
            new_mood = e.payload.get("mood", "?")
            changes.append(f"System mood shifted to {new_mood}")
        elif e.event_type == SESSION_ENDED:
            agent = e.payload.get("agent", e.source)
            changes.append(f"Session ended ({agent})")

    return changes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_briefing(hours: int = 24) -> SessionBriefing:
    """Assemble a session briefing from the last *hours* of activity.

    Reads:
        - Recent events from the pulse event bus
        - Coordination claims JSONL for agent activity
        - Last mood reading from mood-shifted events

    Args:
        hours: Lookback window in hours (default 24).

    Returns:
        SessionBriefing summarising recent system activity.
    """
    from organvm_engine.pulse.events import MOOD_SHIFTED, replay

    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    events = replay(since=since, limit=200)

    claims = _read_recent_claims(hours)
    active = _active_agents_from_claims(claims)

    # Find the last mood-shifted event for the mood reading
    last_mood = None
    for e in reversed(events):
        if e.event_type == MOOD_SHIFTED:
            from organvm_engine.pulse.affective import MoodReading, SystemMood

            mood_val = e.payload.get("mood", "steady")
            try:
                mood_enum = SystemMood(mood_val)
            except ValueError:
                mood_enum = SystemMood.STEADY
            from organvm_engine.pulse.affective import MoodFactors

            last_mood = MoodReading(mood=mood_enum, factors=MoodFactors())
            break

    delta = _compute_system_delta(events)
    key_changes = _extract_key_changes(events)

    return SessionBriefing(
        recent_events=events,
        recent_claims=claims,
        active_agents=active,
        last_mood=last_mood,
        system_delta=delta,
        key_changes=key_changes,
    )


def briefing_to_markdown(briefing: SessionBriefing) -> str:
    """Render a session briefing as human-readable markdown.

    Args:
        briefing: The SessionBriefing to render.

    Returns:
        Markdown string suitable for display at session start.
    """
    lines: list[str] = []
    lines.append("## Session Briefing")
    lines.append("")

    # System delta
    delta_label = {
        "improving": "Improving",
        "declining": "Declining",
        "stable": "Stable",
    }.get(briefing.system_delta, briefing.system_delta.title())
    lines.append(f"**System trajectory:** {delta_label}")

    # Mood
    if briefing.last_mood is not None:
        mood_val = briefing.last_mood.mood.value
        lines.append(f"**Last mood:** {mood_val}")
    lines.append("")

    # Active agents
    if briefing.active_agents:
        lines.append(f"**Active agents:** {', '.join(briefing.active_agents)}")
        lines.append("")

    # Key changes
    if briefing.key_changes:
        lines.append("### Recent Changes")
        lines.append("")
        for change in briefing.key_changes:
            lines.append(f"- {change}")
        lines.append("")

    # Recent events summary
    if briefing.recent_events:
        lines.append(f"### Events ({len(briefing.recent_events)} in window)")
        lines.append("")
        for e in briefing.recent_events[-10:]:
            ts = e.timestamp[:19] if len(e.timestamp) >= 19 else e.timestamp
            lines.append(f"- `{ts}` {e.event_type} ({e.source})")
        if len(briefing.recent_events) > 10:
            lines.append(f"- ... and {len(briefing.recent_events) - 10} more")
        lines.append("")

    # Claims summary
    if briefing.recent_claims:
        lines.append(f"### Agent Activity ({len(briefing.recent_claims)} claims)")
        lines.append("")
        for claim in briefing.recent_claims[-5:]:
            agent = claim.get("agent_id", "?")
            action = claim.get("action", "?")
            organ = claim.get("organ", "")
            repo = claim.get("repo", "")
            target = f"{organ}/{repo}" if organ and repo else organ or repo or "?"
            lines.append(f"- {agent}: {action} on {target}")
        lines.append("")

    return "\n".join(lines)
