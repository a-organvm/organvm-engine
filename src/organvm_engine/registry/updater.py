"""Programmatic registry updates with validation gates."""

from __future__ import annotations

from datetime import datetime, timezone

from organvm_engine.registry.query import find_repo
from organvm_engine.registry.validator import (
    VALID_PROMOTION_STATES,
    VALID_REVENUE_MODELS,
    VALID_REVENUE_STATUSES,
    VALID_STATUSES,
    VALID_TIERS,
)

# Fields with enum constraints
ENUM_FIELDS = {
    "implementation_status": VALID_STATUSES,
    "revenue_model": VALID_REVENUE_MODELS,
    "revenue_status": VALID_REVENUE_STATUSES,
    "promotion_status": VALID_PROMOTION_STATES,
    "tier": VALID_TIERS,
}


def update_repo(
    registry: dict,
    repo_name: str,
    field: str,
    value: str | bool | int,
    *,
    reason: str = "",
) -> tuple[bool, str]:
    """Update a single field on a registry entry with validation.

    When *field* is ``promotion_status``, a record is appended to the
    entry's ``promotion_history`` array (created if absent).  This feeds
    the van der Aalst conformance checker in ``governance.conformance``.

    Args:
        registry: Loaded registry dict (mutated in place).
        repo_name: Repository name.
        field: Field name to update.
        value: New value.
        reason: Optional human-readable reason for the change
            (recorded in promotion_history when field is promotion_status).

    Returns:
        (success, message) tuple.
    """
    result = find_repo(registry, repo_name)
    if not result:
        return False, f"Repo '{repo_name}' not found in registry"

    organ_key, repo = result

    # Validate enum fields
    if field in ENUM_FIELDS:
        valid = ENUM_FIELDS[field]
        if value not in valid:
            return False, f"Invalid {field} '{value}' (valid: {', '.join(sorted(valid))})"

    old_value = repo.get(field, "<unset>")
    repo[field] = value

    # Record promotion_history on promotion_status changes (F-002)
    if field == "promotion_status" and old_value != value:
        _record_promotion_history(repo, str(old_value), str(value), reason=reason)

    # Emit registry update event
    try:
        from organvm_engine.pulse.emitter import emit_engine_event
        from organvm_engine.pulse.types import REGISTRY_UPDATED

        emit_engine_event(
            event_type=REGISTRY_UPDATED,
            source="registry",
            subject_entity=repo_name,
            payload={
                "field": field,
                "old_value": str(old_value),
                "new_value": str(value),
            },
        )
    except Exception:
        pass

    # Emit to Testament Chain
    from organvm_engine.ledger.emit import testament_emit
    testament_emit(
        event_type="registry.update",
        entity_uid=f"ent_repo_{repo_name}",
        source_organ=organ_key,
        source_repo=repo_name,
        actor="cli",
        payload={"field": field, "old": str(old_value), "new": str(value)},
    )

    return True, f"{repo_name}.{field}: {old_value} -> {value}"


# ---------------------------------------------------------------------------
# Promotion history recording (F-002)
# ---------------------------------------------------------------------------

def _record_promotion_history(
    repo: dict,
    from_state: str,
    to_state: str,
    *,
    reason: str = "",
    _now: datetime | None = None,
) -> None:
    """Append a transition record to a repo's ``promotion_history``.

    The record shape matches what ``governance.conformance.extract_promotion_trace``
    reads: ``from_state``, ``to_state``, ``timestamp``, and optionally ``reason``.

    Args:
        repo: Registry entry dict (mutated in place).
        from_state: Previous promotion_status value.
        to_state: New promotion_status value.
        reason: Optional human-readable reason for the transition.
        _now: Injection point for deterministic timestamps in tests.
    """
    if not isinstance(repo.get("promotion_history"), list):
        repo["promotion_history"] = []

    now = _now or datetime.now(timezone.utc)
    record: dict[str, str] = {
        "from_state": from_state,
        "to_state": to_state,
        "timestamp": now.isoformat(),
    }
    if reason:
        record["reason"] = reason

    repo["promotion_history"].append(record)
