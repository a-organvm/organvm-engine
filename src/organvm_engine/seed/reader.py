"""Parse and validate seed.yaml files."""

from pathlib import Path

import yaml


def read_seed(path: Path | str) -> dict:
    """Read and parse a seed.yaml file.

    Args:
        path: Path to seed.yaml.

    Returns:
        Parsed seed dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    seed_path = Path(path)
    with seed_path.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"seed.yaml at {seed_path} is not a YAML mapping")

    return data


def get_produces(seed: dict) -> list[dict]:
    """Extract produces entries from a seed."""
    return seed.get("produces", []) or []


def get_consumes(seed: dict) -> list[dict]:
    """Extract consumes entries from a seed."""
    return seed.get("consumes", []) or []


def get_subscriptions(seed: dict) -> list[dict]:
    """Extract subscription entries from a seed."""
    return seed.get("subscriptions", []) or []


def get_breathing_paths(seed: dict, cadence: str | None = None) -> list[str]:
    """Extract breathing file paths from a seed, optionally filtered by cadence."""
    entries = seed.get("breathing", []) or []
    if cadence:
        entries = [e for e in entries if e.get("cadence") == cadence]
    return [e["path"] for e in entries if "path" in e]


def seed_identity(seed: dict) -> str:
    """Get org/repo identity string from a seed."""
    org = seed.get("org", "unknown")
    repo = seed.get("repo", "unknown")
    return f"{org}/{repo}"
