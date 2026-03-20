"""Social renderer — system pulse as social-ready content.

Generates concise, publishable snippets from system state.
Ready for ORGAN-VII kerygma pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class SocialPulse:
    """A social-ready system pulse."""

    short: str  # ~140 chars (tweet-length)
    medium: str  # ~280 chars
    long: str  # ~500 chars (LinkedIn-length)
    hashtags: list[str] = field(default_factory=list)
    date: str = ""


def render_pulse(
    total_repos: int = 0,
    met_ratio: float = 0.0,
    organ_densities: dict[str, float] | None = None,
    density_ranking: list[str] | None = None,
    self_portrait_text: str | None = None,
) -> SocialPulse:
    """Generate social pulse from system state."""
    densities = organ_densities or {}
    today = date.today().isoformat()
    omega_pct = int(met_ratio * 100)
    avg_density = int(sum(densities.values()) / len(densities) * 100) if densities else 0

    # Short (tweet)
    short = (
        f"ORGANVM pulse: {total_repos} repos, {omega_pct}% omega, "
        f"{avg_density}% density. The system renders itself."
    )

    # Medium
    ranking = density_ranking or sorted(
        densities, key=lambda k: densities.get(k, 0), reverse=True,
    )
    top_3 = ", ".join(ranking[:3]) if ranking else "META, I, III"
    medium = (
        f"ORGANVM system pulse — {today}\n"
        f"{total_repos} repositories across 8 organs. "
        f"Omega maturity: {omega_pct}%. "
        f"Densest organs: {top_3}. "
        f"Every computational function is also a generative function. "
        f"The system renders its own density into experience."
    )

    # Long (LinkedIn)
    long = (
        f"ORGANVM System Pulse — {today}\n\n"
        f"An eight-organ creative-institutional system comprising "
        f"{total_repos} repositories, operating at {omega_pct}% system "
        f"maturity and {avg_density}% average structural density.\n\n"
        f"Each organ specializes: Theoria (theory), Poiesis (art), "
        f"Ergon (commerce), Taxis (orchestration), Logos (discourse), "
        f"Koinonia (community), Kerygma (distribution), Meta (governance).\n\n"
        f"The testament module renders the system's operational "
        f"algorithms — dependency graph traversal, metrics computation, "
        f"promotion state evaluation — as publishable artifacts in "
        f"10 modalities: visual, statistical, schematic, mathematical, "
        f"theoretical, academic, social, philosophical, sonic, archival.\n\n"
        f"The system does not merely track data. "
        f"It renders its own density into experience."
    )

    hashtags = [
        "#ORGANVM", "#generativeSystems", "#autopoiesis",
        "#creativeInfrastructure", "#systemsArt",
    ]

    return SocialPulse(
        short=short,
        medium=medium,
        long=long,
        hashtags=hashtags,
        date=today,
    )


def render_pulse_markdown(pulse: SocialPulse) -> str:
    """Render social pulse as markdown document."""
    tags = " ".join(pulse.hashtags)
    return (
        f"# System Pulse — {pulse.date}\n\n"
        f"## Short (140 chars)\n\n{pulse.short}\n\n"
        f"## Medium (280 chars)\n\n{pulse.medium}\n\n"
        f"## Long (LinkedIn)\n\n{pulse.long}\n\n"
        f"## Tags\n\n{tags}\n"
    )
