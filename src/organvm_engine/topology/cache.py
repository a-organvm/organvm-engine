"""Topology cache: build, load, and save the capability index.

The cache maps identities to locations. It is built by scanning seed.yaml
files across the workspace, extracting identity and produces/consumes
declarations, and writing a JSON file to $XDG_CACHE_HOME/organvm/topology.json.

The cache is an optimization — the system works without it (via filesystem
scan). When the cache exists, resolution is O(1) dictionary lookup.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from organvm_engine.paths import workspace_root
from organvm_engine.seed.discover import discover_seeds
from organvm_engine.seed.reader import read_seed

# Cache lives in XDG_CACHE_HOME, not in any repo.
_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "organvm"
_CACHE_FILE = _CACHE_DIR / "topology.json"
_CACHE_TTL_SECONDS = 3600  # 1 hour


# ── Aliases: human-friendly names → canonical repo names ──
ALIASES: dict[str, str] = {
    "conductor": "tool-interaction-design",
    "skills": "a-i--skills",
    "corpus": "organvm-corpvs-testamentvm",
    "engine": "organvm-engine",
    "vox": "vox--architectura-gubernatio",
    "dashboard": "system-dashboard",
    "registry": "organvm-corpvs-testamentvm",
    "portfolio": "portfolio",
}


@dataclass
class RepoEntry:
    """A resolved repo in the topology."""

    path: str
    name: str
    org: str
    identity: str  # "org/name"
    organ: str
    tier: str
    produces: list[str] = field(default_factory=list)
    consumes: list[str] = field(default_factory=list)


@dataclass
class TopologyCache:
    """The full topology: all repos, aliases, capability index."""

    version: int = 1
    generated: str = ""
    workspace_root: str = ""
    repos: dict[str, dict] = field(default_factory=dict)  # name → RepoEntry as dict
    aliases: dict[str, str] = field(default_factory=dict)
    producers: dict[str, str] = field(default_factory=dict)  # capability → repo name


def build_topology(workspace: Path | str | None = None) -> TopologyCache:
    """Scan workspace, read all seeds, build the topology cache."""
    ws = Path(workspace) if workspace else workspace_root()

    # Discover all seed.yaml files — uses existing infrastructure
    seeds = discover_seeds(workspace=ws)

    cache = TopologyCache(
        generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        workspace_root=str(ws),
        aliases=dict(ALIASES),
    )

    seen_canonical: set[str] = set()

    for seed_path in seeds:
        try:
            seed = read_seed(seed_path)
        except Exception:
            continue

        repo_dir = seed_path.parent
        # Resolve symlinks to avoid duplicates
        canonical = str(repo_dir.resolve())
        if canonical in seen_canonical:
            continue
        seen_canonical.add(canonical)

        name = seed.get("name") or seed.get("repo") or repo_dir.name
        org = seed.get("org", "")
        identity = f"{org}/{name}" if org else name
        organ = seed.get("organ", "")
        tier = seed.get("tier", "")

        # Extract produces/consumes capability types
        # Seeds may have dicts ({"type": "X"}) or bare strings ("X")
        raw_produces = seed.get("produces", []) or []
        raw_consumes = seed.get("consumes", []) or []
        produces = [
            (p.get("type", "") if isinstance(p, dict) else str(p))
            for p in raw_produces
            if (p.get("type") if isinstance(p, dict) else p)
        ]
        consumes = [
            (c.get("type", "") if isinstance(c, dict) else str(c))
            for c in raw_consumes
            if (c.get("type") if isinstance(c, dict) else c)
        ]

        entry = RepoEntry(
            path=canonical,
            name=name,
            org=org,
            identity=identity,
            organ=str(organ),
            tier=str(tier),
            produces=produces,
            consumes=consumes,
        )
        cache.repos[name] = asdict(entry)

        # Build producers index (capability type → repo name)
        for cap in produces:
            if cap not in cache.producers:
                cache.producers[cap] = name

    return cache


def save_cache(cache: TopologyCache, path: Path | None = None) -> Path:
    """Write topology cache to disk."""
    target = path or _CACHE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(cache), indent=2) + "\n")
    return target


def load_cache(path: Path | None = None, max_age: int = _CACHE_TTL_SECONDS) -> TopologyCache | None:
    """Load topology cache if it exists and is fresh enough."""
    target = path or _CACHE_FILE
    if not target.is_file():
        return None

    age = time.time() - target.stat().st_mtime
    if age > max_age:
        return None

    try:
        data = json.loads(target.read_text())
        return TopologyCache(
            version=data.get("version", 1),
            generated=data.get("generated", ""),
            workspace_root=data.get("workspace_root", ""),
            repos=data.get("repos", {}),
            aliases=data.get("aliases", {}),
            producers=data.get("producers", {}),
        )
    except (json.JSONDecodeError, KeyError):
        return None
