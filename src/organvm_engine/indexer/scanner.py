"""Directory tree scanner — walks repos to absolute bottom.

Perception layer of the AMMOI architecture: raw filesystem observation.
Builds a DirectoryNode tree with file metadata at every level.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from organvm_engine.indexer.types import DirectoryNode

# Directories to skip during scanning
_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", ".env", "new_venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "vendor", "third_party", ".tox", ".nox", "site-packages",
    "coverage_html", "htmlcov", ".eggs", ".cache",
})

# File extensions to skip (binary/compiled)
_SKIP_EXTENSIONS = frozenset({".pyc", ".pyo", ".so", ".dylib", ".whl"})

# Build manifest filenames
_BUILD_MANIFESTS = frozenset({
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "Cargo.toml", "go.mod",
    "Makefile", "CMakeLists.txt",
})

# Barrel file names (JS/TS module entry points)
_BARREL_FILES = frozenset({
    "index.ts", "index.js", "index.tsx", "index.jsx",
})


def _count_lines(file_path: Path) -> int:
    """Count lines in a file, returning 0 on any error."""
    with contextlib.suppress(OSError, UnicodeDecodeError):
        return sum(1 for _ in file_path.open())
    return 0


def walk_repo(repo_path: Path, max_depth: int = 20) -> DirectoryNode | None:
    """Walk a repository's directory tree and build a DirectoryNode tree.

    Args:
        repo_path: Absolute path to the repository root.
        max_depth: Maximum recursion depth to prevent runaway trees.

    Returns:
        Root DirectoryNode, or None if repo_path doesn't exist.
    """
    if not repo_path.is_dir():
        return None
    return _walk_dir(repo_path, repo_path, depth=0, max_depth=max_depth)


def _walk_dir(
    dir_path: Path,
    repo_root: Path,
    depth: int,
    max_depth: int,
) -> DirectoryNode:
    """Recursively walk a directory, building the tree."""
    rel_path = str(dir_path.relative_to(repo_root)) if dir_path != repo_root else "."

    node = DirectoryNode(
        path=rel_path,
        name=dir_path.name if dir_path != repo_root else ".",
        depth=depth,
    )

    file_types: dict[str, int] = {}
    file_count = 0
    line_count = 0
    build_manifests: list[str] = []

    try:
        entries = sorted(dir_path.iterdir())
    except (OSError, PermissionError):
        return node

    for entry in entries:
        if entry.is_file():
            ext = entry.suffix.lower()
            if ext in _SKIP_EXTENSIONS:
                continue

            file_count += 1
            file_types[ext] = file_types.get(ext, 0) + 1
            line_count += _count_lines(entry)

            fname = entry.name
            if fname == "__init__.py":
                node.has_init_py = True
            elif fname == "package.json":
                node.has_package_json = True
            elif fname == "go.mod":
                node.has_go_mod = True
            elif fname == "Cargo.toml":
                node.has_cargo_toml = True
            elif fname in _BARREL_FILES:
                node.has_barrel_file = True

            if fname in _BUILD_MANIFESTS:
                build_manifests.append(fname)

        elif entry.is_dir() and depth < max_depth:
            if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                continue
            if entry.name.endswith(".egg-info"):
                continue

            child = _walk_dir(entry, repo_root, depth + 1, max_depth)
            node.children.append(child)

    node.file_count = file_count
    node.line_count = line_count
    node.file_types = file_types
    node.build_manifests = build_manifests

    return node
