"""Seed generator — produces micro-seeds for atomic components.

Each micro-seed captures enough metadata to serve as a component's
identity in the living index: parent repo, path, language, dependency
edges, and a content fingerprint for change detection.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from organvm_engine.indexer.types import Component, ComponentSeed


def generate_seeds(
    components: list[Component],
    repo_path: Path | None = None,
) -> list[ComponentSeed]:
    """Generate micro-seeds for a list of components."""
    seeds: list[ComponentSeed] = []

    for comp in components:
        fingerprint = _compute_fingerprint(comp, repo_path)
        produces = _extract_produces(comp)
        consumes = [p.rstrip("/").split("/")[-1] for p in comp.imports_from]

        seeds.append(ComponentSeed(
            parent_repo=comp.repo,
            organ=comp.organ,
            path=comp.path,
            cohesion_type=comp.cohesion_type,
            files=comp.file_count,
            lines=comp.line_count,
            language=comp.dominant_language,
            produces=produces,
            consumes=consumes,
            depth=comp.depth,
            fingerprint=fingerprint,
        ))

    return seeds


def _compute_fingerprint(comp: Component, repo_path: Path | None) -> str:
    """Compute a structural fingerprint for change detection.

    Uses path + file listing (not full file contents) for speed.
    Same fingerprint across two scans = directory structure unchanged.
    """
    h = hashlib.sha256()
    h.update(f"{comp.repo}:{comp.path}".encode())
    h.update(f"files={comp.file_count}".encode())
    h.update(f"lines={comp.line_count}".encode())
    h.update(f"lang={comp.dominant_language}".encode())

    if repo_path:
        comp_dir = repo_path / comp.path
        if comp_dir.is_dir():
            file_names = sorted(f.name for f in comp_dir.iterdir() if f.is_file())
            for fname in file_names:
                h.update(fname.encode())

    return h.hexdigest()[:16]


def _extract_produces(comp: Component) -> list[str]:
    """Derive what this component produces (its importable name)."""
    name = comp.path.rstrip("/").split("/")[-1]
    return [name]
