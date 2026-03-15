"""Tests for organvm ontologia mutation CLI commands.

Covers relocate, reclassify, merge, and split subcommands.
"""

from __future__ import annotations

import argparse
import json

import pytest
from ontologia.entity.identity import EntityType
from ontologia.events import bus as ontologia_bus
from ontologia.registry.store import RegistryStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_events(tmp_path):
    """Redirect ontologia event bus to tmp_path for test isolation."""
    store_dir = tmp_path / "ontologia-events"
    store_dir.mkdir()
    ontologia_bus.set_events_path(store_dir / "events.jsonl")
    ontologia_bus.clear_subscribers()
    yield
    ontologia_bus.set_events_path(None)
    ontologia_bus.clear_subscribers()


@pytest.fixture
def bootstrapped_store(tmp_path):
    """A temp ontologia store with one organ and three repos, plus a mock open_store."""
    store_dir = tmp_path / "ontologia"
    store_dir.mkdir()
    ontologia_bus.set_events_path(store_dir / "events.jsonl")

    store = RegistryStore(store_dir=store_dir)
    store.load()

    # Create organ entity
    organ = store.create_entity(EntityType.ORGAN, "ORGAN-I", created_by="test")

    # Create three repo entities as children of the organ
    repo_a = store.create_entity(EntityType.REPO, "repo-alpha", created_by="test")
    repo_b = store.create_entity(EntityType.REPO, "repo-beta", created_by="test")
    repo_c = store.create_entity(EntityType.REPO, "repo-gamma", created_by="test")

    # Give repo_a and repo_b a parent edge to organ
    store.add_hierarchy_edge(parent_id=organ.uid, child_id=repo_a.uid)
    store.add_hierarchy_edge(parent_id=organ.uid, child_id=repo_b.uid)
    store.save()

    return store, organ.uid, repo_a.uid, repo_b.uid, repo_c.uid


# ---------------------------------------------------------------------------
# cmd_ontologia_relocate
# ---------------------------------------------------------------------------

class TestCmdOntologiaRelocate:
    def test_relocate_success(self, bootstrapped_store, monkeypatch, capsys):
        """Relocate moves entity to new parent and reports success."""
        from organvm_engine.cli.ontologia import cmd_ontologia_relocate

        store, organ_uid, repo_a_uid, repo_b_uid, repo_c_uid = bootstrapped_store

        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            entity=repo_c_uid,
            new_parent=organ_uid,
            json=False,
        )
        rc = cmd_ontologia_relocate(args)
        assert rc == 0

        out = capsys.readouterr().out
        assert "Relocated" in out
        assert repo_c_uid in out or organ_uid in out

    def test_relocate_success_json(self, bootstrapped_store, monkeypatch, capsys):
        """JSON output includes expected keys."""
        from organvm_engine.cli.ontologia import cmd_ontologia_relocate

        store, organ_uid, repo_a_uid, repo_b_uid, repo_c_uid = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            entity=repo_c_uid,
            new_parent=organ_uid,
            json=True,
        )
        rc = cmd_ontologia_relocate(args)
        assert rc == 0

        data = json.loads(capsys.readouterr().out)
        assert data["operation"] == "relocate"
        assert data["success"] is True
        assert isinstance(data["edges_created"], int)
        assert isinstance(data["edges_closed"], int)

    def test_relocate_entity_not_found(self, bootstrapped_store, monkeypatch, capsys):
        """Returns 1 and prints error when entity UID does not exist."""
        from organvm_engine.cli.ontologia import cmd_ontologia_relocate

        store, organ_uid, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            entity="ent_repo_nonexistent",
            new_parent=organ_uid,
            json=False,
        )
        rc = cmd_ontologia_relocate(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower() or "error" in err.lower()

    def test_relocate_parent_not_found(self, bootstrapped_store, monkeypatch, capsys):
        """Returns 1 when new parent UID does not exist."""
        from organvm_engine.cli.ontologia import cmd_ontologia_relocate

        store, organ_uid, repo_a_uid, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            entity=repo_a_uid,
            new_parent="ent_organ_nonexistent",
            json=False,
        )
        rc = cmd_ontologia_relocate(args)
        assert rc == 1


