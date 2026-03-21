"""Unified event emitter — bridge from engine modules to ontologia's event bus.

All engine modules call emit_engine_event() to record significant actions.
Events flow to both:
  1. The engine's own JSONL log (~/.organvm/events/events.jsonl)
  2. Ontologia's event bus (~/.organvm/ontologia/events.jsonl) + in-memory pub/sub

If ontologia is unavailable (not installed, store missing), emission degrades
gracefully — the engine continues without error.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_entity_uid(entity_name: str) -> str | None:
    """Attempt to resolve a repo/organ name to an ontologia UID.

    Returns None if ontologia is unavailable or the entity is unknown.
    """
    try:
        from ontologia.entity.resolver import (
            resolve as ontologia_resolve,  # pyright: ignore[reportAttributeAccessIssue]
        )
        from ontologia.registry.store import (
            OntologiaStore,  # pyright: ignore[reportAttributeAccessIssue]
        )

        store = OntologiaStore()
        if not store.store_dir.exists():
            return None
        store.load()
        result = ontologia_resolve(entity_name, store)
        if result:
            return result.uid
    except Exception:
        pass
    return None


def emit_engine_event(
    event_type: str,
    source: str,
    subject_entity: str | None = None,
    payload: dict[str, Any] | None = None,
    resolve_entity: bool = True,
) -> None:
    """Emit an event from an engine module to the unified bus.

    This is the single entry point for all engine event emission.
    Non-blocking and fail-safe — never raises.

    Args:
        event_type: Event type constant from pulse.types.
        source: Engine module identifier (e.g., "governance", "metrics").
        subject_entity: Entity name or UID this event concerns.
            If a name is given and resolve_entity is True, it will
            attempt to resolve to an ontologia UID.
        payload: Additional event data.
        resolve_entity: Whether to resolve entity names to UIDs.
    """
    try:
        resolved_uid = subject_entity
        if subject_entity and resolve_entity and not subject_entity.startswith("ent_"):
            uid = _resolve_entity_uid(subject_entity)
            if uid:
                resolved_uid = uid

        # Emit to engine's own event log
        from organvm_engine.pulse.events import emit as engine_emit

        engine_emit(
            event_type=event_type,
            source=source,
            payload={
                **(payload or {}),
                **({"subject_entity": resolved_uid} if resolved_uid else {}),
            },
        )

        # Also emit directly to ontologia's enhanced bus (with entity tracking)
        try:
            from ontologia.events.bus import emit as ontologia_emit

            ontologia_emit(
                event_type=event_type,
                source=f"engine:{source}",
                subject_entity=resolved_uid,
                payload=payload or {},
            )
        except ImportError:
            pass
    except Exception:
        # Never let event emission break the calling module
        logger.debug("Event emission failed for %s (non-fatal)", event_type, exc_info=True)
