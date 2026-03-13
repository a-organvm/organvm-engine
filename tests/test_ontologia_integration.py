"""Integration tests for ontologia bridge in organvm-engine.

Tests the resolve_entity bridge, CLI ontologia commands, and
event bus forwarding. Uses ontologia directly since it's installed
in the same venv.
"""

from __future__ import annotations

import argparse
import json
from unittest.mock import patch

import pytest
from ontologia.entity.identity import EntityType
from ontologia.events import bus as ontologia_bus
from ontologia.registry.store import RegistryStore

from organvm_engine.registry.query import resolve_entity

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_ontologia(tmp_path, monkeypatch):
    """Redirect ontologia store and events to tmp_path."""
    store_dir = tmp_path / "ontologia"
    store_dir.mkdir()
    ontologia_bus.set_events_path(store_dir / "events.jsonl")
    ontologia_bus.clear_subscribers()
    # Patch open_store to use tmp dir
    monkeypatch.setattr(
        "ontologia.registry.store._default_store_dir",
        lambda: store_dir,
    )
    yield
    ontologia_bus.set_events_path(None)
    ontologia_bus.clear_subscribers()


@pytest.fixture
def ont_store(tmp_path) -> RegistryStore:
    """Create a populated ontologia store for testing."""
    store_dir = tmp_path / "ontologia"
    store_dir.mkdir(exist_ok=True)
    ontologia_bus.set_events_path(store_dir / "events.jsonl")

    store = RegistryStore(store_dir=store_dir)
    store.load()

    # Create test entities
    store.create_entity(EntityType.ORGAN, "ORGAN-I", created_by="test")
    store.create_entity(EntityType.REPO, "recursive-engine--generative-entity", created_by="test")
    store.create_entity(EntityType.REPO, "organvm-engine", created_by="test")
    store.save()

    return store


@pytest.fixture
def mini_registry():
    """Minimal registry dict for fallback testing."""
    return {
        "organs": {
            "ORGAN-I": {
                "repositories": [
                    {"name": "recursive-engine--generative-entity", "tier": "flagship"},
                ],
            },
            "META-ORGANVM": {
                "repositories": [
                    {"name": "organvm-engine", "tier": "flagship"},
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# resolve_entity bridge
# ---------------------------------------------------------------------------

class TestResolveEntity:
    def test_resolve_via_ontologia(self, ont_store, mini_registry):
        """When ontologia has the entity, it should resolve with UID."""
        # Patch open_store to return our test store
        with patch("ontologia.registry.store.open_store", return_value=ont_store):
            result = resolve_entity("organvm-engine", registry=mini_registry)

        assert result is not None
        assert result["source"] == "ontologia"
        assert result["uid"] is not None
        assert result["uid"].startswith("ent_repo_")
        assert result["display_name"] == "organvm-engine"
        assert result["matched_by"] in ("primary_name", "slug")

    def test_resolve_fallback_to_registry(self, mini_registry):
        """When ontologia import fails, fall back to name-based lookup."""
        # Simulate ontologia not available by patching the import
        with patch.dict("sys.modules", {"ontologia.registry.store": None}):
            result = resolve_entity("organvm-engine", registry=mini_registry)

        assert result is not None
        assert result["source"] == "registry"
        assert result["uid"] is None
        assert result["display_name"] == "organvm-engine"
        assert result["organ_key"] == "META-ORGANVM"

    def test_resolve_not_found(self, mini_registry):
        """When entity exists nowhere, return None."""
        with patch.dict("sys.modules", {"ontologia.registry.store": None}):
            result = resolve_entity("nonexistent-repo", registry=mini_registry)
        assert result is None

    def test_resolve_enriches_with_registry(self, ont_store, mini_registry):
        """Ontologia result should include registry data when available."""
        with patch("ontologia.registry.store.open_store", return_value=ont_store):
            result = resolve_entity("organvm-engine", registry=mini_registry)

        assert result is not None
        assert result.get("organ_key") == "META-ORGANVM"
        assert result.get("registry_entry", {}).get("tier") == "flagship"


# ---------------------------------------------------------------------------
# Event bus forwarding
# ---------------------------------------------------------------------------

class TestEventBusForwarding:
    def test_pulse_emit_forwards_to_ontologia(self, tmp_path):
        """Pulse events should also appear on the ontologia bus."""
        from organvm_engine.pulse import events as pulse_events

        received: list = []
        ontologia_bus.subscribe("*", received.append)

        # Redirect pulse events to tmp_path too
        pulse_path = tmp_path / "pulse-events.jsonl"
        with patch.object(pulse_events, "_events_path", return_value=pulse_path):
            pulse_events.emit("test.event", "test-source", {"key": "value"})

        # Should have been forwarded to ontologia
        assert len(received) == 1
        assert received[0].event_type == "test.event"
        assert received[0].source == "pulse:test-source"


# ---------------------------------------------------------------------------
# CLI ontologia commands
# ---------------------------------------------------------------------------

class TestCLIOntologia:
    def test_ontologia_status_no_store(self, capsys):
        """Status command should work even with empty store."""
        from organvm_engine.cli.ontologia import cmd_ontologia_status

        args = argparse.Namespace()
        result = cmd_ontologia_status(args)
        assert result == 0
        output = capsys.readouterr().out
        assert "Store:" in output

    def test_ontologia_list_empty(self, capsys):
        """List command with empty store."""
        from organvm_engine.cli.ontologia import cmd_ontologia_list

        args = argparse.Namespace(type=None, json=False)
        result = cmd_ontologia_list(args)
        assert result == 0
        output = capsys.readouterr().out
        assert "Total: 0" in output

    def test_ontologia_resolve_not_found(self, capsys):
        """Resolve command with unknown entity."""
        from organvm_engine.cli.ontologia import cmd_ontologia_resolve

        args = argparse.Namespace(query="nonexistent", json=False)
        result = cmd_ontologia_resolve(args)
        assert result == 1

    def test_ontologia_bootstrap(self, tmp_path, capsys):
        """Bootstrap from a minimal registry."""
        from organvm_engine.cli.ontologia import cmd_ontologia_bootstrap

        # Write a mini registry
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps({
            "organs": {
                "ORGAN-I": {
                    "name": "Theoria",
                    "repositories": [
                        {"name": "test-repo", "tier": "standard"},
                    ],
                },
            },
        }))

        store_dir = tmp_path / "ont-store"
        args = argparse.Namespace(
            registry=str(registry_path),
            store_dir=str(store_dir),
        )
        result = cmd_ontologia_bootstrap(args)
        assert result == 0
        output = capsys.readouterr().out
        assert "Organs created:  1" in output
        assert "Repos created:   1" in output

    def test_parser_has_ontologia_command(self):
        """Verify ontologia is registered in the CLI parser."""
        from organvm_engine.cli import build_parser

        parser = build_parser()
        # Parse a minimal ontologia command
        args = parser.parse_args(["ontologia", "status"])
        assert args.command == "ontologia"
        assert args.subcommand == "status"

    def test_parser_ontologia_resolve(self):
        """Verify resolve subcommand args."""
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["ontologia", "resolve", "my-entity", "--json"])
        assert args.command == "ontologia"
        assert args.subcommand == "resolve"
        assert args.query == "my-entity"
        assert args.json is True
