"""Evolution policy evaluator — classifies changes and enforces migration rules.

Implements: SPEC-008, EVOL-001 through EVOL-003
Resolves: engine #22

The evolution policy distinguishes three modes of system change:
  - CONSERVATIVE: adds detail without altering existing structure or semantics.
  - CONSTRAINED:  extends scope (new fields, new states) but preserves all
                   existing contracts.
  - BREAKING:     removes or renames fields, changes semantics, requires
                   migration for downstream consumers.

Every change is classified by comparing before/after state snapshots.
The evaluator then checks whether the change mode is permitted given which
specs are affected (e.g., breaking changes to SPEC-004 require explicit
migration records per EVOL-004).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Change mode classification
# ---------------------------------------------------------------------------

class ChangeMode(str, enum.Enum):
    """Evolution change mode per SPEC-008."""

    CONSERVATIVE = "CONSERVATIVE"
    CONSTRAINED = "CONSTRAINED"
    BREAKING = "BREAKING"


# Specs that require a migration record for breaking changes (EVOL-003)
_MIGRATION_REQUIRED_SPECS: frozenset[str] = frozenset({
    "SPEC-000",  # System Manifesto
    "SPEC-001",  # Ontology Charter
    "SPEC-002",  # Primitive Register
    "SPEC-003",  # Invariant Register
    "SPEC-004",  # Logical Specification
    "SPEC-005",  # Architectural Specification
    "SPEC-006",  # Traceability Matrix
    "SPEC-007",  # Verification Plan
    "SPEC-008",  # Evolution & Migration Law
})


# ---------------------------------------------------------------------------
# Change classification
# ---------------------------------------------------------------------------

def classify_change(
    before_state: dict[str, Any],
    after_state: dict[str, Any],
) -> ChangeMode:
    """Classify a change by comparing before and after state snapshots.

    Classification rules (EVOL-001):
      - CONSERVATIVE: after_state adds new keys but does not modify or remove
        any existing key's value.
      - CONSTRAINED:  after_state modifies values of existing keys but does
        not remove any key.
      - BREAKING:     after_state removes keys present in before_state, or
        changes the type of an existing value.

    Args:
        before_state: The state before the change.
        after_state:  The state after the change.

    Returns:
        The classified ChangeMode.
    """
    if not before_state:
        # Creating from nothing is always conservative
        return ChangeMode.CONSERVATIVE

    before_keys = set(before_state.keys())
    after_keys = set(after_state.keys())

    # Removed keys → BREAKING
    removed = before_keys - after_keys
    if removed:
        return ChangeMode.BREAKING

    # Check for type changes on existing keys → BREAKING
    for key in before_keys & after_keys:
        before_val = before_state[key]
        after_val = after_state[key]
        if type(before_val) is not type(after_val):
            return ChangeMode.BREAKING

    # Check for value changes on existing keys → CONSTRAINED
    for key in before_keys & after_keys:
        if before_state[key] != after_state[key]:
            return ChangeMode.CONSTRAINED

    # Only additions, no modifications → CONSERVATIVE
    if after_keys - before_keys:
        return ChangeMode.CONSERVATIVE

    # Identical states
    return ChangeMode.CONSERVATIVE


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------

def evaluate_evolution_policy(
    change_mode: ChangeMode,
    affected_specs: list[str],
) -> tuple[bool, list[str]]:
    """Check if a change mode is permitted given the affected specifications.

    Rules (EVOL-002):
      - CONSERVATIVE changes are always permitted.
      - CONSTRAINED changes are permitted but produce advisory warnings when
        they touch core specs (SPEC-000 through SPEC-008).
      - BREAKING changes to core specs are blocked unless a migration record
        is provided (callers must create one via create_migration_record and
        re-evaluate with CONSTRAINED after applying it).

    Args:
        change_mode:    The classified change mode.
        affected_specs: List of spec identifiers affected by this change.

    Returns:
        (permitted, messages) tuple.
    """
    messages: list[str] = []

    if change_mode == ChangeMode.CONSERVATIVE:
        messages.append("Conservative change: permitted without conditions.")
        return True, messages

    # Identify core specs affected
    core_affected = [s for s in affected_specs if s in _MIGRATION_REQUIRED_SPECS]

    if change_mode == ChangeMode.CONSTRAINED:
        if core_affected:
            for spec in core_affected:
                messages.append(
                    f"Advisory: constrained change affects core spec {spec}. "
                    f"Ensure backward compatibility.",
                )
        else:
            messages.append("Constrained change: permitted (no core specs affected).")
        return True, messages

    # BREAKING
    if core_affected:
        for spec in core_affected:
            messages.append(
                f"Blocked: breaking change to {spec} requires a migration record "
                f"(EVOL-004). Create one via create_migration_record() before proceeding.",
            )
        return False, messages

    # Breaking change to non-core specs is permitted with warning
    messages.append(
        "Breaking change permitted (non-core specs only). "
        "Consider creating a migration record for traceability.",
    )
    return True, messages


# ---------------------------------------------------------------------------
# Migration records
# ---------------------------------------------------------------------------

def create_migration_record(
    change_mode: ChangeMode | str,
    description: str,
    affected_entities: list[str],
    *,
    actor: str = "cli",
) -> dict[str, Any]:
    """Create an EVOL-004 compatible migration record.

    The record captures what changed, why, and who is affected, enabling
    downstream systems to apply compensating actions.

    Args:
        change_mode:       The change classification.
        description:       Human-readable description of the change.
        affected_entities: List of entity UIDs or repo names affected.
        actor:             Who or what created this record.

    Returns:
        A migration record dict suitable for persistence or event emission.
    """
    mode_str = change_mode.value if isinstance(change_mode, ChangeMode) else str(change_mode)

    return {
        "migration_id": str(uuid.uuid4()),
        "change_mode": mode_str,
        "description": description,
        "affected_entities": list(affected_entities),
        "actor": actor,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "spec_reference": "EVOL-004",
    }


def validate_migration_record(record: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate the structure of a migration record.

    Args:
        record: The migration record dict.

    Returns:
        (valid, errors) tuple.
    """
    errors: list[str] = []
    required_fields = [
        "migration_id",
        "change_mode",
        "description",
        "affected_entities",
        "created_at",
        "status",
    ]
    for f in required_fields:
        if f not in record:
            errors.append(f"missing required field: {f}")

    if "change_mode" in record:
        valid_modes = {m.value for m in ChangeMode}
        if record["change_mode"] not in valid_modes:
            errors.append(
                f"invalid change_mode: {record['change_mode']}. "
                f"Must be one of: {sorted(valid_modes)}",
            )

    if "affected_entities" in record:
        if not isinstance(record["affected_entities"], list):
            errors.append("affected_entities must be a list")
        elif not record["affected_entities"]:
            errors.append("affected_entities must not be empty")

    if "status" in record:
        valid_statuses = {"pending", "applied", "rolled_back"}
        if record["status"] not in valid_statuses:
            errors.append(
                f"invalid status: {record['status']}. "
                f"Must be one of: {sorted(valid_statuses)}",
            )

    return (len(errors) == 0, errors)
