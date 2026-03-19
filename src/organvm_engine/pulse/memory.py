"""Entity memory aggregation — cross-store signal collector.

Aggregates all signals about a named entity from every data source
in the system.  Fulfills the prime directive's "inherit its memory"
capability by giving any entity access to its complete history.

Sources:
  1. Pulse events (events.jsonl) — filtered by repo/source match
  2. Shared memory (shared-memory.jsonl) — insights tagged to the entity
  3. Ontologia events — entity-scoped event history
  4. Continuity briefing — recent system context
  5. Metrics timeseries — soak test trend data
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EntityMemory:
    """Aggregated memory for a single entity across all data stores."""

    entity: str  # name or UID that was queried
    entity_uid: str = ""
    entity_type: str = ""

    # From pulse events
    pulse_events: list[dict[str, Any]] = field(default_factory=list)
    pulse_event_count: int = 0

    # From shared memory
    insights: list[dict[str, Any]] = field(default_factory=list)
    insight_count: int = 0

    # From ontologia
    ontologia_events: list[dict[str, Any]] = field(default_factory=list)
    ontologia_event_count: int = 0
    name_history: list[dict[str, Any]] = field(default_factory=list)
    lifecycle_status: str = ""

    # From continuity
    recent_claims: list[dict[str, Any]] = field(default_factory=list)
    active_tensions: list[dict[str, Any]] = field(default_factory=list)

    # From metrics
    metrics_trend: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_signals(self) -> int:
        return (
            self.pulse_event_count
            + self.insight_count
            + self.ontologia_event_count
            + len(self.name_history)
            + len(self.recent_claims)
            + len(self.metrics_trend)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "entity_uid": self.entity_uid,
            "entity_type": self.entity_type,
            "total_signals": self.total_signals,
            "pulse": {
                "events": self.pulse_events,
                "count": self.pulse_event_count,
            },
            "shared_memory": {
                "insights": self.insights,
                "count": self.insight_count,
            },
            "ontologia": {
                "events": self.ontologia_events,
                "event_count": self.ontologia_event_count,
                "name_history": self.name_history,
                "lifecycle_status": self.lifecycle_status,
            },
            "continuity": {
                "recent_claims": self.recent_claims,
                "active_tensions": self.active_tensions,
            },
            "metrics": {
                "trend": self.metrics_trend,
            },
        }


def _gather_pulse_events(entity_name: str, mem: EntityMemory, limit: int) -> None:
    """Collect pulse events mentioning this entity."""
    try:
        from organvm_engine.pulse.events import replay

        all_events = replay(limit=limit * 5)  # over-fetch to filter

        matching = []
        for event in all_events:
            source = event.source or ""
            payload = event.payload or {}
            repo = payload.get("repo", "")

            # Match on source, repo in payload, or entity name in payload values
            if (
                entity_name in source
                or repo == entity_name
                or entity_name in str(payload.get("name", ""))
            ):
                matching.append({
                    "event_type": event.event_type,
                    "source": event.source,
                    "timestamp": event.timestamp,
                    "payload": event.payload,
                })

        mem.pulse_events = matching[-limit:]
        mem.pulse_event_count = len(matching)
    except Exception:
        logger.debug("Pulse events unavailable for memory query", exc_info=True)


def _gather_insights(entity_name: str, mem: EntityMemory, limit: int) -> None:
    """Collect shared memory insights tagged to this entity."""
    try:
        from organvm_engine.pulse.shared_memory import _load_all

        all_insights = _load_all()

        matching = []
        for ins in all_insights:
            if (
                ins.repo == entity_name
                or entity_name in ins.tags
                or entity_name in ins.organ
                or entity_name in ins.content
            ):
                matching.append(ins.to_dict())

        mem.insights = matching[-limit:]
        mem.insight_count = len(matching)
    except Exception:
        logger.debug("Shared memory unavailable for memory query", exc_info=True)


def _gather_ontologia(entity_name: str, mem: EntityMemory, limit: int) -> None:
    """Collect ontologia event history and name records."""
    try:
        from ontologia.registry.store import open_store

        store = open_store()
        if store.entity_count == 0:
            return

        resolver = store.resolver()
        result = resolver.resolve(entity_name)
        if not result:
            return

        uid = result.identity.uid
        mem.entity_uid = uid
        mem.entity_type = result.identity.entity_type.value
        mem.lifecycle_status = result.identity.lifecycle_status.value

        # Name history
        names = store.name_history(uid)
        mem.name_history = [
            {
                "display_name": nr.display_name,
                "is_primary": nr.is_primary,
                "valid_from": nr.valid_from,
                "source": nr.source,
            }
            for nr in names
        ]

        # Ontologia events for this entity
        events = store.events(subject_entity=uid, limit=limit)
        mem.ontologia_events = [
            {
                "event_type": ev.event_type,
                "source": ev.source,
                "timestamp": ev.timestamp,
                "payload": ev.payload if hasattr(ev, "payload") else {},
            }
            for ev in events
        ]
        mem.ontologia_event_count = len(mem.ontologia_events)

    except ImportError:
        logger.debug("ontologia not available for memory query", exc_info=True)
    except Exception:
        logger.debug("Ontologia memory query failed (non-fatal)", exc_info=True)


def _gather_continuity(entity_name: str, mem: EntityMemory) -> None:
    """Collect continuity signals related to this entity."""
    try:
        from organvm_engine.pulse.continuity import build_briefing

        briefing = build_briefing()

        # Filter claims mentioning this entity
        for claim in briefing.recent_claims:
            repo = claim.get("repo", "")
            organ = claim.get("organ", "")
            if entity_name in (repo, organ) or entity_name in str(claim):
                mem.recent_claims.append(claim)

        # Filter tensions mentioning this entity
        for tension in briefing.active_tensions:
            entity_ids = tension.get("entity_ids", [])
            desc = tension.get("description", "")
            if entity_name in str(entity_ids) or entity_name in desc:
                mem.active_tensions.append(tension)

    except Exception:
        logger.debug("Continuity unavailable for memory query", exc_info=True)


def _gather_metrics(entity_name: str, mem: EntityMemory) -> None:
    """Collect metrics timeseries data for this entity."""
    try:
        from organvm_engine.metrics.timeseries import ci_trend, load_snapshots

        snapshots = load_snapshots()
        if not snapshots:
            return

        # CI trend is system-level, but we include it for context
        trend = ci_trend(snapshots)
        if trend:
            mem.metrics_trend = trend[-14:]  # last 14 days

    except Exception:
        logger.debug("Metrics unavailable for memory query", exc_info=True)


def aggregate_entity_memory(
    entity_name: str,
    include_pulse: bool = True,
    include_insights: bool = True,
    include_ontologia: bool = True,
    include_continuity: bool = True,
    include_metrics: bool = True,
    limit: int = 50,
) -> EntityMemory:
    """Aggregate all signals about a named entity from every data source.

    Fulfills the prime directive's "inherit its memory" capability
    by giving any entity access to its complete history across
    pulse events, shared memory, ontologia, continuity, and metrics.

    Args:
        entity_name: Repo name, component path, or entity UID.
        include_pulse: Include pulse event history.
        include_insights: Include shared memory insights.
        include_ontologia: Include ontologia event + name history.
        include_continuity: Include continuity briefing signals.
        include_metrics: Include metrics timeseries.
        limit: Max events/insights per source.

    Returns:
        EntityMemory with all discovered signals.
    """
    mem = EntityMemory(entity=entity_name)

    if include_pulse:
        _gather_pulse_events(entity_name, mem, limit)

    if include_insights:
        _gather_insights(entity_name, mem, limit)

    if include_ontologia:
        _gather_ontologia(entity_name, mem, limit)

    if include_continuity:
        _gather_continuity(entity_name, mem)

    if include_metrics:
        _gather_metrics(entity_name, mem)

    return mem
