"""The Bridge — connects fossil events to the testament chain.

Produces event dicts compatible with any chain implementation.
Does NOT import from organvm_engine.ledger or organvm_engine.testament.
The caller decides where to route these events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.fossil.archivist import Intention
from organvm_engine.fossil.drift import DriftRecord
from organvm_engine.fossil.narrator import EpochStats


def emit_epoch_event(
    epoch_id: str,
    stats: EpochStats,
    chronicle_path: Path | None,
) -> dict:
    """Create an event dict for an epoch closure.

    Args:
        epoch_id: The epoch identifier (e.g. "EPOCH-007").
        stats: Computed statistics for the epoch.
        chronicle_path: Path to the generated chronicle markdown, or None.

    Returns:
        Event dict with event_type, timestamp, source, and payload.
    """
    return {
        "event_type": "EPOCH_CLOSED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": fossil_uri("epoch", epoch_id),
        "payload": {
            "epoch_id": epoch_id,
            "epoch_name": stats.epoch_name,
            "date_range": f"{stats.start.isoformat()} — {stats.end.isoformat()}",
            "commit_count": stats.commit_count,
            "dominant_archetype": stats.dominant_archetype.value,
            "secondary_archetype": (
                stats.secondary_archetype.value if stats.secondary_archetype else None
            ),
            "organs_touched": stats.organs_touched,
            "repos_touched": len(stats.repos_touched),
            "trickster_ratio": round(stats.trickster_ratio, 3),
            "chronicle_path": str(chronicle_path) if chronicle_path else None,
        },
    }


def emit_intention_event(intention: Intention) -> dict:
    """Create an event dict for a newly captured intention.

    Args:
        intention: The captured Intention object.

    Returns:
        Event dict with event_type, timestamp, source, and payload.
    """
    return {
        "event_type": "INTENTION_BORN",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": fossil_uri("intention", intention.id),
        "payload": {
            "intention_id": intention.id,
            "uniqueness_score": intention.uniqueness_score,
            "archetype": intention.archetypes[0].value if intention.archetypes else "unknown",
            "preview": intention.raw_text[:120],
            "epoch": intention.epoch,
            "session_id": intention.session_id,
        },
    }


def emit_drift_event(drift: DriftRecord, intention: Intention) -> dict:
    """Create an event dict for a detected drift between intention and reality.

    Args:
        drift: The computed DriftRecord.
        intention: The original Intention that was analyzed.

    Returns:
        Event dict with event_type, timestamp, source, and payload.
    """
    return {
        "event_type": "DRIFT_DETECTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": fossil_uri("intention", drift.intention_id),
        "payload": {
            "intention_id": drift.intention_id,
            "convergence": drift.convergence,
            "drift_archetype": drift.drift_archetype.value,
            "mutation_count": len(drift.mutations),
            "shadow_count": len(drift.shadows),
            "mutations": drift.mutations,
            "shadows": drift.shadows,
            "intended_scope": drift.intended_scope,
            "actual_scope": drift.actual_scope,
        },
    }


def fossil_uri(entity_type: str, entity_id: str) -> str:
    """Construct a fossil URI for an entity.

    Args:
        entity_type: The type of entity (epoch, intention, drift, record).
        entity_id: The entity identifier.

    Returns:
        URI in the form ``fossil://{entity_type}/{entity_id}``.
    """
    return f"fossil://{entity_type}/{entity_id}"
