"""Deep structural indexer — drills to absolute bottom of every repo.

Perception + Normalization layers of the AMMOI architecture.
Identifies cohesive atomic components and generates micro-seeds
for a full living breathing index.

Pipeline: scan → identify → seed
  1. Scanner walks every directory to leaf level
  2. Cohesion analyzer classifies atomic components bottom-up
  3. Seed generator produces micro-seeds with dependency edges
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.indexer.cohesion import identify_components
from organvm_engine.indexer.scanner import walk_repo
from organvm_engine.indexer.seed_gen import generate_seeds
from organvm_engine.indexer.types import (
    Component,
    ComponentSeed,
    DirectoryNode,
    RepoIndex,
    SystemIndex,
)

__all__ = [
    "Component",
    "ComponentSeed",
    "DirectoryNode",
    "RepoIndex",
    "SystemIndex",
    "index_repo",
    "run_deep_index",
]


def index_repo(
    repo_path: Path,
    repo_name: str,
    organ_key: str,
) -> RepoIndex:
    """Index a single repository: scan → identify → seed."""
    tree = walk_repo(repo_path)
    if tree is None:
        return RepoIndex(repo=repo_name, organ=organ_key)

    components = identify_components(tree, repo_name, organ_key, repo_path)
    seeds = generate_seeds(components, repo_path)

    max_depth = max((c.depth for c in components), default=0)

    return RepoIndex(
        repo=repo_name,
        organ=organ_key,
        tree=tree,
        components=components,
        seeds=seeds,
        total_files=tree.total_files,
        total_lines=tree.total_lines,
        max_depth=max_depth,
    )


def run_deep_index(
    workspace: Path,
    registry: dict,
    repo_filter: str | None = None,
    organ_filter: str | None = None,
) -> SystemIndex:
    """Run the deep structural index across the workspace.

    Scans every non-archived repo, walks to absolute bottom,
    identifies atomic components, generates micro-seeds.
    """
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.registry.query import all_repos

    r2d = registry_key_to_dir()
    repo_indices: list[RepoIndex] = []
    by_organ: dict[str, int] = {}
    by_language: dict[str, int] = {}
    by_cohesion: dict[str, int] = {}
    total_components = 0

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue

        name = repo.get("name", "")
        if not name:
            continue

        if organ_filter and organ_key != organ_filter:
            continue
        if repo_filter and name != repo_filter:
            continue

        organ_dir = r2d.get(organ_key, "")
        if not organ_dir:
            continue

        repo_path = workspace / organ_dir / name
        if not repo_path.is_dir():
            continue

        idx = index_repo(repo_path, name, organ_key)
        repo_indices.append(idx)

        for comp in idx.components:
            total_components += 1
            by_organ[organ_key] = by_organ.get(organ_key, 0) + 1
            by_language[comp.dominant_language] = (
                by_language.get(comp.dominant_language, 0) + 1
            )
            by_cohesion[comp.cohesion_type] = (
                by_cohesion.get(comp.cohesion_type, 0) + 1
            )

    return SystemIndex(
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
        scanned_repos=len(repo_indices),
        total_components=total_components,
        repos=repo_indices,
        by_organ=by_organ,
        by_language=by_language,
        by_cohesion=by_cohesion,
    )
