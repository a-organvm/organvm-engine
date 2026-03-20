"""Digest assembly for operational-tier testament events.

Produces human-readable summaries of event batches for social syndication
(Ghost blog posts, Discord digests, weekly newsletters).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from organvm_engine.events.spine import EventRecord
from organvm_engine.ledger.tiers import classify_event_tier


@dataclass
class DigestSummary:
    """Summary of a batch of events for syndication."""

    event_count: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_tier: dict[str, int] = field(default_factory=dict)
    by_organ: dict[str, int] = field(default_factory=dict)
    sequence_range: tuple[int, int] = (-1, -1)
    governance_highlights: list[str] = field(default_factory=list)

    def render_text(self) -> str:
        """Render a plain-text digest summary."""
        lines = [f"Testament Digest — {self.event_count} event(s)"]
        if self.sequence_range[0] >= 0:
            lines.append(
                f"Sequence range: {self.sequence_range[0]}-{self.sequence_range[1]}",
            )
        lines.append("")

        if self.by_tier:
            lines.append("By tier:")
            for tier, count in sorted(self.by_tier.items()):
                lines.append(f"  {tier}: {count}")

        if self.by_type:
            lines.append("\nBy type:")
            for etype, count in sorted(self.by_type.items(), key=lambda x: -x[1]):
                lines.append(f"  {etype}: {count}")

        if self.governance_highlights:
            lines.append("\nGovernance highlights:")
            for h in self.governance_highlights:
                lines.append(f"  - {h}")

        return "\n".join(lines)


def assemble_digest(events: list[EventRecord]) -> DigestSummary:
    """Assemble a digest summary from a list of events."""
    if not events:
        return DigestSummary()

    type_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    organ_counts: Counter[str] = Counter()
    highlights: list[str] = []

    for ev in events:
        type_counts[ev.event_type] += 1
        tier = classify_event_tier(ev.event_type)
        tier_counts[tier.value] += 1
        if ev.source_organ:
            organ_counts[ev.source_organ] += 1
        if tier.value == "governance":
            desc = f"{ev.event_type}"
            if ev.source_repo:
                desc += f" ({ev.source_repo})"
            highlights.append(desc)

    seqs = [ev.sequence for ev in events if ev.sequence >= 0]
    seq_range = (min(seqs), max(seqs)) if seqs else (-1, -1)

    return DigestSummary(
        event_count=len(events),
        by_type=dict(type_counts),
        by_tier=dict(tier_counts),
        by_organ=dict(organ_counts),
        sequence_range=seq_range,
        governance_highlights=highlights,
    )
