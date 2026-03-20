"""Cross-repo network queries.

Functions for querying the network map across the full workspace —
which repos mirror which projects, where are the blind spots,
which organs have the densest external surface.
"""

from __future__ import annotations

from organvm_engine.network.schema import NetworkMap


def repos_mirroring(maps: list[NetworkMap], external_project: str) -> list[str]:
    """Find all ORGANVM repos that mirror a given external project.

    Args:
        maps: All discovered network maps.
        external_project: The external project identifier (e.g., "astral-sh/ruff").

    Returns:
        List of ORGANVM repo names that have this project as a mirror.
    """
    return [
        nmap.repo
        for nmap in maps
        if any(m.project == external_project for m in nmap.all_mirrors)
    ]


def blind_spots(maps: list[NetworkMap], all_repos: list[str]) -> list[str]:
    """Repos with no network-map.yaml or zero mirrors.

    These are the repos with no external connections documented.
    """
    mapped_repos = {nmap.repo for nmap in maps if nmap.mirror_count > 0}
    return [r for r in all_repos if r not in mapped_repos]


def organ_density(maps: list[NetworkMap]) -> dict[str, dict[str, int]]:
    """Mirror counts per organ, broken down by lens.

    Returns:
        {organ: {technical: N, parallel: N, kinship: N, total: N}}
    """
    density: dict[str, dict[str, int]] = {}
    for nmap in maps:
        organ = nmap.organ
        if organ not in density:
            density[organ] = {"technical": 0, "parallel": 0, "kinship": 0, "total": 0}
        density[organ]["technical"] += len(nmap.technical)
        density[organ]["parallel"] += len(nmap.parallel)
        density[organ]["kinship"] += len(nmap.kinship)
        density[organ]["total"] += nmap.mirror_count
    return density


def engagement_targets(
    maps: list[NetworkMap],
    lens: str | None = None,
) -> list[dict]:
    """All external projects across all maps, with metadata.

    Useful for generating a flat list of potential engagement targets.

    Args:
        maps: All network maps.
        lens: Optional filter by lens type.

    Returns:
        List of dicts with project, platform, relevance, organvm_repo, lens.
    """
    targets: list[dict] = []
    for nmap in maps:
        for lens_name in ("technical", "parallel", "kinship"):
            if lens and lens_name != lens:
                continue
            for mirror in nmap.mirrors_by_lens(lens_name):
                targets.append({
                    "project": mirror.project,
                    "platform": mirror.platform,
                    "relevance": mirror.relevance,
                    "organvm_repo": nmap.repo,
                    "lens": lens_name,
                    "engagement": mirror.engagement,
                    "url": mirror.url,
                })
    return targets
