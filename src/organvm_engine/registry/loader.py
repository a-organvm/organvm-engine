"""Load and save registry-v2.json."""

import json
from pathlib import Path

from organvm_engine.paths import registry_path as _default_registry_path

# Minimum repo count to accept a registry write.  The production registry
# has 100+ repos; anything dramatically smaller is almost certainly test
# fixture data being written to the real path by accident.
_MIN_REPO_COUNT = 50


def _count_repos(data: dict) -> int:
    """Count total repositories across all organs."""
    total = 0
    for organ in data.get("organs", {}).values():
        if isinstance(organ, dict):
            total += len(organ.get("repositories", []))
    return total


def load_registry(path: Path | str | None = None) -> dict:
    """Load registry-v2.json from disk.

    Args:
        path: Path to registry file. Defaults to the corpus repo location.

    Returns:
        Parsed registry dict.
    """
    registry_path = Path(path) if path else _default_registry_path()
    with registry_path.open() as f:
        return json.load(f)


def save_registry(data: dict, path: Path | str | None = None) -> None:
    """Write registry-v2.json back to disk with consistent formatting.

    Guards against accidental overwrites: if writing to the default
    production path and the data contains far fewer repos than expected,
    raises ValueError instead of silently clobbering the file.

    Args:
        data: Registry dict to write.
        path: Path to write to. Defaults to the corpus repo location.

    Raises:
        ValueError: If the data looks like test fixture data being written
            to the production registry path.
    """
    default_path = _default_registry_path()
    registry_path = Path(path) if path else default_path

    # Guard: only enforce on the default production path
    if path is None or Path(path).resolve() == default_path.resolve():
        repo_count = _count_repos(data)
        if repo_count < _MIN_REPO_COUNT:
            raise ValueError(
                f"Refusing to write registry with only {repo_count} repos "
                f"to production path {registry_path}. This looks like test "
                f"fixture data. Pass an explicit path to override.",
            )

    with registry_path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
