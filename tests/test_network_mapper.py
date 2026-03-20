"""Tests for network/mapper.py — read/write/discover/validate/merge operations.

Focused on data roundtrip correctness, edge cases, and workspace discovery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from organvm_engine.network import NETWORK_MAP_FILENAME
from organvm_engine.network.schema import MirrorEntry, NetworkMap
from organvm_engine.network.mapper import (
    discover_network_maps,
    merge_mirrors,
    read_network_map,
    validate_network_map,
    write_network_map,
)


# ─── Helpers ──────────────────────────────────────────────────────────────


def _mirror(project: str = "org/proj", **kwargs) -> MirrorEntry:
    return MirrorEntry(
        project=project,
        platform=kwargs.get("platform", "github"),
        relevance=kwargs.get("relevance", "test dep"),
        engagement=kwargs.get("engagement", []),
        url=kwargs.get("url"),
        tags=kwargs.get("tags", []),
        notes=kwargs.get("notes"),
    )


def _netmap(
    repo: str = "engine",
    organ: str = "META",
    tech: int = 0,
    par: int = 0,
    kin: int = 0,
) -> NetworkMap:
    return NetworkMap(
        schema_version="1.0",
        repo=repo,
        organ=organ,
        technical=[_mirror(f"tech/{i}") for i in range(tech)],
        parallel=[_mirror(f"par/{i}") for i in range(par)],
        kinship=[_mirror(f"kin/{i}", platform="community") for i in range(kin)],
    )


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False)


# ─── read_network_map / write_network_map roundtrip ───────────────────────


class TestReadWriteRoundtrip:
    def test_full_roundtrip_preserves_all_fields(self, tmp_path: Path):
        """Write a NetworkMap, read it back, verify every field survives."""
        nmap = NetworkMap(
            schema_version="1.0",
            repo="my-repo",
            organ="ORGAN-I",
            technical=[_mirror("astral-sh/ruff", relevance="linter", tags=["python"])],
            parallel=[_mirror("pallets/flask", relevance="web framework")],
            kinship=[_mirror("creative-coding-community", platform="community",
                             relevance="values alignment")],
            ledger="~/.organvm/network/ledger.jsonl",
            last_scanned="2026-03-20T00:00:00",
        )
        out = tmp_path / "network-map.yaml"
        write_network_map(nmap, out)
        loaded = read_network_map(out)

        assert loaded.schema_version == "1.0"
        assert loaded.repo == "my-repo"
        assert loaded.organ == "ORGAN-I"
        assert len(loaded.technical) == 1
        assert loaded.technical[0].project == "astral-sh/ruff"
        assert loaded.technical[0].tags == ["python"]
        assert len(loaded.parallel) == 1
        assert len(loaded.kinship) == 1
        assert loaded.kinship[0].platform == "community"
        assert loaded.last_scanned == "2026-03-20T00:00:00"

    def test_roundtrip_empty_mirrors(self, tmp_path: Path):
        """A map with zero mirrors survives roundtrip."""
        nmap = _netmap(tech=0, par=0, kin=0)
        out = tmp_path / "network-map.yaml"
        write_network_map(nmap, out)
        loaded = read_network_map(out)
        assert loaded.mirror_count == 0

    def test_write_creates_nested_parents(self, tmp_path: Path):
        """write_network_map creates intermediate directories."""
        out = tmp_path / "a" / "b" / "c" / "network-map.yaml"
        write_network_map(_netmap(tech=1), out)
        assert out.exists()
        loaded = read_network_map(out)
        assert loaded.mirror_count == 1

    def test_read_nonexistent_raises(self, tmp_path: Path):
        """Reading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            read_network_map(tmp_path / "no-such-file.yaml")

    def test_read_non_mapping_raises_valueerror(self, tmp_path: Path):
        """A YAML file that is a list (not dict) raises ValueError."""
        bad = tmp_path / "network-map.yaml"
        bad.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="not a YAML mapping"):
            read_network_map(bad)

    def test_read_malformed_yaml_raises(self, tmp_path: Path):
        """Malformed YAML raises yaml.YAMLError."""
        bad = tmp_path / "network-map.yaml"
        bad.write_text("key: [broken: {no_end")
        with pytest.raises(yaml.YAMLError):
            read_network_map(bad)


# ─── discover_network_maps ────────────────────────────────────────────────


