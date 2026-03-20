"""Tests for Testament Protocol event tier classification."""

from organvm_engine.ledger.tiers import EventTier, classify_event_tier


class TestEventTier:

    def test_governance_events(self):
        for et in [
            "governance.promotion",
            "governance.audit",
            "governance.dependency_change",
            "testament.genesis",
            "testament.checkpoint",
            "testament.verified",
        ]:
            assert classify_event_tier(et) == EventTier.GOVERNANCE, f"{et} should be GOVERNANCE"

    def test_milestone_events(self):
        for et in ["ci.health", "content.published", "ecosystem.mutation", "pitch.generated"]:
            assert classify_event_tier(et) == EventTier.MILESTONE, f"{et} should be MILESTONE"

    def test_operational_events(self):
        for et in [
            "registry.update",
            "seed.update",
            "metrics.update",
            "context.sync",
            "entity.created",
            "entity.archived",
            "ontologia.variable",
        ]:
            assert classify_event_tier(et) == EventTier.OPERATIONAL, f"{et} should be OPERATIONAL"

    def test_infrastructure_events(self):
        for et in ["git.sync", "agent.punch_in", "agent.punch_out", "agent.tool_lock"]:
            assert classify_event_tier(et) == EventTier.INFRASTRUCTURE, (
                f"{et} should be INFRASTRUCTURE"
            )

    def test_unknown_event_defaults_to_operational(self):
        assert classify_event_tier("unknown.type") == EventTier.OPERATIONAL

    def test_all_existing_event_types_classified(self):
        from organvm_engine.events.spine import EventType

        for et in EventType:
            tier = classify_event_tier(et.value)
            assert isinstance(tier, EventTier)

    def test_tier_syndicated_flag(self):
        assert EventTier.GOVERNANCE.syndicated is True
        assert EventTier.MILESTONE.syndicated is True
        assert EventTier.OPERATIONAL.syndicated is False
        assert EventTier.INFRASTRUCTURE.syndicated is False

    def test_tier_values_are_strings(self):
        for tier in EventTier:
            assert isinstance(tier.value, str)
