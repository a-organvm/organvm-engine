"""Agent authority matrix.

Implements: SPEC-017, AUTH-001 through AUTH-004

Defines the four authority levels (READ, PROPOSE, MUTATE, APPROVE) and
provides functions to check required authority for operations.  Immutable
specs (SPEC-000 through SPEC-002) cannot be amended without an explicit
era-transition override.

The authority model enforces the constitutional principle that AI agents
generate volume while humans retain governance control over state
transitions, spec amendments, and topological mutations.
"""

from __future__ import annotations

from enum import IntEnum


class AuthorityLevel(IntEnum):
    """Authority tiers — higher values grant more destructive power."""

    READ = 1
    PROPOSE = 2
    MUTATE = 3
    APPROVE = 4


# Specs whose amendment requires APPROVE authority *and* era-transition context.
IMMUTABLE_SPECS = {"SPEC-000", "SPEC-001", "SPEC-002"}

# Operations classified by required authority level.
_APPROVE_OPS = frozenset({
    "amend_spec",
    "era_transition",
    "topological_mutation",
    "dissolve_organ",
    "create_organ",
})

_MUTATE_OPS = frozenset({
    "promote",
    "demote",
    "archive",
    "update_registry",
    "modify_governance",
    "merge_repo",
    "split_repo",
})


def check_authority(agent_type: str, operation: str) -> AuthorityLevel:
    """Return minimum authority level required for an operation.

    Args:
        agent_type: The kind of agent requesting the operation
            (e.g. "claude", "gemini", "codex", "human").
        operation: The operation name to check (e.g. "promote",
            "amend_spec", "read_registry").

    Returns:
        The minimum ``AuthorityLevel`` needed to perform *operation*.
    """
    if operation in _APPROVE_OPS:
        return AuthorityLevel.APPROVE
    if operation in _MUTATE_OPS:
        return AuthorityLevel.MUTATE
    if operation.startswith("propose_"):
        return AuthorityLevel.PROPOSE
    return AuthorityLevel.READ


def can_amend_spec(spec_id: str, has_era_context: bool = False) -> bool:
    """Check whether a spec can be amended under current conditions.

    Immutable specs (SPEC-000, SPEC-001, SPEC-002) require an active
    era-transition context.  All other specs can be amended at APPROVE
    authority level.

    Args:
        spec_id: The identifier of the spec (e.g. "SPEC-003").
        has_era_context: Whether an era-transition is currently active.

    Returns:
        ``True`` if amendment is permitted, ``False`` otherwise.
    """
    if spec_id in IMMUTABLE_SPECS:
        return has_era_context
    return True


def agent_ceiling(agent_type: str) -> AuthorityLevel:
    """Return the maximum authority level an agent type can hold.

    Human operators can reach APPROVE.  AI agents are capped at MUTATE
    by default — APPROVE operations require human confirmation.

    Args:
        agent_type: Agent identifier (e.g. "human", "claude").

    Returns:
        The ceiling ``AuthorityLevel`` for the given agent type.
    """
    if agent_type == "human":
        return AuthorityLevel.APPROVE
    return AuthorityLevel.MUTATE


def is_authorized(agent_type: str, operation: str) -> bool:
    """Check whether *agent_type* may perform *operation*.

    Combines :func:`check_authority` (required level) with
    :func:`agent_ceiling` (agent's maximum level).

    Args:
        agent_type: Agent identifier.
        operation: Operation name.

    Returns:
        ``True`` if the agent's ceiling meets or exceeds the required level.
    """
    required = check_authority(agent_type, operation)
    ceiling = agent_ceiling(agent_type)
    return ceiling >= required
