"""Subscription wiring — resolve seed.yaml subscriptions into a dispatch graph.

Each seed.yaml can declare subscriptions like:

    subscriptions:
      - event: product.release
        source: organvm-iii-ergon/*
        action: notify

This module walks all seeds, collects those declarations, and builds a
NerveBundle that the event bus can use to propagate events to listeners.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.pulse.events import Event
from organvm_engine.seed.discover import discover_seeds
from organvm_engine.seed.reader import get_subscriptions, read_seed, seed_identity

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Subscription:
    """A single event subscription declared in a seed.yaml."""

    subscriber: str       # org/repo identity of the subscribing repo
    event_type: str       # event type pattern (e.g. "product.release")
    source: str           # source filter (e.g. "organvm-iii-ergon/*", or "" for any)
    action: str           # action tag (e.g. "notify", "rebuild", "sync")

    def to_dict(self) -> dict:
        return {
            "subscriber": self.subscriber,
            "event_type": self.event_type,
            "source": self.source,
            "action": self.action,
        }


@dataclass
class NerveBundle:
    """Collected subscriptions indexed for fast lookup."""

    subscriptions: list[Subscription] = field(default_factory=list)
    by_event: dict[str, list[Subscription]] = field(default_factory=lambda: defaultdict(list))
    by_subscriber: dict[str, list[Subscription]] = field(
        default_factory=lambda: defaultdict(list),
    )

    def add(self, sub: Subscription) -> None:
        """Register a subscription and update indices."""
        self.subscriptions.append(sub)
        self.by_event[sub.event_type].append(sub)
        self.by_subscriber[sub.subscriber].append(sub)

    def listeners_for(self, event_type: str) -> list[Subscription]:
        """All subscriptions listening for a given event type."""
        return list(self.by_event.get(event_type, []))

    def subscriptions_for(self, subscriber: str) -> list[Subscription]:
        """All subscriptions belonging to a given subscriber."""
        return list(self.by_subscriber.get(subscriber, []))

    def to_dict(self) -> dict:
        return {
            "total": len(self.subscriptions),
            "by_event": {
                k: [s.to_dict() for s in v]
                for k, v in sorted(self.by_event.items())
            },
            "by_subscriber": {
                k: [s.to_dict() for s in v]
                for k, v in sorted(self.by_subscriber.items())
            },
        }


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_subscriptions(workspace: Path | str | None = None) -> NerveBundle:
    """Walk all seeds and collect subscription declarations into a NerveBundle.

    Args:
        workspace: Workspace root directory. None = default from paths module.

    Returns:
        NerveBundle with all discovered subscriptions indexed.
    """
    bundle = NerveBundle()
    seed_paths = discover_seeds(workspace)

    for path in seed_paths:
        try:
            seed = read_seed(path)
        except Exception:
            continue

        identity = seed_identity(seed)
        for sub_entry in get_subscriptions(seed):
            if isinstance(sub_entry, str):
                # Bare string subscription — treat as event type with no filter
                bundle.add(Subscription(
                    subscriber=identity,
                    event_type=sub_entry,
                    source="",
                    action="default",
                ))
            elif isinstance(sub_entry, dict):
                bundle.add(Subscription(
                    subscriber=identity,
                    event_type=sub_entry.get("event", sub_entry.get("event_type", "")),
                    source=sub_entry.get("source", ""),
                    action=sub_entry.get("action", "default"),
                ))

    return bundle


# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------

def _source_matches(pattern: str, source: str) -> bool:
    """Check if an event source matches a subscription source pattern.

    Patterns can be:
        ""                  — matches everything
        "exact/match"       — exact string match
        "organvm-iii-ergon/*" — prefix wildcard (org-level)
    """
    if not pattern:
        return True
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        return source == prefix or source.startswith(prefix + "/")
    return pattern == source


def propagate(event: Event, bundle: NerveBundle) -> list[dict]:
    """Find all subscriptions that match an event and produce dispatch records.

    Args:
        event: The emitted event to propagate.
        bundle: NerveBundle with all known subscriptions.

    Returns:
        List of dispatch record dicts, one per matching subscription.
    """
    records: list[dict] = []
    for sub in bundle.listeners_for(event.event_type):
        if _source_matches(sub.source, event.source):
            records.append({
                "subscriber": sub.subscriber,
                "event_type": event.event_type,
                "source": event.source,
                "action": sub.action,
                "timestamp": event.timestamp,
                "payload": event.payload,
            })
    return records
