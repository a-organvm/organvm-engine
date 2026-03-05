"""Tests for the registry module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from organvm_engine.registry.loader import load_registry, save_registry
from organvm_engine.registry.query import find_repo, all_repos, list_repos, resolve_organ_key
from organvm_engine.registry.validator import validate_registry
from organvm_engine.registry.updater import update_repo


class TestLoader:
    def test_load_returns_dict(self, registry):
        assert isinstance(registry, dict)
        assert registry["version"] == "2.0"

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_registry("/nonexistent/path.json")

    def test_save_to_explicit_path(self, registry, tmp_path):
        out = tmp_path / "out.json"
        save_registry(registry, out)
        reloaded = load_registry(out)
        assert reloaded["version"] == "2.0"

    def test_save_refuses_small_registry_to_production_path(self):
        """Guard against test fixture data overwriting production registry."""
        tiny = {"version": "2.0", "organs": {"ORGAN-I": {"name": "Theory", "repositories": [{"name": "repo-a"}]}}}
        with pytest.raises(ValueError, match="Refusing to write registry with only 1 repos"):
            save_registry(tiny)

    def test_save_allows_small_registry_to_explicit_path(self, tmp_path):
        """Small registries are fine when writing to an explicit non-production path."""
        tiny = {"version": "2.0", "organs": {"ORGAN-I": {"name": "Theory", "repositories": [{"name": "repo-a"}]}}}
        out = tmp_path / "test-registry.json"
        save_registry(tiny, out)
        assert out.exists()


class TestQuery:
    def test_find_repo_exists(self, registry):
        result = find_repo(registry, "recursive-engine")
        assert result is not None
        organ_key, repo = result
        assert organ_key == "ORGAN-I"
        assert repo["name"] == "recursive-engine"

    def test_find_repo_missing(self, registry):
        assert find_repo(registry, "nonexistent") is None

    def test_all_repos_yields_all(self, registry):
        repos = list(all_repos(registry))
        assert len(repos) == 6

    def test_list_repos_by_organ(self, registry):
        results = list_repos(registry, organ="ORGAN-I")
        assert len(results) == 2
        assert all(ok == "ORGAN-I" for ok, _ in results)

    def test_list_repos_by_organ_meta(self, registry):
        """META alias resolves to META-ORGANVM registry key."""
        results = list_repos(registry, organ="META")
        assert len(results) == 2
        assert all(ok == "META-ORGANVM" for ok, _ in results)

    def test_list_repos_by_organ_meta_full_key(self, registry):
        """Full registry key META-ORGANVM also works."""
        results = list_repos(registry, organ="META-ORGANVM")
        assert len(results) == 2

    def test_list_repos_by_organ_shorthand(self, registry):
        """Shorthand 'I' resolves to 'ORGAN-I'."""
        results = list_repos(registry, organ="I")
        assert len(results) == 2
        assert all(ok == "ORGAN-I" for ok, _ in results)

    def test_list_repos_by_tier(self, registry):
        flagships = list_repos(registry, tier="flagship")
        assert len(flagships) == 4

    def test_list_repos_public_only(self, registry):
        public = list_repos(registry, public_only=True)
        assert len(public) == 6  # all are public in fixture

    def test_list_repos_by_promotion_status(self, registry):
        public_process = list_repos(registry, promotion_status="PUBLIC_PROCESS")
        assert len(public_process) == 3
        assert all(r.get("promotion_status") == "PUBLIC_PROCESS" for _, r in public_process)

    def test_list_repos_by_promotion_status_local(self, registry):
        local = list_repos(registry, promotion_status="LOCAL")
        assert len(local) == 3
        assert all(r.get("promotion_status") == "LOCAL" for _, r in local)


class TestResolveOrganKey:
    def test_shorthand_to_full(self):
        assert resolve_organ_key("I") == "ORGAN-I"
        assert resolve_organ_key("VII") == "ORGAN-VII"

    def test_meta_alias(self):
        assert resolve_organ_key("META") == "META-ORGANVM"

    def test_passthrough_full_key(self):
        assert resolve_organ_key("ORGAN-I") == "ORGAN-I"
        assert resolve_organ_key("META-ORGANVM") == "META-ORGANVM"

    def test_unknown_passthrough(self):
        assert resolve_organ_key("UNKNOWN") == "UNKNOWN"


class TestValidator:
    def test_valid_registry_passes(self, registry):
        result = validate_registry(registry)
        assert result.passed
        assert result.total_repos == 6

    def test_missing_field_is_error(self):
        bad = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [{"name": "test"}]
                }
            }
        }
        result = validate_registry(bad)
        assert not result.passed
        assert any("missing required" in e for e in result.errors)

    def test_invalid_status_is_error(self):
        bad = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [{
                        "name": "test",
                        "org": "organvm-i-theoria",
                        "implementation_status": "BOGUS",
                        "public": True,
                        "description": "Test repo",
                    }]
                }
            }
        }
        result = validate_registry(bad)
        assert not result.passed
        assert any("BOGUS" in e for e in result.errors)

    def test_back_edge_detected(self):
        bad = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [{
                        "name": "theory-repo",
                        "org": "organvm-i-theoria",
                        "implementation_status": "ACTIVE",
                        "public": True,
                        "description": "Theory",
                        "dependencies": ["organvm-ii-poiesis/art-repo"],
                    }]
                },
                "ORGAN-II": {
                    "repositories": [{
                        "name": "art-repo",
                        "org": "organvm-ii-poiesis",
                        "implementation_status": "ACTIVE",
                        "public": True,
                        "description": "Art",
                        "dependencies": [],
                    }]
                },
            }
        }
        result = validate_registry(bad)
        assert any("back-edge" in e for e in result.errors)


class TestUpdater:
    def test_update_valid_field(self, registry):
        ok, msg = update_repo(registry, "recursive-engine", "tier", "standard")
        assert ok
        _, repo = find_repo(registry, "recursive-engine")
        assert repo["tier"] == "standard"

    def test_update_invalid_status(self, registry):
        ok, msg = update_repo(registry, "recursive-engine", "implementation_status", "BOGUS")
        assert not ok

    def test_update_missing_repo(self, registry):
        ok, msg = update_repo(registry, "nonexistent", "tier", "standard")
        assert not ok
