"""Promotion state machine: LOCAL -> CANDIDATE -> PUBLIC_PROCESS -> GRADUATED -> ARCHIVED."""

# Canonical transitions from governance-rules.json
TRANSITIONS = {
    "INCUBATOR": ["LOCAL", "ARCHIVED"],
    "LOCAL": ["CANDIDATE", "ARCHIVED"],
    "CANDIDATE": ["PUBLIC_PROCESS", "LOCAL", "ARCHIVED"],
    "PUBLIC_PROCESS": ["GRADUATED", "CANDIDATE", "ARCHIVED"],
    "GRADUATED": ["ARCHIVED"],
    "ARCHIVED": [],
}


def get_valid_transitions(current_state: str) -> list[str]:
    """Get valid target states for a given current state.

    Args:
        current_state: Current promotion_status.

    Returns:
        List of valid target states.
    """
    return TRANSITIONS.get(current_state, [])


def check_transition(current_state: str, target_state: str) -> tuple[bool, str]:
    """Check if a state transition is valid.

    Args:
        current_state: Current promotion_status.
        target_state: Desired promotion_status.

    Returns:
        (valid, message) tuple.
    """
    valid = TRANSITIONS.get(current_state)
    if valid is None:
        return False, f"Unknown state '{current_state}'"

    if target_state in valid:
        return True, f"{current_state} -> {target_state}"

    return False, (
        f"Cannot transition {current_state} -> {target_state}. "
        f"Valid targets: {', '.join(valid) if valid else 'none (terminal state)'}"
    )


def emit_promotion_event(
    repo_name: str,
    previous_state: str,
    new_state: str,
) -> None:
    """Emit a promotion change event to the unified bus."""
    try:
        from organvm_engine.pulse.emitter import emit_engine_event
        from organvm_engine.pulse.types import PROMOTION_CHANGED

        emit_engine_event(
            event_type=PROMOTION_CHANGED,
            source="governance",
            subject_entity=repo_name,
            payload={
                "previous_state": previous_state,
                "new_state": new_state,
            },
        )
    except Exception:
        pass
