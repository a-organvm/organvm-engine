"""Network testament metrics for the Living Data Organism.

Calculates network density, engagement velocity, mirror coverage,
and reciprocity from the network maps and engagement ledger.
"""

from __future__ import annotations

from organvm_engine.network.schema import EngagementEntry, NetworkMap


def network_density(maps: list[NetworkMap], total_active_repos: int) -> float:
    """Ratio of repos with populated network-map.yaml to total active repos.

    A density of 1.0 means every active repo has at least one mirror.
    """
    if total_active_repos == 0:
        return 0.0
    populated = sum(1 for m in maps if m.mirror_count > 0)
    return populated / total_active_repos


def mirror_coverage(maps: list[NetworkMap]) -> dict[str, float]:
    """Per-lens coverage: what % of mapped repos have at least one mirror in each lens.

    Returns:
        {"technical": 0.8, "parallel": 0.5, "kinship": 0.3}
    """
    if not maps:
        return {"technical": 0.0, "parallel": 0.0, "kinship": 0.0}

    total = len(maps)
    return {
        "technical": sum(1 for m in maps if m.technical) / total,
        "parallel": sum(1 for m in maps if m.parallel) / total,
        "kinship": sum(1 for m in maps if m.kinship) / total,
    }


def engagement_velocity(entries: list[EngagementEntry], period_days: int = 30) -> float:
    """Engagement actions per period.

    Simple count of actions in the given period. Growth rate can be
    computed by comparing consecutive periods.
    """
    if not entries or period_days <= 0:
        return 0.0
    return len(entries) / period_days


def network_reciprocity(entries: list[EngagementEntry]) -> float:
    """Ratio of actions that received a response/outcome vs total actions.

    A reciprocity of 1.0 means every action got a response.
    0.0 means no responses recorded (or no actions taken).
    """
    if not entries:
        return 0.0
    with_outcome = sum(1 for e in entries if e.outcome)
    return with_outcome / len(entries)


def lens_balance(entries: list[EngagementEntry]) -> dict[str, float]:
    """Distribution of engagement across the three lenses.

    Perfect balance is 0.333 each. Measures whether engagement
    is skewing toward one lens (e.g., only technical contributions).
    """
    if not entries:
        return {"technical": 0.0, "parallel": 0.0, "kinship": 0.0}

    total = len(entries)
    counts: dict[str, int] = {"technical": 0, "parallel": 0, "kinship": 0}
    for e in entries:
        if e.lens in counts:
            counts[e.lens] += 1

    return {k: v / total for k, v in counts.items()}


def form_balance(entries: list[EngagementEntry]) -> dict[str, float]:
    """Distribution of engagement across the four forms.

    Measures whether engagement is skewing toward one form
    (e.g., only presence without contribution).
    """
    if not entries:
        return {"presence": 0.0, "contribution": 0.0, "dialogue": 0.0, "invitation": 0.0}

    total = len(entries)
    counts: dict[str, int] = {
        "presence": 0, "contribution": 0, "dialogue": 0, "invitation": 0,
    }
    for e in entries:
        if e.action_type in counts:
            counts[e.action_type] += 1

    return {k: v / total for k, v in counts.items()}


def convergence_points(maps: list[NetworkMap]) -> dict[str, list[str]]:
    """External projects mirrored by multiple ORGANVM repos.

    These are high-value targets — communities where the system
    has multiple points of contact.

    Returns:
        {external_project: [organvm_repo, organvm_repo, ...]}
    """
    project_repos: dict[str, list[str]] = {}
    for nmap in maps:
        for mirror in nmap.all_mirrors:
            if mirror.project not in project_repos:
                project_repos[mirror.project] = []
            project_repos[mirror.project].append(nmap.repo)

    # Only return projects with 2+ ORGANVM repos
    return {p: repos for p, repos in project_repos.items() if len(repos) >= 2}
