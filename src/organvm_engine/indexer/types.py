"""Types for the deep structural indexer.

Dataclasses representing the structural census at every level:
directory nodes, atomic components, micro-seeds, and indices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DirectoryNode:
    """Tree representation of a directory with file metadata."""

    path: str  # relative to repo root ("." for root)
    name: str
    depth: int
    file_count: int = 0
    line_count: int = 0
    file_types: dict[str, int] = field(default_factory=dict)
    has_init_py: bool = False
    has_package_json: bool = False
    has_go_mod: bool = False
    has_cargo_toml: bool = False
    has_barrel_file: bool = False  # index.ts/js/tsx/jsx
    build_manifests: list[str] = field(default_factory=list)
    children: list[DirectoryNode] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def total_files(self) -> int:
        return self.file_count + sum(c.total_files for c in self.children)

    @property
    def total_lines(self) -> int:
        return self.line_count + sum(c.total_lines for c in self.children)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "depth": self.depth,
            "file_count": self.file_count,
            "line_count": self.line_count,
            "file_types": self.file_types,
            "has_init_py": self.has_init_py,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class Component:
    """An identified atomic component — the deepest functional unit."""

    repo: str
    organ: str
    path: str  # relative to repo root
    cohesion_type: str
    depth: int
    file_count: int = 0
    line_count: int = 0
    dominant_language: str = "unknown"
    imports_from: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "organ": self.organ,
            "path": self.path,
            "cohesion_type": self.cohesion_type,
            "depth": self.depth,
            "file_count": self.file_count,
            "line_count": self.line_count,
            "dominant_language": self.dominant_language,
            "imports_from": self.imports_from,
            "imported_by": self.imported_by,
        }


@dataclass
class ComponentSeed:
    """Micro-seed metadata for an atomic component."""

    parent_repo: str
    organ: str
    path: str
    cohesion_type: str
    files: int = 0
    lines: int = 0
    language: str = "unknown"
    produces: list[str] = field(default_factory=list)
    consumes: list[str] = field(default_factory=list)
    depth: int = 0
    fingerprint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": True,
            "parent_repo": self.parent_repo,
            "organ": self.organ,
            "path": self.path,
            "cohesion_type": self.cohesion_type,
            "files": self.files,
            "lines": self.lines,
            "language": self.language,
            "produces": self.produces,
            "consumes": self.consumes,
            "depth": self.depth,
            "fingerprint": self.fingerprint,
        }


@dataclass
class RepoIndex:
    """Full structural index for one repository."""

    repo: str
    organ: str
    tree: DirectoryNode | None = None
    components: list[Component] = field(default_factory=list)
    seeds: list[ComponentSeed] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    max_depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "organ": self.organ,
            "components": [c.to_dict() for c in self.components],
            "seeds": [s.to_dict() for s in self.seeds],
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "max_depth": self.max_depth,
        }


@dataclass
class SystemIndex:
    """Complete system-wide structural index."""

    schema_version: str = "1.0"
    scan_timestamp: str = ""
    scanned_repos: int = 0
    total_components: int = 0
    repos: list[RepoIndex] = field(default_factory=list)
    by_organ: dict[str, int] = field(default_factory=dict)
    by_language: dict[str, int] = field(default_factory=dict)
    by_cohesion: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scan_timestamp": self.scan_timestamp,
            "scanned_repos": self.scanned_repos,
            "total_components": self.total_components,
            "repos": [r.to_dict() for r in self.repos],
            "by_organ": self.by_organ,
            "by_language": self.by_language,
            "by_cohesion": self.by_cohesion,
        }
