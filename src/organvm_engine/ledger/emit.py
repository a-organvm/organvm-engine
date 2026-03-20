"""Fail-safe testament chain emission helper.

Provides a single entry point for all engine modules to emit events
to the Testament Chain. Never raises — if the chain is unavailable,
the calling operation continues unaffected.

Usage:
    from organvm_engine.ledger.emit import testament_emit

    testament_emit(
        event_type="registry.update",
        entity_uid="ent_repo_...",
        source_organ="META-ORGANVM",
        source_repo="organvm-engine",
        actor="cli",
        payload={"field": "status", "old": "CANDIDATE", "new": "GRADUATED"},
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CHAIN_PATH = Path.home() / ".organvm" / "testament" / "chain.jsonl"


def testament_emit(
    event_type: str,
    entity_uid: str = "",
    source_organ: str = "",
    source_repo: str = "",
    actor: str = "",
    payload: dict[str, Any] | None = None,
    causal_predecessor: str = "",
) -> str | None:
    """Emit an event to the Testament Chain. Fail-safe: never raises.

    Returns:
        The event_id if successful, None if emission failed.
    """
    try:
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(_CHAIN_PATH)
        record = spine.emit(
            event_type=event_type,
            entity_uid=entity_uid,
            source_organ=source_organ,
            source_repo=source_repo,
            actor=actor,
            payload=payload or {},
            causal_predecessor=causal_predecessor,
        )
        return record.event_id
    except Exception:
        logger.debug("Testament chain emission failed (non-fatal)", exc_info=True)
        return None
