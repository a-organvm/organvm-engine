"""Event tier classification for the Testament Protocol (Ring 3).

Tiers determine syndication behavior:
  GOVERNANCE      → Full dedicated social post (Bluesky, Mastodon, Discord, Ghost)
  MILESTONE       → Announcement post (Bluesky, Mastodon, Discord)
  OPERATIONAL     → Bundled into digest (Ghost, Portal)
  INFRASTRUCTURE  → Not syndicated (chain-only)
"""

from __future__ import annotations

import enum


class EventTier(enum.Enum):
    """Syndication tier for testament events."""

    GOVERNANCE = "governance"
    MILESTONE = "milestone"
    OPERATIONAL = "operational"
    INFRASTRUCTURE = "infrastructure"

    @property
    def syndicated(self) -> bool:
        """Whether events at this tier are syndicated to social platforms."""
        return self in (EventTier.GOVERNANCE, EventTier.MILESTONE)


TIER_MAP: dict[str, EventTier] = {
    # GOVERNANCE — syndicated individually
    "governance.promotion": EventTier.GOVERNANCE,
    "governance.audit": EventTier.GOVERNANCE,
    "governance.dependency_change": EventTier.GOVERNANCE,
    "testament.genesis": EventTier.GOVERNANCE,
    "testament.checkpoint": EventTier.GOVERNANCE,
    "testament.verified": EventTier.GOVERNANCE,
    # MILESTONE — syndicated as announcements
    "ci.health": EventTier.MILESTONE,
    "content.published": EventTier.MILESTONE,
    "ecosystem.mutation": EventTier.MILESTONE,
    "pitch.generated": EventTier.MILESTONE,
    # OPERATIONAL — bundled into digests
    "registry.update": EventTier.OPERATIONAL,
    "seed.update": EventTier.OPERATIONAL,
    "metrics.update": EventTier.OPERATIONAL,
    "context.sync": EventTier.OPERATIONAL,
    "entity.created": EventTier.OPERATIONAL,
    "entity.archived": EventTier.OPERATIONAL,
    "ontologia.variable": EventTier.OPERATIONAL,
    # INFRASTRUCTURE — chain-only
    "git.sync": EventTier.INFRASTRUCTURE,
    "agent.punch_in": EventTier.INFRASTRUCTURE,
    "agent.punch_out": EventTier.INFRASTRUCTURE,
    "agent.tool_lock": EventTier.INFRASTRUCTURE,
}


def classify_event_tier(event_type: str) -> EventTier:
    """Classify an event type into its syndication tier.

    Unknown event types default to OPERATIONAL.
    """
    return TIER_MAP.get(event_type, EventTier.OPERATIONAL)
