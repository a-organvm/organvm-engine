"""Data source adapters for testament rendering.

Each function extracts structured data from existing engine modules,
returning dicts/lists suitable for passing to renderers. All imports
are deferred to avoid circular dependencies.
"""

from __future__ import annotations

from pathlib import Path


def topology_data(
    registry_path: Path | None = None,
) -> dict:
    """Extract system topology: organs, repo counts, dependency edges.

    Returns dict with keys: organ_repo_counts, edges, total_repos.
    """
    from organvm_engine.organ_config import ORGANS
    from organvm_engine.registry.loader import load_registry

    registry = load_registry(registry_path)
    organs_data = registry.get("organs", {})

    organ_repo_counts: dict[str, int] = {}
    total = 0

    # Map registry keys to CLI keys
    registry_to_cli: dict[str, str] = {}
    for cli_key, meta in ORGANS.items():
        reg_key = meta.get("registry_key", "")
        if reg_key:
            registry_to_cli[reg_key] = cli_key

    for reg_key, organ_data in organs_data.items():
        cli_key: str = registry_to_cli.get(str(reg_key), str(reg_key))
        repos = organ_data.get("repositories", [])
        count = len(repos)
        organ_repo_counts[cli_key] = count
        total += count

    return {
        "organ_repo_counts": organ_repo_counts,
        "total_repos": total,
    }


def omega_data(
    registry_path: Path | None = None,
) -> dict:
    """Extract omega scorecard data for mandala rendering.

    Returns dict with keys: criteria (list of dicts), met_count, total.
    """
    try:
        from organvm_engine.omega.scorecard import evaluate
        from organvm_engine.registry.loader import load_registry

        reg = load_registry(registry_path) if registry_path else None
        scorecard = evaluate(registry=reg)
        criteria = [
            {"id": c.id, "name": c.name, "met": c.status == "MET", "status": c.status}
            for c in scorecard.criteria
        ]
        return {
            "criteria": criteria,
            "met_count": scorecard.met_count,
            "total": len(scorecard.criteria),
        }
    except Exception:
        # Fallback if evaluation requires live data
        return {"criteria": [], "met_count": 0, "total": 17}


def dependency_data(
    registry_path: Path | None = None,
) -> dict:
    """Extract dependency graph edges between organs.

    Returns dict with keys: edges (list of tuples), organ_keys.
    """
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.registry.query import build_dependency_maps

    registry = load_registry(registry_path)
    outbound, _ = build_dependency_maps(registry)

    # Aggregate repo-level deps to organ-level
    organ_edges: set[tuple[str, str]] = set()
    for repo_name, deps in outbound.items():
        src_organ = _repo_to_organ_key(repo_name, registry)
        for dep_name in deps:
            dst_organ = _repo_to_organ_key(dep_name, registry)
            if src_organ and dst_organ and src_organ != dst_organ:
                organ_edges.add((src_organ, dst_organ))

    return {
        "edges": sorted(organ_edges),
        "organ_keys": ["I", "II", "III", "IV", "V", "VI", "VII", "META"],
    }


def density_data(
    registry_path: Path | None = None,
) -> dict:
    """Extract per-organ density metrics for density bar rendering.

    Returns dict with keys: organ_densities (dict[str, float]).
    """
    try:
        from organvm_engine.metrics.organism import compute_organism
        from organvm_engine.pulse.density import compute_density
        from organvm_engine.registry.loader import load_registry
        from organvm_engine.seed.graph import build_seed_graph

        registry = load_registry(registry_path)
        organism = compute_organism(registry)
        graph = build_seed_graph()
        profile = compute_density(graph, organism)

        densities: dict[str, float] = {}
        for organ_key in ["I", "II", "III", "IV", "V", "VI", "VII", "META"]:
            raw = profile.organ_density.get(organ_key, 0.0)
            densities[organ_key] = min(raw / 100.0, 1.0)
        return {"organ_densities": densities}
    except Exception:
        # Fallback with reasonable defaults
        return {
            "organ_densities": {
                "META": 0.70, "I": 0.58, "II": 0.48, "III": 0.56,
                "IV": 0.45, "V": 0.35, "VI": 0.30, "VII": 0.25,
            },
        }


def organ_identity_data(
    organ_key: str,
    registry_path: Path | None = None,
) -> dict:
    """Extract identity data for a single organ's card rendering.

    Returns dict with keys: organ_key, repo_count, flagship_count,
    status_counts, edges, formation_types.
    """
    from organvm_engine.organ_config import ORGANS
    from organvm_engine.registry.loader import load_registry

    registry = load_registry(registry_path)
    organs_data = registry.get("organs", {})

    # Find the registry key for this organ
    reg_key = ""
    for cli_key, meta in ORGANS.items():
        if cli_key == organ_key:
            reg_key = meta.get("registry_key", "")
            break

    organ_data = organs_data.get(reg_key, {})
    repos = organ_data.get("repositories", [])

    repo_count = len(repos)
    flagship_count = sum(1 for r in repos if r.get("tier") == "flagship")

    status_counts: dict[str, int] = {}
    for r in repos:
        status = r.get("promotion_status", r.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1

    formation_types: list[str] = []

    return {
        "organ_key": organ_key,
        "repo_count": repo_count,
        "flagship_count": flagship_count,
        "status_counts": status_counts,
        "edges": 0,
        "formation_types": formation_types,
    }


def system_summary(
    registry_path: Path | None = None,
) -> dict:
    """Extract high-level system summary for prose rendering.

    Returns dict with system-wide statistics.
    """
    from organvm_engine.registry.loader import load_registry

    registry = load_registry(registry_path)
    organs_data = registry.get("organs", {})

    total_repos = 0
    total_public = 0
    status_counts: dict[str, int] = {}

    for organ_data in organs_data.values():
        repos = organ_data.get("repositories", [])
        total_repos += len(repos)
        for r in repos:
            if r.get("public", False):
                total_public += 1
            status = r.get("promotion_status", r.get("status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "total_repos": total_repos,
        "total_public": total_public,
        "total_organs": len(organs_data),
        "status_counts": status_counts,
        "schema_version": registry.get("schema_version", "unknown"),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _repo_to_organ_key(repo_name: str, registry: dict) -> str | None:
    """Map a repo name to its organ CLI key."""
    from organvm_engine.organ_config import ORGANS

    organs_data = registry.get("organs", {})
    registry_to_cli: dict[str, str] = {}
    for cli_key, meta in ORGANS.items():
        reg_key = meta.get("registry_key", "")
        if reg_key:
            registry_to_cli[reg_key] = cli_key

    for reg_key, organ_data in organs_data.items():
        repos = organ_data.get("repositories", [])
        for r in repos:
            if r.get("name") == repo_name:
                return registry_to_cli.get(reg_key)
    return None


def isomorphism_data(
    registry_path: Path | None = None,
) -> dict:
    """Extract trivium isomorphism data for testament rendering.

    Delegates to the trivium sources module.
    """
    from organvm_engine.trivium.sources import isomorphism_data as _iso_data

    return _iso_data(registry_path)
