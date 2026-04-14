"""Tests for the fabrica task router (SPEC-024 Phase 3)."""

from __future__ import annotations

import pytest

from organvm_engine.fabrica.router import (
    DEFAULT_ROUTING_TABLE,
    RoutingRule,
    route_task,
)

# ---------------------------------------------------------------------------
# Agent-type routing
# ---------------------------------------------------------------------------


class TestAgentRouting:
    def test_route_copilot_agent(self) -> None:
        assert route_task(agent_types=["copilot"]) == "copilot"

    def test_route_jules_agent(self) -> None:
        assert route_task(agent_types=["jules"]) == "jules"

    def test_route_claude_agent(self) -> None:
        assert route_task(agent_types=["claude"]) == "claude"

    def test_multiple_agents_first_match_wins(self) -> None:
        # copilot and jules both at priority 10; sorted is stable,
        # so the first one in table order wins.
        result = route_task(agent_types=["copilot", "jules"])
        assert result in ("copilot", "jules")


# ---------------------------------------------------------------------------
# Tag-based routing
# ---------------------------------------------------------------------------


class TestTagRouting:
    def test_route_scheduled_tag(self) -> None:
        assert route_task(tags=["scheduled"]) == "launchagent"

    def test_route_recurring_tag(self) -> None:
        assert route_task(tags=["recurring"]) == "launchagent"

    def test_route_ci_tag(self) -> None:
        assert route_task(tags=["ci"]) == "actions"

    def test_route_workflow_tag(self) -> None:
        assert route_task(tags=["workflow"]) == "actions"


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


class TestFallback:
    def test_no_params_falls_to_human(self) -> None:
        assert route_task() == "human"

    def test_unknown_agent_falls_to_human(self) -> None:
        assert route_task(agent_types=["unknown_agent"]) == "human"

    def test_unknown_tags_fall_to_human(self) -> None:
        assert route_task(tags=["miscellaneous"]) == "human"

    def test_empty_lists_fall_to_human(self) -> None:
        assert route_task(agent_types=[], tags=[]) == "human"


# ---------------------------------------------------------------------------
# Override
# ---------------------------------------------------------------------------


class TestOverride:
    def test_backend_override_bypasses_routing(self) -> None:
        # Even with a copilot agent hint, override wins
        result = route_task(agent_types=["copilot"], backend_override="human")
        assert result == "human"

    def test_override_returns_exact_backend(self) -> None:
        assert route_task(backend_override="actions") == "actions"

    def test_invalid_override_raises(self) -> None:
        with pytest.raises(ValueError, match="not in VALID_BACKENDS"):
            route_task(backend_override="nonexistent")


# ---------------------------------------------------------------------------
# Custom routing table
# ---------------------------------------------------------------------------


class TestCustomTable:
    def test_custom_table_is_used(self) -> None:
        custom = [
            RoutingRule(backend="actions", match_tags=["deploy"], priority=1),
            RoutingRule(backend="human", priority=999),
        ]
        assert route_task(tags=["deploy"], routing_table=custom) == "actions"

    def test_custom_table_fallback(self) -> None:
        custom = [RoutingRule(backend="claude", priority=999)]
        assert route_task(routing_table=custom) == "claude"

    def test_scope_matching(self) -> None:
        custom = [
            RoutingRule(backend="jules", match_scopes=["heavy"], priority=5),
            RoutingRule(backend="human", priority=999),
        ]
        assert route_task(scope="heavy", routing_table=custom) == "jules"
        assert route_task(scope="light", routing_table=custom) == "human"

    def test_empty_table_returns_human(self) -> None:
        assert route_task(routing_table=[]) == "human"


# ---------------------------------------------------------------------------
# RoutingRule validation
# ---------------------------------------------------------------------------


class TestRoutingRuleValidation:
    def test_invalid_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend"):
            RoutingRule(backend="nonexistent")

    def test_valid_backends_accepted(self) -> None:
        for name in ("copilot", "jules", "actions", "claude", "launchagent", "human"):
            rule = RoutingRule(backend=name)
            assert rule.backend == name


# ---------------------------------------------------------------------------
# Default table structure
# ---------------------------------------------------------------------------


class TestDefaultTable:
    def test_default_table_not_empty(self) -> None:
        assert len(DEFAULT_ROUTING_TABLE) > 0

    def test_human_is_lowest_priority(self) -> None:
        priorities = [(r.backend, r.priority) for r in DEFAULT_ROUTING_TABLE]
        human_rules = [p for b, p in priorities if b == "human"]
        non_human = [p for b, p in priorities if b != "human"]
        assert all(h > nh for h in human_rules for nh in non_human)

    def test_all_six_backends_covered(self) -> None:
        backends = {r.backend for r in DEFAULT_ROUTING_TABLE}
        assert backends == {"copilot", "jules", "claude", "launchagent", "actions", "human"}