# ---------------------------------------------------------------------------
# cmd_ontologia_reclassify
# ---------------------------------------------------------------------------

class TestCmdOntologiaReclassify:
    def test_reclassify_success(self, bootstrapped_store, monkeypatch, capsys):
        """Reclassify changes entity type and reports success."""
        from organvm_engine.cli.ontologia import cmd_ontologia_reclassify

        store, organ_uid, repo_a_uid, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            entity=repo_a_uid,
            new_type="module",
            json=False,
        )
        rc = cmd_ontologia_reclassify(args)
        assert rc == 0

        out = capsys.readouterr().out
        assert "Reclassified" in out

    def test_reclassify_success_json(self, bootstrapped_store, monkeypatch, capsys):
        """JSON output has success=True and modified list."""
        from organvm_engine.cli.ontologia import cmd_ontologia_reclassify

        store, organ_uid, repo_a_uid, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            entity=repo_a_uid,
            new_type="module",
            json=True,
        )
        rc = cmd_ontologia_reclassify(args)
        assert rc == 0

        data = json.loads(capsys.readouterr().out)
        assert data["operation"] == "reclassify"
        assert data["success"] is True
        assert repo_a_uid in data["entities_modified"]

    def test_reclassify_invalid_type(self, bootstrapped_store, monkeypatch, capsys):
        """Returns 1 and prints valid types when type value is invalid."""
        from organvm_engine.cli.ontologia import cmd_ontologia_reclassify

        store, organ_uid, repo_a_uid, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            entity=repo_a_uid,
            new_type="bogus_type",
            json=False,
        )
        rc = cmd_ontologia_reclassify(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "Invalid entity type" in err
        assert "bogus_type" in err

    def test_reclassify_entity_not_found(self, bootstrapped_store, monkeypatch, capsys):
        """Returns 1 when entity UID does not exist."""
        from organvm_engine.cli.ontologia import cmd_ontologia_reclassify

        store, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            entity="ent_repo_nonexistent",
            new_type="module",
            json=False,
        )
        rc = cmd_ontologia_reclassify(args)
        assert rc == 1


# ---------------------------------------------------------------------------
# cmd_ontologia_merge
# ---------------------------------------------------------------------------

