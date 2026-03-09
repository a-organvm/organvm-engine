"""Discover seed.yaml files across the workspace."""

from pathlib import Path

from organvm_engine.organ_config import organ_org_dirs
from organvm_engine.paths import workspace_root

# Known org directories — derived from canonical organ_config
ORGAN_ORGS = organ_org_dirs()

# For backward compatibility with git modules
DEFAULT_WORKSPACE = workspace_root()


def discover_seeds(
    workspace: Path | str | None = None,
    orgs: list[str] | None = None,
) -> list[Path]:
    """Walk the workspace and find all seed.yaml files.

    Structure: ~/Workspace/<org>/<repo>/seed.yaml

    Args:
        workspace: Root workspace directory. Defaults to ~/Workspace.
        orgs: List of org directory names to scan. Defaults to all 8 organs.

    Returns:
        Sorted list of paths to seed.yaml files found.
    """
    ws = Path(workspace) if workspace else workspace_root()
    scan_orgs = orgs or ORGAN_ORGS

    seeds: list[Path] = []
    for org_name in scan_orgs:
        org_dir = ws / org_name
        if not org_dir.is_dir():
            continue
        for repo_dir in sorted(org_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            seed_file = repo_dir / "seed.yaml"
            if seed_file.is_file():
                seeds.append(seed_file)

    return sorted(seeds)