class TestDiscoverNetworkMaps:
    def test_discovers_maps_in_workspace_structure(self, tmp_path: Path):
        """Finds network-map.yaml files two levels deep (organ/repo/)."""
        for name in ("repo-a", "repo-b"):
            repo = tmp_path / "organ-x" / name
            repo.mkdir(parents=True)
            write_network_map(_netmap(repo=name, organ="X"), repo / NETWORK_MAP_FILENAME)

        found = discover_network_maps(tmp_path)
        assert len(found) == 2
        repos = {nmap.repo for _, nmap in found}
        assert repos == {"repo-a", "repo-b"}

    def test_skips_dotdirs(self, tmp_path: Path):
        """Hidden directories (starting with .) are skipped."""
        hidden = tmp_path / ".hidden-organ" / "repo"
        hidden.mkdir(parents=True)
        write_network_map(_netmap(repo="hidden"), hidden / NETWORK_MAP_FILENAME)

        visible = tmp_path / "organ-x" / "repo-a"
        visible.mkdir(parents=True)
        write_network_map(_netmap(repo="visible"), visible / NETWORK_MAP_FILENAME)

        found = discover_network_maps(tmp_path)
        assert len(found) == 1
        assert found[0][1].repo == "visible"

    def test_skips_malformed_files(self, tmp_path: Path):
        """Malformed YAML files are silently skipped."""
        repo = tmp_path / "organ" / "bad-repo"
        repo.mkdir(parents=True)
        (repo / NETWORK_MAP_FILENAME).write_text("- not\n- a\n- map\n")

        good = tmp_path / "organ" / "good-repo"
        good.mkdir(parents=True)
        write_network_map(_netmap(repo="good"), good / NETWORK_MAP_FILENAME)

        found = discover_network_maps(tmp_path)
        assert len(found) == 1
        assert found[0][1].repo == "good"

    def test_empty_workspace_returns_empty(self, tmp_path: Path):
        """An empty workspace yields no results."""
        assert discover_network_maps(tmp_path) == []


# ─── validate_network_map ─────────────────────────────────────────────────


class TestValidateNetworkMap:
    def test_valid_complete_data(self):
        """Fully valid data produces zero errors."""
        data = {
            "repo": "my-repo",
            "organ": "META",
            "mirrors": {
                "technical": [{"project": "x/y", "platform": "github", "engagement": []}],
                "parallel": [],
                "kinship": [],
            },
        }
        assert validate_network_map(data) == []

    def test_missing_repo(self):
        errors = validate_network_map({"organ": "META"})
        assert any("repo" in e for e in errors)

    def test_missing_organ(self):
        errors = validate_network_map({"repo": "x"})
        assert any("organ" in e for e in errors)

    def test_mirrors_not_a_mapping(self):
        errors = validate_network_map({"repo": "x", "organ": "M", "mirrors": "string"})
        assert any("mapping" in e for e in errors)

    def test_entry_missing_project_and_platform(self):
        data = {
            "repo": "x", "organ": "M",
            "mirrors": {"technical": [{"engagement": []}], "parallel": [], "kinship": []},
        }
        errors = validate_network_map(data)
        assert any("project" in e for e in errors)
        assert any("platform" in e for e in errors)

    def test_entry_bad_engagement_type(self):
        data = {
            "repo": "x", "organ": "M",
            "mirrors": {
                "technical": [{"project": "p", "platform": "g", "engagement": "not-a-list"}],
                "parallel": [],
                "kinship": [],
            },
        }
        errors = validate_network_map(data)
        assert any("engagement" in e for e in errors)

    def test_non_dict_entry(self):
        data = {
            "repo": "x", "organ": "M",
            "mirrors": {"technical": ["just-a-string"], "parallel": [], "kinship": []},
        }
        errors = validate_network_map(data)
        assert any("mapping" in e for e in errors)

    def test_no_mirrors_key_is_ok(self):
        """Missing mirrors section is fine — no mirror-specific errors."""
        errors = validate_network_map({"repo": "x", "organ": "M"})
        assert errors == []


# ─── merge_mirrors ────────────────────────────────────────────────────────


class TestMergeMirrors:
    def test_merge_adds_new_entries(self):
        existing = [_mirror("a/1")]
        discovered = [_mirror("b/2"), _mirror("c/3")]
        merged = merge_mirrors(existing, discovered)
        assert len(merged) == 3

    def test_dedup_by_project_name(self):
        """Duplicate project names are not added."""
        existing = [_mirror("shared/proj")]
        discovered = [_mirror("shared/proj")]
        merged = merge_mirrors(existing, discovered)
        assert len(merged) == 1

    def test_existing_takes_precedence(self):
        """When a duplicate exists, the existing entry wins."""
        existing = [MirrorEntry(
            project="shared/proj", platform="github",
            relevance="Human curated", engagement=["contribution"],
        )]
        discovered = [MirrorEntry(
            project="shared/proj", platform="github",
            relevance="Auto-discovered", engagement=["watch"],
        )]
        merged = merge_mirrors(existing, discovered)
        assert len(merged) == 1
        assert merged[0].relevance == "Human curated"

    def test_empty_existing(self):
        """Merging into an empty list takes all discovered."""
        discovered = [_mirror("a/1"), _mirror("b/2")]
        merged = merge_mirrors([], discovered)
        assert len(merged) == 2

    def test_empty_discovered(self):
        """Discovering nothing leaves existing unchanged."""
        existing = [_mirror("a/1")]
        merged = merge_mirrors(existing, [])
        assert len(merged) == 1

    def test_both_empty(self):
        assert merge_mirrors([], []) == []
