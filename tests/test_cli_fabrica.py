"""Tests for the fabrica CLI command group (SPEC-024 Phase 4).

Tests the CLI projection of the Cyclic Dispatch Protocol:
release, catch, handoff, fortify, status, log subcommands.
"""

from __future__ import annotations

import argparse

import pytest


@pytest.fixture(autouse=True)
def _isolate_fabrica(tmp_path, monkeypatch):
    """Redirect fabrica I/O to a temp directory."""
    monkeypatch.setenv("ORGANVM_FABRICA_DIR", str(tmp_path / "fabrica"))


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestFabricaParser:
    def test_fabrica_command_exists(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        # Should not raise
        args = parser.parse_args(["fabrica", "status"])
        assert args.command == "fabrica"
        assert args.subcommand == "status"

    def test_fabrica_release_args(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "fabrica", "release",
            "--text", "Build the dispatch protocol",
            "--organ", "META",
            "--tags", "dispatch,protocol",
        ])
        assert args.command == "fabrica"
        assert args.subcommand == "release"
        assert args.text == "Build the dispatch protocol"
        assert args.organ == "META"
        assert args.tags == "dispatch,protocol"

    def test_fabrica_catch_args(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "fabrica", "catch",
            "--packet-id", "abc123",
            "--thesis", "Engine module approach",
            "--scope", "heavy",
        ])
        assert args.packet_id == "abc123"
        assert args.thesis == "Engine module approach"
        assert args.scope == "heavy"

    def test_fabrica_handoff_args(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "fabrica", "handoff",
            "--packet-id", "abc123",
            "--backend", "copilot",
            "--repo", "meta-organvm/organvm-engine",
            "--title", "Task title",
        ])
        assert args.backend == "copilot"
        assert args.repo == "meta-organvm/organvm-engine"
        assert args.title == "Task title"

    def test_fabrica_fortify_args(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "fabrica", "fortify",
            "--verdict", "approve",
            "--intent-id", "int001",
        ])
        assert args.verdict == "approve"
        assert args.intent_id == "int001"

    def test_fabrica_log_args(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args([
            "fabrica", "log",
            "--packet-id", "abc123",
            "--json",
        ])
        assert args.packet_id == "abc123"
        assert args.json is True


# ---------------------------------------------------------------------------
# Command execution tests
# ---------------------------------------------------------------------------

class TestFabricaRelease:
    def test_release_creates_packet(self):
        from organvm_engine.cli.fabrica import cmd_fabrica_release
        from organvm_engine.fabrica.store import load_packets

        args = argparse.Namespace(
            text="Build the dispatch protocol",
            source="cli",
            organ="META",
            tags="dispatch,protocol",
            json=False,
        )
        rc = cmd_fabrica_release(args)
        assert rc == 0

        packets = load_packets()
        assert len(packets) == 1
        assert packets[0].raw_text == "Build the dispatch protocol"
        assert packets[0].organ_hint == "META"
        assert packets[0].tags == ["dispatch", "protocol"]

    def test_release_requires_text(self):
        from organvm_engine.cli.fabrica import cmd_fabrica_release

        args = argparse.Namespace(
            text=None,
            source="cli",
            organ=None,
            tags=None,
            json=False,
        )
        rc = cmd_fabrica_release(args)
        assert rc == 1

    def test_release_json_output(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_release

        args = argparse.Namespace(
            text="JSON test",
            source="cli",
            organ=None,
            tags=None,
            json=True,
        )
        rc = cmd_fabrica_release(args)
        assert rc == 0
        import json
        output = json.loads(capsys.readouterr().out)
        assert output["raw_text"] == "JSON test"
        assert output["type"] == "relay_packet"


class TestFabricaCatch:
    def _create_packet(self) -> str:
        from organvm_engine.fabrica.models import RelayPacket
        from organvm_engine.fabrica.store import save_packet

        p = RelayPacket(raw_text="test packet", source="cli")
        save_packet(p)
        return p.id

    def test_catch_create_vector(self):
        from organvm_engine.cli.fabrica import cmd_fabrica_catch
        from organvm_engine.fabrica.store import load_vectors

        pid = self._create_packet()
        args = argparse.Namespace(
            packet_id=pid,
            thesis="Engine module approach",
            select=None,
            list=False,
            organs="META,ORGAN-I",
            scope="heavy",
            agents="claude,copilot",
            json=False,
        )
        rc = cmd_fabrica_catch(args)
        assert rc == 0

        vectors = load_vectors(packet_id=pid)
        assert len(vectors) == 1
        assert vectors[0].thesis == "Engine module approach"
        assert vectors[0].target_organs == ["META", "ORGAN-I"]
        assert vectors[0].agent_types == ["claude", "copilot"]

    def test_catch_list_vectors(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_catch
        from organvm_engine.fabrica.models import ApproachVector
        from organvm_engine.fabrica.store import save_vector

        pid = self._create_packet()
        v = ApproachVector(packet_id=pid, thesis="First approach")
        save_vector(v)

        args = argparse.Namespace(
            packet_id=pid,
            thesis=None,
            select=None,
            list=True,
            organs=None,
            scope="medium",
            agents=None,
            json=False,
        )
        rc = cmd_fabrica_catch(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "First approach" in out

    def test_catch_select_vector(self):
        from organvm_engine.cli.fabrica import cmd_fabrica_catch
        from organvm_engine.fabrica.models import ApproachVector
        from organvm_engine.fabrica.store import load_transitions, save_vector

        pid = self._create_packet()
        v = ApproachVector(packet_id=pid, thesis="Selected approach")
        save_vector(v)

        args = argparse.Namespace(
            packet_id=pid,
            thesis=None,
            select=v.id[:4],
            list=False,
            organs=None,
            scope="medium",
            agents=None,
            json=False,
        )
        rc = cmd_fabrica_catch(args)
        assert rc == 0

        transitions = load_transitions(packet_id=pid)
        to_phases = [t["to"] for t in transitions]
        assert "handoff" in to_phases

    def test_catch_unknown_packet(self):
        from organvm_engine.cli.fabrica import cmd_fabrica_catch

        args = argparse.Namespace(
            packet_id="nonexistent",
            thesis=None,
            select=None,
            list=False,
            organs=None,
            scope="medium",
            agents=None,
            json=False,
        )
        rc = cmd_fabrica_catch(args)
        assert rc == 1


class TestFabricaHandoff:
    def _create_packet_with_vector(self) -> str:
        from organvm_engine.fabrica.models import ApproachVector, RelayPacket
        from organvm_engine.fabrica.store import save_packet, save_vector

        p = RelayPacket(raw_text="handoff test", source="cli")
        save_packet(p)
        v = ApproachVector(packet_id=p.id, thesis="approach", selected=True)
        save_vector(v)
        return p.id

    def test_handoff_dry_run(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_handoff
        from organvm_engine.fabrica.store import load_dispatches

        pid = self._create_packet_with_vector()
        args = argparse.Namespace(
            packet_id=pid,
            backend="copilot",
            repo="meta-organvm/organvm-engine",
            title="Test dispatch",
            body="Implement this",
            task_id="task-dry",
            labels=None,
            branch=None,
            execute=False,
            json=False,
        )
        rc = cmd_fabrica_handoff(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "DRY-RUN" in out

        dispatches = load_dispatches()
        assert len(dispatches) == 1
        assert dispatches[0].backend == "copilot"

    def test_handoff_invalid_backend(self):
        from organvm_engine.cli.fabrica import cmd_fabrica_handoff

        pid = self._create_packet_with_vector()
        args = argparse.Namespace(
            packet_id=pid,
            backend="skynet",
            repo="org/repo",
            title="Test",
            body="",
            task_id=None,
            labels=None,
            branch=None,
            execute=False,
            json=False,
        )
        rc = cmd_fabrica_handoff(args)
        assert rc == 1

    def test_handoff_missing_repo(self):
        from organvm_engine.cli.fabrica import cmd_fabrica_handoff

        pid = self._create_packet_with_vector()
        args = argparse.Namespace(
            packet_id=pid,
            backend="copilot",
            repo=None,
            title="Test",
            body="",
            task_id=None,
            labels=None,
            branch=None,
            execute=False,
            json=False,
        )
        rc = cmd_fabrica_handoff(args)
        assert rc == 1


class TestFabricaStatus:
    def test_status_empty(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_status

        args = argparse.Namespace(packet_id=None, json=False)
        rc = cmd_fabrica_status(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "No relay cycles" in out

    def test_status_shows_packets(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_status
        from organvm_engine.fabrica.models import RelayPacket
        from organvm_engine.fabrica.store import save_packet

        p = RelayPacket(raw_text="Status test packet", source="cli")
        save_packet(p)

        args = argparse.Namespace(packet_id=None, json=False)
        rc = cmd_fabrica_status(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "Status test packet" in out

    def test_status_json_output(self, capsys):
        import json

        from organvm_engine.cli.fabrica import cmd_fabrica_status
        from organvm_engine.fabrica.models import RelayPacket
        from organvm_engine.fabrica.store import save_packet

        p = RelayPacket(raw_text="JSON status", source="mcp")
        save_packet(p)

        args = argparse.Namespace(packet_id=None, json=True)
        rc = cmd_fabrica_status(args)
        assert rc == 0
        output = json.loads(capsys.readouterr().out)
        assert len(output) == 1
        assert output[0]["packet"]["raw_text"] == "JSON status"


class TestFabricaLog:
    def test_log_empty(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_log

        args = argparse.Namespace(packet_id=None, json=False)
        rc = cmd_fabrica_log(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "No transitions" in out

    def test_log_shows_transitions(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_log
        from organvm_engine.fabrica.models import RelayPhase
        from organvm_engine.fabrica.store import log_transition

        log_transition("pkt001", RelayPhase.RELEASE, RelayPhase.CATCH, reason="test")
        log_transition("pkt001", RelayPhase.CATCH, RelayPhase.HANDOFF, reason="selected")

        args = argparse.Namespace(packet_id="pkt001", json=False)
        rc = cmd_fabrica_log(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "release" in out
        assert "catch" in out
        assert "handoff" in out

    def test_log_json_output(self, capsys):
        import json

        from organvm_engine.cli.fabrica import cmd_fabrica_log
        from organvm_engine.fabrica.models import RelayPhase
        from organvm_engine.fabrica.store import log_transition

        log_transition("pkt002", RelayPhase.RELEASE, RelayPhase.CATCH)

        args = argparse.Namespace(packet_id="pkt002", json=True)
        rc = cmd_fabrica_log(args)
        assert rc == 0
        output = json.loads(capsys.readouterr().out)
        assert len(output) == 1
        assert output[0]["from"] == "release"
        assert output[0]["to"] == "catch"


# ---------------------------------------------------------------------------
# Full cycle integration
# ---------------------------------------------------------------------------

class TestFabricaCLIFullCycle:
    """Trace a complete RELEASE → CATCH → HANDOFF → FORTIFY → COMPLETE
    cycle through the CLI layer."""

    def test_full_cycle_dry_run(self):
        from organvm_engine.cli.fabrica import (
            cmd_fabrica_catch,
            cmd_fabrica_handoff,
            cmd_fabrica_release,
            cmd_fabrica_status,
        )
        from organvm_engine.fabrica.store import load_packets, load_transitions

        # RELEASE
        release_args = argparse.Namespace(
            text="Full cycle test",
            source="cli",
            organ="META",
            tags="test",
            json=False,
        )
        assert cmd_fabrica_release(release_args) == 0
        packets = load_packets()
        assert len(packets) == 1
        pid = packets[0].id

        # CATCH — create vector
        catch_args = argparse.Namespace(
            packet_id=pid,
            thesis="Engine module approach",
            select=None,
            list=False,
            organs="META",
            scope="medium",
            agents="copilot",
            json=False,
        )
        assert cmd_fabrica_catch(catch_args) == 0

        # CATCH — select vector
        from organvm_engine.fabrica.store import load_vectors
        vectors = load_vectors(packet_id=pid)
        assert len(vectors) == 1

        select_args = argparse.Namespace(
            packet_id=pid,
            thesis=None,
            select=vectors[0].id[:4],
            list=False,
            organs=None,
            scope="medium",
            agents=None,
            json=False,
        )
        assert cmd_fabrica_catch(select_args) == 0

        # HANDOFF — dispatch (dry-run)
        handoff_args = argparse.Namespace(
            packet_id=pid,
            backend="copilot",
            repo="meta-organvm/organvm-engine",
            title="Full cycle task",
            body="Implement full cycle",
            task_id="full-cycle-task",
            labels=None,
            branch=None,
            execute=False,
            json=False,
        )
        assert cmd_fabrica_handoff(handoff_args) == 0

        # STATUS
        status_args = argparse.Namespace(packet_id=None, json=False)
        assert cmd_fabrica_status(status_args) == 0

        # Verify transitions
        transitions = load_transitions(packet_id=pid)
        phases = [t["to"] for t in transitions]
        assert "catch" in phases
        assert "handoff" in phases
        assert "fortify" in phases
