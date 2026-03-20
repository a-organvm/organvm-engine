"""Load, save, and query network-map.yaml files across the workspace."""

from __future__ import annotations

from pathlib import Path

import yaml

from organvm_engine.network import NETWORK_MAP_FILENAME
from organvm_engine.network.schema import MirrorEntry, NetworkMap


def read_network_map(path: Path | str) -> NetworkMap:
    """Read and parse a network-map.yaml file.

    Args:
        path: Path to network-map.yaml.

    Returns:
        Parsed NetworkMap object.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    map_path = Path(path)
    with map_path.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"network-map.yaml at {map_path} is not a YAML mapping")

    return NetworkMap.from_dict(data)


def write_network_map(network_map: NetworkMap, path: Path | str) -> None:
    """Write a NetworkMap to a YAML file.

    Args:
        network_map: The network map to serialize.
        path: Destination path.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        yaml.dump(
            network_map.to_dict(),
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


def discover_network_maps(workspace: Path) -> list[tuple[Path, NetworkMap]]:
    """Find all network-map.yaml files across the workspace.

    Walks organ directories looking for the file in each repo root.

    Returns:
        List of (path, NetworkMap) tuples sorted by repo name.
    """
    found: list[tuple[Path, NetworkMap]] = []
    for organ_dir in sorted(workspace.iterdir()):
        if not organ_dir.is_dir() or organ_dir.name.startswith("."):
            continue
        # Check if organ_dir itself has a network map (meta-organvm subprojects)
        for repo_dir in sorted(organ_dir.iterdir()):
            if not repo_dir.is_dir() or repo_dir.name.startswith("."):
                continue
            nmap_path = repo_dir / NETWORK_MAP_FILENAME
            if nmap_path.exists():
                try:
                    nmap = read_network_map(nmap_path)
                    found.append((nmap_path, nmap))
                except (ValueError, yaml.YAMLError, KeyError):
                    continue
    return found


def validate_network_map(data: dict) -> list[str]:
    """Validate network map data structure.

    Returns:
        List of validation error messages (empty = valid).
    """
    errors: list[str] = []

    for field_name in ("repo", "organ"):
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")

    mirrors = data.get("mirrors", {})
    if not isinstance(mirrors, dict):
        errors.append("'mirrors' must be a mapping")
        return errors

    valid_lenses = {"technical", "parallel", "kinship"}
    for lens_name in valid_lenses:
        entries = mirrors.get(lens_name, [])
        if not isinstance(entries, list):
            errors.append(f"mirrors.{lens_name} must be a list")
            continue
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"mirrors.{lens_name}[{i}] must be a mapping")
                continue
            if "project" not in entry:
                errors.append(f"mirrors.{lens_name}[{i}] missing 'project'")
            if "platform" not in entry:
                errors.append(f"mirrors.{lens_name}[{i}] missing 'platform'")
            eng = entry.get("engagement", [])
            if not isinstance(eng, list):
                errors.append(f"mirrors.{lens_name}[{i}].engagement must be a list")

    return errors


def merge_mirrors(
    existing: list[MirrorEntry], discovered: list[MirrorEntry]
) -> list[MirrorEntry]:
    """Merge discovered mirrors into existing list without duplicates.

    Deduplicates by project name. Existing entries take precedence
    (human curation wins over automated discovery).

    Returns:
        Merged list.
    """
    existing_projects = {m.project for m in existing}
    merged = list(existing)
    for entry in discovered:
        if entry.project not in existing_projects:
            merged.append(entry)
            existing_projects.add(entry.project)
    return merged
