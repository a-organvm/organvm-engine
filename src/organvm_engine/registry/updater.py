"""Programmatic registry updates with validation gates."""

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
) -> tuple[bool, str]:
    """Update a single field on a registry entry with validation.

    Args:
        registry: Loaded registry dict (mutated in place).
        repo_name: Repository name.
        field: Field name to update.
        value: New value.

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

    return True, f"{repo_name}.{field}: {old_value} -> {value}"
