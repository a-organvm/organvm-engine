"""Agent routing table for the Cyclic Dispatch Protocol (SPEC-024).

Maps task characteristics to dispatch backends. The routing table
is data, not hardcoded logic -- extension without code changes.

During HANDOFF, each atomized task is fed through ``route_task()``
which walks the table in priority order and returns the first
matching backend name. An explicit ``backend_override`` short-circuits
all matching logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from organvm_engine.fabrica.backends import VALID_BACKENDS

# ---------------------------------------------------------------------------
# Routing rule
# ---------------------------------------------------------------------------


@dataclass
class RoutingRule:
    """A single routing predicate.

    Match criteria are OR'd within a field and AND-free across fields:
    any single field match is sufficient. A rule with no match criteria
    acts as a catch-all (ordered by priority).
    """

    backend: str
    match_agents: list[str] = field(default_factory=list)
    match_scopes: list[str] = field(default_factory=list)
    match_tags: list[str] = field(default_factory=list)
    priority: int = 100  # lower = higher priority

    def __post_init__(self) -> None:
        if self.backend not in VALID_BACKENDS:
            raise ValueError(
                f"Unknown backend {self.backend!r}. "
                f"Valid: {', '.join(sorted(VALID_BACKENDS))}",
            )


# ---------------------------------------------------------------------------
# Default routing table
# ---------------------------------------------------------------------------

DEFAULT_ROUTING_TABLE: list[RoutingRule] = [
    # Agent-specific rules (highest priority)
    RoutingRule(backend="copilot", match_agents=["copilot"], priority=10),
    RoutingRule(backend="jules", match_agents=["jules"], priority=10),
    RoutingRule(backend="claude", match_agents=["claude"], priority=10),
    # Tag-based rules
    RoutingRule(backend="launchagent", match_tags=["scheduled", "recurring"], priority=20),
    RoutingRule(backend="actions", match_tags=["ci", "workflow"], priority=20),
    # Catch-all fallback
    RoutingRule(backend="human", priority=999),
]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def route_task(
    agent_types: list[str] | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    backend_override: str | None = None,
    routing_table: list[RoutingRule] | None = None,
) -> str:
    """Route a task to the appropriate backend.

    Returns the backend name (one of ``VALID_BACKENDS``).

    Parameters
    ----------
    agent_types:
        Agent types requested for this task (e.g. ``["copilot"]``).
    scope:
        Task scope -- ``"light"``, ``"medium"``, or ``"heavy"``.
    tags:
        Semantic tags on the task (e.g. ``["ci", "lint"]``).
    backend_override:
        If set, bypasses all routing logic and returns this value
        directly.  Validated against ``VALID_BACKENDS``.
    routing_table:
        Custom routing table.  Falls back to ``DEFAULT_ROUTING_TABLE``.
    """
    if backend_override:
        if backend_override not in VALID_BACKENDS:
            raise ValueError(
                f"Override backend {backend_override!r} not in "
                f"VALID_BACKENDS: {', '.join(sorted(VALID_BACKENDS))}",
            )
        return backend_override

    table = routing_table or DEFAULT_ROUTING_TABLE
    agents = agent_types or []
    task_tags = tags or []

    for rule in sorted(table, key=lambda r: r.priority):
        # Agent match
        if rule.match_agents and any(a in rule.match_agents for a in agents):
            return rule.backend
        # Tag match
        if rule.match_tags and any(t in rule.match_tags for t in task_tags):
            return rule.backend
        # Scope match
        if rule.match_scopes and scope in rule.match_scopes:
            return rule.backend
        # Catch-all (no criteria = fallback)
        if not rule.match_agents and not rule.match_tags and not rule.match_scopes:
            return rule.backend

    # Ultimate fallback if table is empty or fully filtered
    return "human"
