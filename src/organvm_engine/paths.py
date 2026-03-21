"""Workspace path resolution.

Resolves canonical paths to ORGANVM data sources. Uses environment
variables when available, falls back to conventional defaults.

Environment variables:
    ORGANVM_WORKSPACE_DIR — workspace root (default: ~/Workspace)
    ORGANVM_CORPUS_DIR — corpus repo (default: <workspace>/meta-organvm/organvm-corpvs-testamentvm)
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_WORKSPACE = Path.home() / "Workspace"
_DEFAULT_CORPUS_SUBPATH = "meta-organvm/organvm-corpvs-testamentvm"


@dataclass(frozen=True)
class PathConfig:
    """Explicit workspace/corpus path configuration.

    When unset, values fall back to the environment and conventional defaults.
    """

    workspace_dir: Path | str | None = None
    corpus_root: Path | str | None = None

    def workspace_root(self) -> Path:
        raw = self.workspace_dir
        if raw is not None:
            return _coerce_path(raw)
        return _coerce_path(os.environ.get("ORGANVM_WORKSPACE_DIR", str(_DEFAULT_WORKSPACE)))

    def corpus_dir(self) -> Path:
        raw = self.corpus_root
        if raw is not None:
            return _coerce_path(raw)
        env = os.environ.get("ORGANVM_CORPUS_DIR")
        if env:
            return _coerce_path(env)
        return self.workspace_root() / _DEFAULT_CORPUS_SUBPATH

    def registry_path(self) -> Path:
        return self.corpus_dir() / "registry-v2.json"

    def governance_rules_path(self) -> Path:
        return self.corpus_dir() / "governance-rules.json"

    def registry_dir(self) -> Path:
        """Return the path for per-organ split registry directory."""
        return self.corpus_dir() / "registry"

    def soak_dir(self) -> Path:
        return self.corpus_dir() / "data" / "soak-test"

    def atoms_dir(self) -> Path:
        return self.corpus_dir() / "data" / "atoms"

    def irf_path(self) -> Path:
        """Path to INST-INDEX-RERUM-FACIENDARUM.md."""
        return self.corpus_dir() / "INST-INDEX-RERUM-FACIENDARUM.md"

    def content_dir(self) -> Path:
        """Content pipeline posts directory in praxis-perpetua."""
        return self.corpus_dir().parent / "praxis-perpetua" / "content-pipeline" / "posts"


def _coerce_path(value: Path | str) -> Path:
    return Path(value).expanduser()


def resolve_path_config(config: PathConfig | None = None) -> PathConfig:
    """Return an explicit path configuration object."""
    return config if config is not None else PathConfig()


def workspace_root(config: PathConfig | None = None) -> Path:
    """Return the workspace root directory."""
    return resolve_path_config(config).workspace_root()


def corpus_dir(config: PathConfig | None = None) -> Path:
    """Return the path to organvm-corpvs-testamentvm."""
    return resolve_path_config(config).corpus_dir()


def registry_path(config: PathConfig | None = None) -> Path:
    """Return the path to registry-v2.json."""
    return resolve_path_config(config).registry_path()


def irf_path(config: PathConfig | None = None) -> Path:
    """Return the path to INST-INDEX-RERUM-FACIENDARUM.md."""
    return resolve_path_config(config).irf_path()


def registry_dir(config: PathConfig | None = None) -> Path:
    """Return the path to the per-organ registry directory."""
    return resolve_path_config(config).registry_dir()


def governance_rules_path(config: PathConfig | None = None) -> Path:
    """Return the path to governance-rules.json."""
    return resolve_path_config(config).governance_rules_path()


def soak_dir(config: PathConfig | None = None) -> Path:
    """Return the path to the soak-test data directory."""
    return resolve_path_config(config).soak_dir()


def atoms_dir(config: PathConfig | None = None) -> Path:
    """Return the path to the centralized atoms output directory."""
    return resolve_path_config(config).atoms_dir()


def content_dir(config: PathConfig | None = None) -> Path:
    """Return the path to the content pipeline posts directory."""
    return resolve_path_config(config).content_dir()


def resolve_workspace(
    args: "argparse.Namespace | None" = None,
    config: PathConfig | None = None,
) -> Path | None:
    """Resolve workspace from CLI args, env, or default."""
    if args is not None:
        raw = getattr(args, "workspace", None)
        if raw:
            return _coerce_path(raw).resolve()
    cfg = resolve_path_config(config)
    if cfg.workspace_dir is not None:
        return cfg.workspace_root().resolve()
    env = os.environ.get("ORGANVM_WORKSPACE_DIR")
    if env:
        return _coerce_path(env).resolve()
    default = _DEFAULT_WORKSPACE
    return default if default.is_dir() else None
