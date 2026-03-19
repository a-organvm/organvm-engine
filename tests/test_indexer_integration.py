"""Integration tests — verify wiring between indexer, AMMOI, and contextmd.

Tests the end-to-end pipeline:
  indexer → deep-index.json → ammoi.py → contextmd → CLAUDE.md

Each test class targets a specific integration boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_py_package(base: Path, name: str, files: list[str]) -> None:
    """Create a minimal Python package with __init__.py and named files."""
    pkg = base / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(f'"""Package {name}."""\n')
    for f in files:
        (pkg / f).write_text(f"# {f}\npass\n")


def _make_deep_index_json(tmp_path: Path, data: dict) -> Path:
    """Write a deep-index.json and return its path."""
    idx_dir = tmp_path / "data" / "index"
    idx_dir.mkdir(parents=True, exist_ok=True)
    out = idx_dir / "deep-index.json"
    out.write_text(json.dumps(data, indent=2))
    return out


# ---------------------------------------------------------------------------
# 1. Indexer → deep-index.json (serialization integrity)
# ---------------------------------------------------------------------------


class TestIndexerSerializationIntegrity:
    """Verify that indexer output can be written and read back faithfully."""

    def test_system_index_roundtrip(self, tmp_path):
        """run_deep_index → to_dict → JSON → from_dict preserves all fields."""
        from organvm_engine.indexer import index_repo
        from organvm_engine.indexer.types import SystemIndex

        # Create a repo with structure
        repo = tmp_path / "test-repo"
        src = repo / "src" / "mylib"
        _make_py_package(src, "core", ["engine.py", "utils.py"])
        _make_py_package(src, "api", ["routes.py"])

        idx = index_repo(repo, "test-repo", "ORGAN-I")
        system = SystemIndex(
            scan_timestamp="2026-03-14T00:00:00Z",
            scanned_repos=1,
            total_components=len(idx.components),
            repos=[idx],
            by_organ={"ORGAN-I": len(idx.components)},
            by_language={"python": len(idx.components)},
            by_cohesion={"python_package": len(idx.components)},
        )

        # Serialize → file → deserialize
        data = system.to_dict()
        json_str = json.dumps(data, indent=2)
        restored = json.loads(json_str)

        assert restored["scanned_repos"] == 1
        assert restored["total_components"] == len(idx.components)
        assert restored["by_organ"]["ORGAN-I"] == len(idx.components)

        # Components preserve structure
        for repo_data in restored["repos"]:
            for comp in repo_data["components"]:
                assert "path" in comp
                assert "cohesion_type" in comp
                assert "dominant_language" in comp

    def test_seed_to_dict_has_component_flag(self, tmp_path):
        """ComponentSeed.to_dict() sets component=True for identification."""
        from organvm_engine.indexer import index_repo

        repo = tmp_path / "test-repo"
        _make_py_package(repo / "src" / "lib", "core", ["main.py"])

        idx = index_repo(repo, "test-repo", "ORGAN-I")
        for seed in idx.seeds:
            d = seed.to_dict()
            assert d["component"] is True

    def test_fingerprint_changes_on_file_addition(self, tmp_path):
        """Adding a file to a component changes its fingerprint."""
        from organvm_engine.indexer import index_repo

        repo = tmp_path / "test-repo"
        pkg = repo / "src" / "mylib" / "core"
        _make_py_package(repo / "src" / "mylib", "core", ["main.py"])

        idx1 = index_repo(repo, "test-repo", "ORGAN-I")
        fp1 = idx1.seeds[0].fingerprint

        # Add a file
        (pkg / "extra.py").write_text("# extra\n")
        idx2 = index_repo(repo, "test-repo", "ORGAN-I")
        fp2 = idx2.seeds[0].fingerprint

        assert fp1 != fp2

    def test_import_edges_serialized(self, tmp_path):
        """Import edges appear in component serialization."""
        from organvm_engine.indexer import index_repo

        repo = tmp_path / "test-repo"
        src = repo / "src" / "mylib"
        _make_py_package(src, "core", ["engine.py"])
        _make_py_package(src, "api", ["routes.py"])

        # api imports core
        (src / "api" / "routes.py").write_text("from mylib.core import engine\n")

        idx = index_repo(repo, "test-repo", "ORGAN-I")
        data = idx.to_dict()

        api_comp = next(
            c for c in data["components"] if c["path"].endswith("api")
        )
        assert "imports_from" in api_comp
        assert any("core" in imp for imp in api_comp["imports_from"])


# ---------------------------------------------------------------------------
# 2. deep-index.json → AMMOI (the G2 bridge)
# ---------------------------------------------------------------------------


class TestDeepIndexToAMMOI:
    """Verify AMMOI reads structural census from the cached deep-index.json."""

    def test_ammoi_reads_component_count(self, tmp_path):
        """deep-index.json can be loaded and parsed for component counts."""
        index_data = {
            "total_components": 1654,
            "scanned_repos": 59,
            "by_organ": {"ORGAN-I": 385, "META-ORGANVM": 393},
            "repos": [
                {"repo": "test", "max_depth": 5},
                {"repo": "test2", "max_depth": 7},
            ],
        }
        idx_path = _make_deep_index_json(tmp_path, index_data)
        assert idx_path.is_file()

        idx = json.loads(idx_path.read_text())
        assert idx["total_components"] == 1654
        assert idx["by_organ"]["ORGAN-I"] == 385

        # Verify max_depth extraction logic
        max_depth = max(r.get("max_depth", 0) for r in idx["repos"])
        assert max_depth == 7

    def test_ammoi_degrades_without_index(self):
        """AMMOI defaults to 0 components when deep-index.json is missing."""
        from organvm_engine.pulse.ammoi import AMMOI

        a = AMMOI()
        assert a.total_components == 0

    def test_compressed_text_includes_component_count(self):
        """Compressed text uses 'c' suffix for components."""
        from organvm_engine.pulse.ammoi import AMMOI, _build_compressed_text

        a = AMMOI(
            system_density=0.5,
            total_entities=113,
            total_components=1654,
            active_edges=23,
        )
        text = _build_compressed_text(a)
        assert "1654c" in text
        assert "113r" in text

    def test_compressed_text_falls_back_to_modules(self):
        """Without components, compressed text shows module count."""
        from organvm_engine.pulse.ammoi import AMMOI, _build_compressed_text

        a = AMMOI(
            system_density=0.5,
            total_entities=113,
            total_modules=58,
            total_components=0,
        )
        text = _build_compressed_text(a)
        assert "58m" in text
        assert "c" not in text.split("[")[0]  # no 'c' in the scale section

    def test_organ_density_includes_component_count(self):
        """OrganDensity carries per-organ component count."""
        from organvm_engine.pulse.ammoi import OrganDensity

        od = OrganDensity(
            organ_id="META-ORGANVM",
            organ_name="Meta",
            repo_count=11,
            component_count=393,
        )
        d = od.to_dict()
        assert d["component_count"] == 393

    def test_ammoi_to_dict_includes_total_components(self):
        """AMMOI.to_dict() includes total_components field."""
        from organvm_engine.pulse.ammoi import AMMOI

        a = AMMOI(total_components=1654)
        d = a.to_dict()
        assert d["total_components"] == 1654

    def test_ammoi_from_dict_restores_total_components(self):
        """AMMOI.from_dict() correctly restores total_components."""
        from organvm_engine.pulse.ammoi import AMMOI

        a = AMMOI(total_components=1654, hierarchy_depth=5)
        restored = AMMOI.from_dict(a.to_dict())
        assert restored.total_components == 1654
        assert restored.hierarchy_depth == 5

    def test_ammoi_from_dict_missing_components_defaults_zero(self):
        """Old AMMOI snapshots without total_components load cleanly."""
        from organvm_engine.pulse.ammoi import AMMOI

        old_data = {"timestamp": "2026-03-01T00:00:00Z", "system_density": 0.4}
        restored = AMMOI.from_dict(old_data)
        assert restored.total_components == 0


# ---------------------------------------------------------------------------
# 3. AMMOI → contextmd (the G3 bridge)
# ---------------------------------------------------------------------------


class TestAMMOIToContextmd:
    """Verify the AMMOI density section gets injected into context files."""

    def test_ammoi_section_template_has_scale_line(self):
        """Template contains {scale_line} placeholder."""
        from organvm_engine.contextmd.templates import AMMOI_SECTION

        assert "{scale_line}" in AMMOI_SECTION

    def test_build_ammoi_context_includes_structure(self, monkeypatch):
        """_build_ammoi_context() produces a scale line with component count."""
        from organvm_engine.pulse.ammoi import AMMOI, OrganDensity

        fake_ammoi = AMMOI(
            timestamp="2026-03-14T00:00:00Z",
            system_density=0.57,
            total_entities=113,
            total_components=1654,
            hierarchy_depth=5,
            active_edges=23,
            tension_count=2,
            cluster_count=4,
            event_frequency_24h=100,
            inference_score=0.99,
            organs={
                "ORGAN-I": OrganDensity(
                    organ_id="ORGAN-I",
                    organ_name="Theoria",
                    density=0.5,
                ),
            },
        )

        # Inject into the cache
        monkeypatch.setattr(
            "organvm_engine.contextmd.generator._ammoi_cache",
            {"ammoi": fake_ammoi},
        )

        from organvm_engine.contextmd.generator import _build_ammoi_context

        result = _build_ammoi_context()

        assert "1654 components" in result
        assert "113 repos" in result
        assert "depth 5" in result
        assert "57%" in result
        assert "23" in result

    def test_build_ammoi_context_without_components(self, monkeypatch):
        """Scale line omits components when total_components is 0."""
        from organvm_engine.pulse.ammoi import AMMOI

        fake_ammoi = AMMOI(
            timestamp="2026-03-14T00:00:00Z",
            system_density=0.5,
            total_entities=113,
            total_components=0,
            active_edges=10,
        )

        monkeypatch.setattr(
            "organvm_engine.contextmd.generator._ammoi_cache",
            {"ammoi": fake_ammoi},
        )

        from organvm_engine.contextmd.generator import _build_ammoi_context

        result = _build_ammoi_context()

        assert "113 repos" in result
        assert "components" not in result

    def test_build_ammoi_context_empty_cache(self, monkeypatch):
        """Returns empty string when no AMMOI is cached."""
        monkeypatch.setattr(
            "organvm_engine.contextmd.generator._ammoi_cache",
            {"ammoi": None},
        )

        from organvm_engine.contextmd.generator import _build_ammoi_context

        result = _build_ammoi_context()
        assert result == ""


# ---------------------------------------------------------------------------
# 4. MCP tool wiring
# ---------------------------------------------------------------------------


class TestMCPIndexerTools:
    """Verify MCP indexer tools are registered and dispatchable."""

    def test_index_tools_in_tool_list(self):
        """All indexer + gap tools appear in the TOOLS list."""
        from organvm_mcp.server import TOOLS

        names = {t.name for t in TOOLS}
        assert "organvm_index_scan" in names
        assert "organvm_index_show" in names
        assert "organvm_index_bridge" in names
        assert "organvm_query_relations" in names
        assert "organvm_entity_memory" in names

    def test_index_tools_in_dispatch(self):
        """All indexer + gap tools have dispatch entries."""
        from organvm_mcp.server import _DISPATCH

        assert "organvm_index_scan" in _DISPATCH
        assert "organvm_index_show" in _DISPATCH
        assert "organvm_index_bridge" in _DISPATCH
        assert "organvm_query_relations" in _DISPATCH
        assert "organvm_entity_memory" in _DISPATCH

    def test_index_show_schema_requires_repo(self):
        """organvm_index_show requires the 'repo' parameter."""
        from organvm_mcp.server import TOOLS

        show_tool = next(t for t in TOOLS if t.name == "organvm_index_show")
        assert "repo" in show_tool.inputSchema.get("required", [])

    def test_index_scan_schema_optional_filters(self):
        """organvm_index_scan has optional organ and repo filters."""
        from organvm_mcp.server import TOOLS

        scan_tool = next(t for t in TOOLS if t.name == "organvm_index_scan")
        props = scan_tool.inputSchema.get("properties", {})
        assert "organ" in props
        assert "repo" in props
        assert "required" not in scan_tool.inputSchema


# ---------------------------------------------------------------------------
# 5. CLI wiring
# ---------------------------------------------------------------------------


class TestCLIIndexerWiring:
    """Verify CLI commands are registered and dispatchable."""

    def test_index_subcommands_parseable(self):
        """organvm index scan/show/stats/bridge parse without error."""
        from organvm_engine.cli import build_parser

        parser = build_parser()

        # scan
        args = parser.parse_args(["index", "scan", "--json"])
        assert args.command == "index"
        assert args.subcommand == "scan"
        assert args.json is True

        # show
        args = parser.parse_args(["index", "show", "my-repo"])
        assert args.command == "index"
        assert args.subcommand == "show"
        assert args.repo == "my-repo"

        # stats
        args = parser.parse_args(["index", "stats"])
        assert args.command == "index"
        assert args.subcommand == "stats"

        # bridge
        args = parser.parse_args(["index", "bridge", "--repo", "my-repo", "--json"])
        assert args.command == "index"
        assert args.subcommand == "bridge"
        assert args.repo == "my-repo"
        assert args.json is True

    def test_pulse_relation_and_memory_subcommands(self):
        """organvm pulse relations/entity-memory parse without error."""
        from organvm_engine.cli import build_parser

        parser = build_parser()

        # relations
        args = parser.parse_args(["pulse", "relations", "my-entity", "--json"])
        assert args.command == "pulse"
        assert args.subcommand == "relations"
        assert args.entity == "my-entity"
        assert args.json is True

        # entity-memory
        args = parser.parse_args(
            ["pulse", "entity-memory", "my-entity", "--limit", "10", "--no-pulse"],
        )
        assert args.command == "pulse"
        assert args.subcommand == "entity-memory"
        assert args.entity == "my-entity"
        assert args.limit == 10
        assert args.no_pulse is True

    def test_index_stats_reads_cached_json(self, tmp_path, monkeypatch):
        """cmd_index_stats reads from corpus data/index/deep-index.json."""
        import argparse

        from organvm_engine.cli.indexer import cmd_index_stats

        # Create cached index
        index_data = {
            "scanned_repos": 59,
            "total_components": 1654,
            "scan_timestamp": "2026-03-14T00:00:00Z",
            "by_organ": {"ORGAN-I": 385},
            "by_cohesion": {"python_package": 214},
            "by_language": {"python": 247},
            "repos": [],
        }
        _make_deep_index_json(tmp_path, index_data)

        # corpus_dir is imported locally inside cmd_index_stats,
        # so we patch the paths module that it imports from
        monkeypatch.setattr(
            "organvm_engine.paths.corpus_dir",
            lambda: tmp_path,
        )

        args = argparse.Namespace(registry=None, workspace=None)
        result = cmd_index_stats(args)
        assert result == 0


# ---------------------------------------------------------------------------
# 6. End-to-end: indexer → JSON → AMMOI → compressed text
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    """Full pipeline: scan a repo → write JSON → read into AMMOI → verify."""

    def test_full_pipeline(self, tmp_path, monkeypatch):
        """Indexer output flows through AMMOI to produce compressed text."""
        from organvm_engine.indexer import index_repo
        from organvm_engine.indexer.types import SystemIndex
        from organvm_engine.pulse.ammoi import AMMOI, OrganDensity, _build_compressed_text

        # Create a repo with known structure
        repo = tmp_path / "workspace" / "meta-organvm" / "test-engine"
        for pkg_name in ["core", "api", "utils"]:
            _make_py_package(repo / "src" / "mylib", pkg_name, ["main.py"])

        # Index it
        idx = index_repo(repo, "test-engine", "META-ORGANVM")
        assert len(idx.components) == 3

        # Build system index
        system = SystemIndex(
            scan_timestamp="2026-03-14T00:00:00Z",
            scanned_repos=1,
            total_components=3,
            repos=[idx],
            by_organ={"META-ORGANVM": 3},
            by_language={"python": 3},
            by_cohesion={"python_package": 3},
        )

        # Write to JSON
        out_path = _make_deep_index_json(tmp_path / "corpus", system.to_dict())
        assert out_path.is_file()

        # Read back and verify
        restored = json.loads(out_path.read_text())
        assert restored["total_components"] == 3
        assert restored["by_organ"]["META-ORGANVM"] == 3

        # Feed into AMMOI
        ammoi = AMMOI(
            system_density=0.5,
            total_entities=1,
            total_components=restored["total_components"],
            hierarchy_depth=max(
                r.get("max_depth", 0) for r in restored["repos"]
            ),
            organs={
                "META-ORGANVM": OrganDensity(
                    organ_id="META-ORGANVM",
                    organ_name="Meta",
                    component_count=restored["by_organ"]["META-ORGANVM"],
                ),
            },
        )

        # Verify compressed text carries the data
        text = _build_compressed_text(ammoi)
        assert "3c" in text  # 3 components
        assert "1r" in text  # 1 repo/entity