class TestCmdOntologiaMerge:
    def test_merge_success(self, bootstrapped_store, monkeypatch, capsys):
        """Merge creates successor entity and deprecates sources."""
        from organvm_engine.cli.ontologia import cmd_ontologia_merge

        store, organ_uid, repo_a_uid, repo_b_uid, repo_c_uid = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            sources=[repo_a_uid, repo_b_uid],
            name="repo-unified",
            json=False,
        )
        rc = cmd_ontologia_merge(args)
        assert rc == 0

        out = capsys.readouterr().out
        assert "repo-unified" in out
        assert "Merged" in out

    def test_merge_success_json(self, bootstrapped_store, monkeypatch, capsys):
        """JSON output includes entities_created and lineage_records as int."""
        from organvm_engine.cli.ontologia import cmd_ontologia_merge

        store, organ_uid, repo_a_uid, repo_b_uid, repo_c_uid = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            sources=[repo_a_uid, repo_b_uid],
            name="repo-merged",
            json=True,
        )
        rc = cmd_ontologia_merge(args)
        assert rc == 0

        data = json.loads(capsys.readouterr().out)
        assert data["operation"] == "merge"
        assert data["success"] is True
        assert len(data["entities_created"]) == 1
        assert isinstance(data["lineage_records"], int)
        assert data["lineage_records"] == 2  # one per source
        assert isinstance(data["edges_created"], int)
        assert isinstance(data["edges_closed"], int)

    def test_merge_source_not_found(self, bootstrapped_store, monkeypatch, capsys):
        """Returns 1 when any source UID does not exist."""
        from organvm_engine.cli.ontologia import cmd_ontologia_merge

        store, organ_uid, repo_a_uid, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            sources=[repo_a_uid, "ent_repo_nonexistent"],
            name="should-not-be-created",
            json=False,
        )
        rc = cmd_ontologia_merge(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower() or "error" in err.lower()


# ---------------------------------------------------------------------------
# cmd_ontologia_split
# ---------------------------------------------------------------------------

class TestCmdOntologiaSplit:
    def test_split_success(self, bootstrapped_store, monkeypatch, capsys):
        """Split creates descendant entities from source."""
        from organvm_engine.cli.ontologia import cmd_ontologia_split

        store, organ_uid, repo_a_uid, repo_b_uid, repo_c_uid = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            source=repo_a_uid,
            descendants=["repo-alpha-core", "repo-alpha-utils"],
            deprecate=False,
            json=False,
        )
        rc = cmd_ontologia_split(args)
        assert rc == 0

        out = capsys.readouterr().out
        assert "Split" in out
        assert "2" in out  # two descendants created

    def test_split_success_json(self, bootstrapped_store, monkeypatch, capsys):
        """JSON output has entities_created length matching descendants."""
        from organvm_engine.cli.ontologia import cmd_ontologia_split

        store, organ_uid, repo_a_uid, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            source=repo_a_uid,
            descendants=["repo-alpha-part1", "repo-alpha-part2", "repo-alpha-part3"],
            deprecate=False,
            json=True,
        )
        rc = cmd_ontologia_split(args)
        assert rc == 0

        data = json.loads(capsys.readouterr().out)
        assert data["operation"] == "split"
        assert data["success"] is True
        assert len(data["entities_created"]) == 3
        assert isinstance(data["lineage_records"], int)
        assert data["lineage_records"] == 3
        assert isinstance(data["edges_created"], int)

    def test_split_with_deprecate(self, bootstrapped_store, monkeypatch, capsys):
        """Split with --deprecate modifies the source entity."""
        from organvm_engine.cli.ontologia import cmd_ontologia_split

        store, organ_uid, repo_a_uid, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            source=repo_a_uid,
            descendants=["alpha-new"],
            deprecate=True,
            json=True,
        )
        rc = cmd_ontologia_split(args)
        assert rc == 0

        data = json.loads(capsys.readouterr().out)
        assert data["success"] is True
        # Source should be in entities_modified because it was deprecated
        assert repo_a_uid in data["entities_modified"]

    def test_split_source_not_found(self, bootstrapped_store, monkeypatch, capsys):
        """Returns 1 when source UID does not exist."""
        from organvm_engine.cli.ontologia import cmd_ontologia_split

        store, *_ = bootstrapped_store
        monkeypatch.setattr("organvm_engine.cli.ontologia.open_store", lambda: store)

        args = argparse.Namespace(
            source="ent_repo_nonexistent",
            descendants=["new-child"],
            deprecate=False,
            json=False,
        )
        rc = cmd_ontologia_split(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower() or "error" in err.lower()


# ---------------------------------------------------------------------------
# Parser registration tests
# ---------------------------------------------------------------------------

class TestParserRegistration:
    def test_parser_has_relocate(self):
        """Verify 'relocate' is registered in the CLI parser."""
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["ontologia", "relocate", "ent_repo_abc", "ent_organ_xyz"])
        assert args.command == "ontologia"
        assert args.subcommand == "relocate"
        assert args.entity == "ent_repo_abc"
        assert args.new_parent == "ent_organ_xyz"
        assert args.json is False

    def test_parser_has_reclassify(self):
        """Verify 'reclassify' is registered in the CLI parser."""
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["ontologia", "reclassify", "ent_repo_abc", "module", "--json"])
        assert args.subcommand == "reclassify"
        assert args.entity == "ent_repo_abc"
        assert args.new_type == "module"
        assert args.json is True

    def test_parser_has_merge(self):
        """Verify 'merge' is registered in the CLI parser."""
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "ontologia", "merge",
            "ent_repo_aaa", "ent_repo_bbb",
            "--name", "merged-repo",
        ])
        assert args.subcommand == "merge"
        assert args.sources == ["ent_repo_aaa", "ent_repo_bbb"]
        assert args.name == "merged-repo"

    def test_parser_has_split(self):
        """Verify 'split' is registered in the CLI parser."""
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "ontologia", "split", "ent_repo_abc",
            "--descendants", "child-a", "child-b",
            "--deprecate",
        ])
        assert args.subcommand == "split"
        assert args.source == "ent_repo_abc"
        assert args.descendants == ["child-a", "child-b"]
        assert args.deprecate is True
