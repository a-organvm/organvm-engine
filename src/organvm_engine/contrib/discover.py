"""Discover contribution repos across the workspace.

Contribution repos are identified by:
1. Directory name matching ``contrib--*`` pattern
2. seed.yaml with ``tier: contrib`` field
3. seed.yaml with ``upstream:`` section declaring target repo/PR
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from organvm_engine.paths import workspace_root


@dataclass
class ContribRepo:
    """A contribution tracking repository."""

    name: str
    path: Path
    target_repo: str
    target_pr: int | None = None
    target_issue: int | None = None
    fork: str | None = None
    language: str | None = None
    organ: str = "IV"
    promotion_status: str = "LOCAL"
    description: str = ""
    raw_seed: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def target_owner_repo(self) -> str:
        """Return owner/repo format (e.g., 'grafana/k6')."""
        return self.target_repo

    @property
    def pr_url(self) -> str | None:
        """Construct GitHub PR URL if PR number is known."""
        if self.target_pr is None:
            return None
        return f"https://github.com/{self.target_repo}/pull/{self.target_pr}"


def discover_contrib_repos(
    workspace: Path | str | None = None,
) -> list[ContribRepo]:
    """Find all contribution repos in the workspace.

    Scans all directories matching ``contrib--*`` pattern across all organ
    directories. Parses their seed.yaml for upstream target information.

    Args:
        workspace: Root workspace directory. Defaults to ORGANVM_WORKSPACE_DIR.

    Returns:
        List of ContribRepo objects sorted by name.
    """
    ws = Path(workspace) if workspace else workspace_root()
    repos: list[ContribRepo] = []

    # Scan all directories for contrib repos
    for org_dir in ws.iterdir():
        if not org_dir.is_dir():
            continue
        for repo_dir in org_dir.iterdir():
            if not repo_dir.is_dir():
                continue
            if not repo_dir.name.startswith("contrib--"):
                continue
            seed_path = repo_dir / "seed.yaml"
            if not seed_path.exists():
                continue
            repo = _parse_contrib_seed(seed_path, repo_dir)
            if repo is not None:
                repos.append(repo)

    return sorted(repos, key=lambda r: r.name)


def _parse_contrib_seed(seed_path: Path, repo_dir: Path) -> ContribRepo | None:
    """Parse a seed.yaml file into a ContribRepo."""
    try:
        data = yaml.safe_load(seed_path.read_text())
    except (yaml.YAMLError, OSError):
        return None

    if not isinstance(data, dict):
        return None

    upstream = data.get("upstream", {})
    if not isinstance(upstream, dict):
        upstream = {}

    target_repo = upstream.get("repo", "")
    if not target_repo:
        # Try to infer from name: contrib--owner-repo
        parts = repo_dir.name.removeprefix("contrib--").split("-", 1)
        if len(parts) == 2:
            target_repo = f"{parts[0]}/{parts[1]}"

    return ContribRepo(
        name=data.get("name", repo_dir.name),
        path=repo_dir,
        target_repo=target_repo,
        target_pr=upstream.get("pr"),
        target_issue=upstream.get("issue"),
        fork=upstream.get("fork"),
        language=upstream.get("language"),
        organ=data.get("organ", "IV"),
        promotion_status=data.get("promotion_status", "LOCAL"),
        description=data.get("description", ""),
        raw_seed=data,
    )
