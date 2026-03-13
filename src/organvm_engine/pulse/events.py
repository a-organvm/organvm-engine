"""File-based event bus — append-only JSONL event log.

Every system-significant action (registry update, promotion, gate change,
mood shift) emits an event to ~/.organvm/events/events.jsonl.  Consumers
replay the log to reconstruct state or build temporal profiles.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

REGISTRY_UPDATED = "registry.updated"
ORGANISM_COMPUTED = "organism.computed"
GATE_CHANGED = "gate.changed"
REPO_PROMOTED = "repo.promoted"
SESSION_STARTED = "session.started"
SESSION_ENDED = "session.ended"
PULSE_HEARTBEAT = "pulse.heartbeat"
SEED_CHANGED = "seed.changed"
DENSITY_COMPUTED = "density.computed"
MOOD_SHIFTED = "mood.shifted"

ALL_EVENT_TYPES: list[str] = [
    REGISTRY_UPDATED,
    ORGANISM_COMPUTED,
    GATE_CHANGED,
    REPO_PROMOTED,
    SESSION_STARTED,
    SESSION_ENDED,
    PULSE_HEARTBEAT,
    SEED_CHANGED,
    DENSITY_COMPUTED,
    MOOD_SHIFTED,
]


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """A single system event."""

    event_type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _events_dir() -> Path:
    return Path.home() / ".organvm" / "events"


def _events_path() -> Path:
    return _events_dir() / "events.jsonl"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def emit(event_type: str, source: str, payload: dict[str, Any] | None = None) -> Event:
    """Append an event to the JSONL log and return it.

    Creates the events directory if it does not exist.
    Also forwards to the ontologia event bus if available, so that
    ontologia subscribers see pulse events.
    """
    event = Event(
        event_type=event_type,
        source=source,
        payload=payload or {},
    )
    path = _events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(event.to_json() + "\n")

    # Forward to ontologia bus (best-effort)
    try:
        from ontologia.events import bus as ontologia_bus
        ontologia_bus.emit(
            event_type=event_type,
            source=f"pulse:{source}",
            payload=payload or {},
        )
    except ImportError:
        pass

    return event


def replay(
    since: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
) -> list[Event]:
    """Read events from the log, optionally filtering by time and type.

    Args:
        since: ISO timestamp — only return events after this time.
        event_type: Only return events of this type.
        limit: Maximum number of events to return (from the tail).

    Returns:
        List of matching events, most recent last.
    """
    path = _events_path()
    if not path.is_file():
        return []

    events: list[Event] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event_type and data.get("event_type") != event_type:
            continue
        if since and data.get("timestamp", "") <= since:
            continue

        events.append(Event(
            event_type=data.get("event_type", ""),
            source=data.get("source", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
        ))

    # Return the last `limit` events
    return events[-limit:]


def recent(n: int = 20) -> list[Event]:
    """Return the last *n* events from the log."""
    return replay(limit=n)


def event_counts(since: str | None = None) -> dict[str, int]:
    """Count events by type, optionally since a given timestamp.

    Returns:
        Dict mapping event_type to occurrence count.
    """
    path = _events_path()
    if not path.is_file():
        return {}

    counts: dict[str, int] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and data.get("timestamp", "") <= since:
            continue
        etype = data.get("event_type", "")
        counts[etype] = counts.get(etype, 0) + 1

    return counts
