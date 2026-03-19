"""Conformance checking — observed promotion traces vs. state machine spec.

Implements: SPEC-004, van der Aalst conformance checking
Resolves: engine #31

Extracts the observed promotion history from a registry, then checks
whether that trace conforms to the valid transition table from the
state machine specification.  Reports fitness score, skipped states,
and unauthorized transitions.

The approach follows van der Aalst's token-replay conformance checking:
fitness = 1 - (violations / total_transitions).  A perfect score of 1.0
means every observed transition is sanctioned by the spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from organvm_engine.governance.state_machine import FALLBACK_TRANSITIONS

# ---------------------------------------------------------------------------
# Trace record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TraceEntry:
    """A single observed promotion transition.

    Fields:
        entity_uid: The repo or entity identifier.
        from_state: State before the transition.
        to_state:   State after the transition.
        timestamp:  ISO timestamp of the transition (empty if unknown).
    """

    entity_uid: str
    from_state: str
    to_state: str
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Conformance result
# ---------------------------------------------------------------------------

@dataclass
class ConformanceResult:
    """Result of a conformance check.

    Fields:
        fitness:                 Float 0.0..1.0 (1.0 = perfect conformance).
        violations:              List of human-readable violation descriptions.
        skipped_states:          Transitions where intermediate states were bypassed.
        unauthorized_transitions: Transitions not present in the valid spec.
        total_transitions:       Total number of transitions checked.
    """

    fitness: float = 1.0
    violations: list[str] = field(default_factory=list)
    skipped_states: list[dict[str, Any]] = field(default_factory=list)
    unauthorized_transitions: list[dict[str, Any]] = field(default_factory=list)
    total_transitions: int = 0

    def summary(self) -> str:
        """Human-readable summary of the conformance check."""
        lines = [
            f"Conformance: fitness={self.fitness:.3f} "
            f"({self.total_transitions} transitions checked)",
        ]
        if self.skipped_states:
            lines.append(f"  Skipped states: {len(self.skipped_states)}")
            for s in self.skipped_states:
                lines.append(f"    {s['entity_uid']}: {s['from_state']} -> {s['to_state']}")
        if self.unauthorized_transitions:
            lines.append(f"  Unauthorized: {len(self.unauthorized_transitions)}")
            for u in self.unauthorized_transitions:
                lines.append(f"    {u['entity_uid']}: {u['from_state']} -> {u['to_state']}")
        if not self.violations:
            lines.append("  No violations.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The canonical state ordering for skip detection
# ---------------------------------------------------------------------------

_STATE_ORDER: list[str] = [
    "INCUBATOR",
    "LOCAL",
    "CANDIDATE",
    "PUBLIC_PROCESS",
    "GRADUATED",
    "ARCHIVED",
]

_STATE_INDEX: dict[str, int] = {s: i for i, s in enumerate(_STATE_ORDER)}


# ---------------------------------------------------------------------------
# Trace extraction
# ---------------------------------------------------------------------------

def extract_promotion_trace(
    registry: dict[str, Any],
) -> list[TraceEntry]:
    """Extract observed promotion history from a registry.

    This looks for repos that have a ``promotion_history`` list in their
    registry entry.  Each history entry should have ``from_state``,
    ``to_state``, and optionally ``timestamp``.

    For repos without explicit history, if they have a ``promotion_status``
    that differs from the default "LOCAL", a synthetic trace entry is
    created: LOCAL -> current_status.

    Args:
        registry: The loaded registry dict.

    Returns:
        List of TraceEntry objects in declaration order.
    """
    trace: list[TraceEntry] = []

    organs = registry.get("organs", {})
    for _organ_key, organ_data in organs.items():
        repos = organ_data.get("repositories", [])
        for repo in repos:
            name = repo.get("name", "unknown")
            org = repo.get("org", "")
            entity_uid = f"{org}/{name}" if org else name

            # Explicit history
            history = repo.get("promotion_history", [])
            if history and isinstance(history, list):
                for entry in history:
                    if isinstance(entry, dict):
                        trace.append(TraceEntry(
                            entity_uid=entity_uid,
                            from_state=entry.get("from_state", ""),
                            to_state=entry.get("to_state", ""),
                            timestamp=entry.get("timestamp", ""),
                        ))
            else:
                # Synthetic trace from current status
                status = repo.get("promotion_status", "LOCAL")
                if status and status != "LOCAL":
                    trace.append(TraceEntry(
                        entity_uid=entity_uid,
                        from_state="LOCAL",
                        to_state=status,
                        timestamp="",
                    ))

    return trace


# ---------------------------------------------------------------------------
# Conformance checking
# ---------------------------------------------------------------------------

def check_trace_conformance(
    trace: list[TraceEntry],
    valid_transitions: dict[str, list[str]] | None = None,
) -> ConformanceResult:
    """Compare an observed trace against the state machine specification.

    Fitness is computed as:
        fitness = 1 - (violation_count / total_transitions)

    where violation_count is the sum of skipped states and unauthorized
    transitions.

    Args:
        trace:             List of observed TraceEntry objects.
        valid_transitions: Dict mapping current-state to valid targets.
                           Defaults to FALLBACK_TRANSITIONS.

    Returns:
        ConformanceResult with fitness score and violation details.
    """
    if valid_transitions is None:
        valid_transitions = FALLBACK_TRANSITIONS

    result = ConformanceResult(total_transitions=len(trace))

    if not trace:
        result.fitness = 1.0
        return result

    skipped = detect_skipped_states(trace, valid_transitions)
    unauthorized = detect_unauthorized_transitions(trace, valid_transitions)

    result.skipped_states = skipped
    result.unauthorized_transitions = unauthorized

    # Build violation messages
    for s in skipped:
        result.violations.append(
            f"Skipped state: {s['entity_uid']} went "
            f"{s['from_state']} -> {s['to_state']} "
            f"(skipped: {', '.join(s['skipped'])})",
        )
    for u in unauthorized:
        result.violations.append(
            f"Unauthorized: {u['entity_uid']} attempted "
            f"{u['from_state']} -> {u['to_state']}",
        )

    violation_count = len(skipped) + len(unauthorized)
    if result.total_transitions > 0:
        result.fitness = 1.0 - (violation_count / result.total_transitions)
        # Clamp to [0.0, 1.0]
        result.fitness = max(0.0, min(1.0, result.fitness))

    return result


# ---------------------------------------------------------------------------
# Specific detectors
# ---------------------------------------------------------------------------

def detect_skipped_states(
    trace: list[TraceEntry],
    valid_transitions: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Detect transitions that skip intermediate states.

    A "skip" occurs when the from_state and to_state are both in the
    canonical ordering but the to_state is more than one forward step
    away and the direct transition is not in the valid transitions table.

    Args:
        trace:             List of observed TraceEntry objects.
        valid_transitions: Transition table (defaults to FALLBACK_TRANSITIONS).

    Returns:
        List of dicts with keys: entity_uid, from_state, to_state, skipped.
    """
    if valid_transitions is None:
        valid_transitions = FALLBACK_TRANSITIONS

    results: list[dict[str, Any]] = []

    for entry in trace:
        from_idx = _STATE_INDEX.get(entry.from_state)
        to_idx = _STATE_INDEX.get(entry.to_state)

        # Both states must be in the canonical ordering
        if from_idx is None or to_idx is None:
            continue

        # Only consider forward movement (not demotions or ARCHIVED)
        if to_idx <= from_idx:
            continue

        # Check if the direct transition is valid
        valid_targets = valid_transitions.get(entry.from_state, [])
        if entry.to_state in valid_targets:
            continue

        # Identify skipped intermediate states
        skipped = [_STATE_ORDER[i] for i in range(from_idx + 1, to_idx)]
        if skipped:
            results.append({
                "entity_uid": entry.entity_uid,
                "from_state": entry.from_state,
                "to_state": entry.to_state,
                "skipped": skipped,
            })

    return results


def detect_unauthorized_transitions(
    trace: list[TraceEntry],
    valid_transitions: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Detect transitions not present in the valid transition table.

    Args:
        trace:             List of observed TraceEntry objects.
        valid_transitions: Transition table (defaults to FALLBACK_TRANSITIONS).

    Returns:
        List of dicts with keys: entity_uid, from_state, to_state, timestamp.
    """
    if valid_transitions is None:
        valid_transitions = FALLBACK_TRANSITIONS

    results: list[dict[str, Any]] = []

    for entry in trace:
        valid_targets = valid_transitions.get(entry.from_state)

        if valid_targets is None:
            # Unknown source state
            results.append({
                "entity_uid": entry.entity_uid,
                "from_state": entry.from_state,
                "to_state": entry.to_state,
                "timestamp": entry.timestamp,
                "reason": f"unknown source state: {entry.from_state}",
            })
            continue

        if entry.to_state not in valid_targets:
            results.append({
                "entity_uid": entry.entity_uid,
                "from_state": entry.from_state,
                "to_state": entry.to_state,
                "timestamp": entry.timestamp,
                "reason": (
                    f"transition {entry.from_state} -> {entry.to_state} not in "
                    f"valid targets: {valid_targets}"
                ),
            })

    return results
