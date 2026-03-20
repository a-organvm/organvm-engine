"""Automated stack analysis for technical mirror discovery.

Scans dependency files (pyproject.toml, package.json, go.mod, Cargo.toml)
and extracts the external projects that a repo depends on. These become
technical mirror candidates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from organvm_engine.network.schema import MirrorEntry

# Well-known package → GitHub repo mappings
# Expanded by research; this is the seed set
KNOWN_REPOS: dict[str, str] = {
    # Python
    "fastapi": "tiangolo/fastapi",
    "uvicorn": "encode/uvicorn",
    "pydantic": "pydantic/pydantic",
    "pytest": "pytest-dev/pytest",
    "ruff": "astral-sh/ruff",
    "click": "pallets/click",
    "rich": "Textualize/rich",
    "httpx": "encode/httpx",
    "jinja2": "pallets/jinja",
    "pyyaml": "yaml/pyyaml",
    "starlette": "encode/starlette",
    "sqlalchemy": "sqlalchemy/sqlalchemy",
    "alembic": "sqlalchemy/alembic",
    "celery": "celery/celery",
    "redis": "redis/redis-py",
    "boto3": "boto/boto3",
    "requests": "psf/requests",
    "aiohttp": "aio-libs/aiohttp",
    "numpy": "numpy/numpy",
    "pandas": "pandas-dev/pandas",
    "pillow": "python-pillow/Pillow",
    "pyright": "microsoft/pyright",
    # JavaScript/TypeScript
    "react": "facebook/react",
    "next": "vercel/next.js",
    "tailwindcss": "tailwindlabs/tailwindcss",
    "typescript": "microsoft/TypeScript",
    "vite": "vitejs/vite",
    "vitest": "vitest-dev/vitest",
    "eslint": "eslint/eslint",
    "prettier": "prettier/prettier",
    "astro": "withastro/astro",
    "htmx.org": "bigskysoftware/htmx",
    # Go
    "github.com/gorilla/mux": "gorilla/mux",
    "github.com/gin-gonic/gin": "gin-gonic/gin",
    # Rust
    "tokio": "tokio-rs/tokio",
    "serde": "serde-rs/serde",
    "clap": "clap-rs/clap",
}


def scan_pyproject(repo_path: Path) -> list[MirrorEntry]:
    """Extract dependencies from pyproject.toml.

    Parses [project.dependencies] and [project.optional-dependencies]
    sections. Maps known packages to their GitHub repos.
    """
    toml_path = repo_path / "pyproject.toml"
    if not toml_path.exists():
        return []

    content = toml_path.read_text()
    mirrors: list[MirrorEntry] = []
    seen: set[str] = set()

    # Extract dependency names from dependencies and optional-dependencies
    # Simple regex approach — handles most pyproject.toml formats
    dep_pattern = re.compile(r'^\s*"?([a-zA-Z0-9_-]+)', re.MULTILINE)

    in_deps = False
    in_optional = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[project.dependencies]" or stripped.startswith("dependencies = ["):
            in_deps = True
            in_optional = False
            continue
        if stripped.startswith("[project.optional-dependencies"):
            in_optional = True
            in_deps = False
            continue
        if stripped.startswith("[") and not stripped.startswith("[project.optional"):
            in_deps = False
            in_optional = False
            continue

        if in_deps or in_optional:
            match = dep_pattern.match(stripped.strip('"').strip("'"))
            if match:
                raw_name = match.group(1).lower()
                if raw_name in seen:
                    continue
                seen.add(raw_name)

                # Check known repos
                github_repo = KNOWN_REPOS.get(raw_name)
                if github_repo:
                    mirrors.append(MirrorEntry(
                        project=github_repo,
                        platform="github",
                        relevance=f"Python dependency: {raw_name}",
                        engagement=["watch"],
                        tags=["auto-discovered", "python-dep"],
                    ))

    return mirrors


def scan_package_json(repo_path: Path) -> list[MirrorEntry]:
    """Extract dependencies from package.json."""
    pkg_path = repo_path / "package.json"
    if not pkg_path.exists():
        return []

    try:
        data = json.loads(pkg_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    mirrors: list[MirrorEntry] = []
    seen: set[str] = set()

    for dep_key in ("dependencies", "devDependencies"):
        deps = data.get(dep_key, {})
        if not isinstance(deps, dict):
            continue
        for pkg_name in deps:
            clean = pkg_name.lstrip("@").replace("/", "-").lower()
            if clean in seen:
                continue
            seen.add(clean)

            github_repo = KNOWN_REPOS.get(clean) or KNOWN_REPOS.get(pkg_name)
            if github_repo:
                mirrors.append(MirrorEntry(
                    project=github_repo,
                    platform="github",
                    relevance=f"JS/TS dependency: {pkg_name}",
                    engagement=["watch"],
                    tags=["auto-discovered", "js-dep"],
                ))

    return mirrors


def scan_go_mod(repo_path: Path) -> list[MirrorEntry]:
    """Extract dependencies from go.mod."""
    go_mod = repo_path / "go.mod"
    if not go_mod.exists():
        return []

    content = go_mod.read_text()
    mirrors: list[MirrorEntry] = []
    seen: set[str] = set()

    in_require = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "require (":
            in_require = True
            continue
        if stripped == ")" and in_require:
            in_require = False
            continue
        if stripped.startswith("require ") and "(" not in stripped:
            # Single-line require
            parts = stripped.split()
            if len(parts) >= 2:
                mod_path = parts[1]
                if mod_path.startswith("github.com/"):
                    segments = mod_path.split("/")
                    if len(segments) >= 3:
                        github_repo = f"{segments[1]}/{segments[2]}"
                        if github_repo not in seen:
                            seen.add(github_repo)
                            mirrors.append(MirrorEntry(
                                project=github_repo,
                                platform="github",
                                relevance=f"Go dependency: {mod_path}",
                                engagement=["watch"],
                                tags=["auto-discovered", "go-dep"],
                            ))
            continue

        if in_require:
            parts = stripped.split()
            if len(parts) >= 2:
                mod_path = parts[0]
                if mod_path.startswith("github.com/"):
                    segments = mod_path.split("/")
                    if len(segments) >= 3:
                        github_repo = f"{segments[1]}/{segments[2]}"
                        if github_repo not in seen:
                            seen.add(github_repo)
                            mirrors.append(MirrorEntry(
                                project=github_repo,
                                platform="github",
                                relevance=f"Go dependency: {mod_path}",
                                engagement=["watch"],
                                tags=["auto-discovered", "go-dep"],
                            ))

    return mirrors


def scan_cargo_toml(repo_path: Path) -> list[MirrorEntry]:
    """Extract dependencies from Cargo.toml."""
    cargo_path = repo_path / "Cargo.toml"
    if not cargo_path.exists():
        return []

    content = cargo_path.read_text()
    mirrors: list[MirrorEntry] = []
    seen: set[str] = set()

    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped in ("[dependencies]", "[dev-dependencies]", "[build-dependencies]"):
            in_deps = True
            continue
        if stripped.startswith("[") and "dependencies" not in stripped:
            in_deps = False
            continue

        if in_deps and "=" in stripped:
            crate_name = stripped.split("=")[0].strip().strip('"')
            if crate_name and not crate_name.startswith("#"):
                github_repo = KNOWN_REPOS.get(crate_name)
                if github_repo and github_repo not in seen:
                    seen.add(github_repo)
                    mirrors.append(MirrorEntry(
                        project=github_repo,
                        platform="github",
                        relevance=f"Rust dependency: {crate_name}",
                        engagement=["watch"],
                        tags=["auto-discovered", "rust-dep"],
                    ))

    return mirrors


def scan_repo_dependencies(repo_path: Path) -> list[MirrorEntry]:
    """Scan all dependency files in a repo for technical mirrors.

    Aggregates results from pyproject.toml, package.json, go.mod, Cargo.toml.
    Deduplicates by project name.
    """
    all_mirrors: list[MirrorEntry] = []
    seen_projects: set[str] = set()

    for scanner in (scan_pyproject, scan_package_json, scan_go_mod, scan_cargo_toml):
        for mirror in scanner(repo_path):
            if mirror.project not in seen_projects:
                all_mirrors.append(mirror)
                seen_projects.add(mirror.project)

    return all_mirrors
