"""Tests for organvm_engine.metrics.snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from organvm_engine.metrics.snapshot import build_system_snapshot, write_system_snapshot
from organvm_engine.registry.loader import load_registry

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def minimal_registry():
    return load_registry(FIXTURES / "registry-minimal.json")


@pytest.fixture
def computed():
    """Minimal computed metrics dict."""
    return {
        "total_repos": 6,
        "active_repos": 5,
        "ci_workflows": 1,
        "total_organs": 4,
        "dependency_edges": 2,
    }


class TestBuildSystemSnapshot:
    def test_required_top_level_keys(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        assert "generated_at" in snap
        assert "system" in snap
        assert "organs" in snap
        assert "variables" in snap
        assert "promotion_pipeline" in snap

    def test_generated_at_is_iso_string(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        ts = snap["generated_at"]
        assert isinstance(ts, str)
        assert "T" in ts  # ISO 8601 format

    def test_system_section_counts_from_computed_metrics(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        sys = snap["system"]
        assert sys["total_repos"] == 6
        assert sys["active_repos"] == 5
        assert sys["ci_workflows"] == 1

    def test_system_section_has_density_and_entities(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        sys = snap["system"]
        assert "density" in sys
        assert "entities" in sys
        assert "edges" in sys
        assert isinstance(sys["density"], float)
        assert isinstance(sys["entities"], int)
        assert isinstance(sys["edges"], int)

    def test_ammoi_field_is_string(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        assert isinstance(snap["system"]["ammoi"], str)

    def test_organs_list_has_correct_entries(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        organs = snap["organs"]
        # fixture has 4 organs
        assert len(organs) == 4
        keys = [o["key"] for o in organs]
        assert "ORGAN-I" in keys
        assert "META-ORGANVM" in keys

    def test_organs_sorted_by_key(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        keys = [o["key"] for o in snap["organs"]]
        assert keys == sorted(keys)

    def test_organ_has_repo_count(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        organ_i = next(o for o in snap["organs"] if o["key"] == "ORGAN-I")
        assert organ_i["repo_count"] == 2

    def test_organ_has_repositories_list(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        organ_i = next(o for o in snap["organs"] if o["key"] == "ORGAN-I")
        assert isinstance(organ_i["repositories"], list)
        assert len(organ_i["repositories"]) == 2

    def test_repo_entry_has_required_fields(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        organ_i = next(o for o in snap["organs"] if o["key"] == "ORGAN-I")
        repo = organ_i["repositories"][0]
        assert "name" in repo
        assert "status" in repo
        assert "tier" in repo
        assert "ci" in repo

    def test_repo_ci_field_is_bool(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        organ_i = next(o for o in snap["organs"] if o["key"] == "ORGAN-I")
        # recursive-engine has ci_workflow set
        recursive = next(r for r in organ_i["repositories"] if r["name"] == "recursive-engine")
        assert recursive["ci"] is True
        # ontological-framework has no ci_workflow
        ontological = next(
            r for r in organ_i["repositories"] if r["name"] == "ontological-framework"
        )
        assert ontological["ci"] is False

    def test_organ_flagship_count(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        organ_i = next(o for o in snap["organs"] if o["key"] == "ORGAN-I")
        # recursive-engine is flagship, ontological-framework is standard
        assert organ_i["flagship_count"] == 1
        assert organ_i["standard_count"] == 1
        assert organ_i["infrastructure_count"] == 0

    def test_promotion_pipeline_counts_statuses(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        pipeline = snap["promotion_pipeline"]
        # From fixture: recursive-engine=PUBLIC_PROCESS, ontological-framework=LOCAL,
        # metasystem-master=PUBLIC_PROCESS, product-app=LOCAL,
        # organvm-engine=LOCAL, organvm-corpvs-testamentvm=PUBLIC_PROCESS
        assert pipeline.get("LOCAL", 0) == 3
        assert pipeline.get("PUBLIC_PROCESS", 0) == 3

    def test_promotion_pipeline_sorted_keys(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        keys = list(snap["promotion_pipeline"].keys())
        assert keys == sorted(keys)

    def test_variables_is_dict(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        assert isinstance(snap["variables"], dict)

    def test_omega_section_present(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        assert "omega" in snap
        omega = snap["omega"]
        assert "met" in omega
        assert "total" in omega
        assert omega["total"] == 17

    def test_json_serializable(self, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        # Must not raise
        serialized = json.dumps(snap)
        assert len(serialized) > 0

    def test_empty_registry_returns_empty_organs(self, computed):
        snap = build_system_snapshot({}, computed)
        assert snap["organs"] == []
        assert snap["promotion_pipeline"] == {}

    def test_empty_registry_falls_back_to_len_all_repos(self):
        snap = build_system_snapshot({}, {})
        assert snap["system"]["total_repos"] == 0

    def test_computed_metrics_total_repos_used_when_present(self, minimal_registry):
        computed_override = {"total_repos": 999, "active_repos": 42, "ci_workflows": 7}
        snap = build_system_snapshot(minimal_registry, computed_override)
        assert snap["system"]["total_repos"] == 999
        assert snap["system"]["active_repos"] == 42
        assert snap["system"]["ci_workflows"] == 7

    def test_missing_computed_metrics_defaults_gracefully(self, minimal_registry):
        snap = build_system_snapshot(minimal_registry, {})
        # Falls back to len(all_repos) for total_repos
        assert snap["system"]["total_repos"] == 6
        # Defaults to 0 for missing keys
        assert snap["system"]["active_repos"] == 0
        assert snap["system"]["ci_workflows"] == 0


class TestWriteSystemSnapshot:
    def test_creates_file(self, tmp_path, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        out = tmp_path / "system-snapshot.json"
        write_system_snapshot(snap, out)
        assert out.exists()

    def test_creates_parent_directories(self, tmp_path, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        out = tmp_path / "nested" / "deep" / "system-snapshot.json"
        write_system_snapshot(snap, out)
        assert out.exists()

    def test_output_is_valid_json(self, tmp_path, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        out = tmp_path / "system-snapshot.json"
        write_system_snapshot(snap, out)
        with out.open() as f:
            data = json.load(f)
        assert "generated_at" in data
        assert "system" in data
        assert "organs" in data

    def test_output_ends_with_newline(self, tmp_path, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        out = tmp_path / "system-snapshot.json"
        write_system_snapshot(snap, out)
        content = out.read_text()
        assert content.endswith("\n")

    def test_roundtrip_preserves_data(self, tmp_path, minimal_registry, computed):
        snap = build_system_snapshot(minimal_registry, computed)
        out = tmp_path / "system-snapshot.json"
        write_system_snapshot(snap, out)
        with out.open() as f:
            loaded = json.load(f)
        assert loaded["system"]["total_repos"] == snap["system"]["total_repos"]
        assert len(loaded["organs"]) == len(snap["organs"])
        assert loaded["promotion_pipeline"] == snap["promotion_pipeline"]
