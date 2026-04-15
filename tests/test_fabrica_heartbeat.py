"""Tests for the fabrica heartbeat daemon (SPEC-024 Phase 5).

Tests the heartbeat polling, transition, health report, plist generation,
and CLI integration. All backend calls are mocked -- no real GitHub API
traffic.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from organvm_engine.fabrica.heartbeat import (
    DEFAULT_INTERVAL_SECONDS,
    PLIST_LABEL,
    HeartbeatReport,
    PollResult,
    generate_health_report,
    generate_plist,
    poll_active_relays,
    run_heartbeat,
    transition_completed,
)
from organvm_engine.fabrica.models import (
    ApproachVector,
    DispatchRecord,
    DispatchStatus,
    RelayIntent,
    RelayPacket,
    RelayPhase,
)
from organvm_engine.fabrica.store import (
    load_dispatches,
    load_transitions,
    log_transition,
    save_dispatch,
    save_intent,
    save_packet,
    save_vector,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_fabrica(tmp_path, monkeypatch):
    """Redirect all fabrica I/O to a temp directory."""
    monkeypatch.setenv("ORGANVM_FABRICA_DIR", str(tmp_path / "fabrica"))


@pytest.fixture()
def active_relay(tmp_path):
    """Create a full relay cycle with an active dispatch in DISPATCHED state.

    Returns (packet, intent, dispatch_record).
    """
    packet = RelayPacket(
        raw_text="Heartbeat test task",
        source="cli",
        tags=["test"],
        timestamp=1000.0,
    )
    save_packet(packet)
    log_transition(packet.id, RelayPhase.RELEASE, RelayPhase.CATCH, reason="auto")

    vector = ApproachVector(
        packet_id=packet.id,
        thesis="Test approach",
        selected=True,
    )
    save_vector(vector)
    log_transition(packet.id, RelayPhase.CATCH, RelayPhase.HANDOFF, reason="selected")

    intent = RelayIntent(vector_id=vector.id, packet_id=packet.id)
    save_intent(intent)

    record = DispatchRecord(
        task_id="task-hb-001",
        intent_id=intent.id,
        backend="copilot",
        target="https://github.com/meta-organvm/organvm-engine/issues/42",
        status=DispatchStatus.DISPATCHED,
        dispatched_at=time.time(),
    )
    save_dispatch(record)
    log_transition(packet.id, RelayPhase.HANDOFF, RelayPhase.FORTIFY, reason="dispatched")

    return packet, intent, record


@pytest.fixture()
def completed_relay(tmp_path):
    """Create a relay with a MERGED dispatch (terminal state)."""
    packet = RelayPacket(
        raw_text="Completed task",
        source="cli",
        timestamp=2000.0,
    )
    save_packet(packet)

    vector = ApproachVector(packet_id=packet.id, thesis="Done approach", selected=True)
    save_vector(vector)

    intent = RelayIntent(vector_id=vector.id, packet_id=packet.id)
    save_intent(intent)

    record = DispatchRecord(
        task_id="task-done",
        intent_id=intent.id,
        backend="copilot",
        target="https://github.com/org/repo/issues/10",
        status=DispatchStatus.MERGED,
        dispatched_at=time.time() - 3600,
        returned_at=time.time() - 1800,
    )
    save_dispatch(record)

    return packet, intent, record


# ---------------------------------------------------------------------------
# PollResult tests
# ---------------------------------------------------------------------------

class TestPollResult:
    def test_poll_result_fields(self):
        result = PollResult(
            record_id="abc123",
            backend="copilot",
            old_status=DispatchStatus.DISPATCHED,
            new_status=DispatchStatus.IN_PROGRESS,
            changed=True,
        )
        assert result.record_id == "abc123"
        assert result.changed is True
        assert result.error is None

    def test_poll_result_with_error(self):
        result = PollResult(
            record_id="abc123",
            backend="copilot",
            old_status=DispatchStatus.DISPATCHED,
            new_status=DispatchStatus.DISPATCHED,
            changed=False,
            error="Connection timeout",
        )
        assert result.error == "Connection timeout"
        assert result.changed is False


# ---------------------------------------------------------------------------
# HeartbeatReport tests
# ---------------------------------------------------------------------------

class TestHeartbeatReport:
    def test_report_defaults(self):
        report = HeartbeatReport()
        assert report.active_intents == 0
        assert report.total_dispatches == 0
        assert report.polled == 0
        assert report.changed == 0
        assert report.errors == 0

    def test_report_to_dict(self):
        report = HeartbeatReport(
            active_intents=3,
            total_dispatches=5,
            polled=2,
            changed=1,
            completed=1,
            failed=0,
            errors=0,
            duration_seconds=1.5,
        )
        d = report.to_dict()
        assert d["type"] == "heartbeat_report"
        assert d["active_intents"] == 3
        assert d["polled"] == 2
        assert d["changed"] == 1
        assert d["duration_seconds"] == 1.5

    def test_report_to_dict_includes_poll_results(self):
        report = HeartbeatReport(
            poll_results=[{
                "record_id": "r1",
                "backend": "copilot",
                "old_status": "dispatched",
                "new_status": "in_progress",
                "changed": True,
                "pr_url": None,
                "error": None,
            }],
        )
        d = report.to_dict()
        assert len(d["poll_results"]) == 1
        assert d["poll_results"][0]["record_id"] == "r1"


# ---------------------------------------------------------------------------
# poll_active_relays tests
# ---------------------------------------------------------------------------

class TestPollActiveRelays:
    def test_no_active_relays_returns_empty(self):
        results = poll_active_relays()
        assert results == []

    def test_terminal_dispatches_are_skipped(self, completed_relay):
        """MERGED dispatches should not be polled."""
        results = poll_active_relays()
        assert len(results) == 0

    @patch("organvm_engine.fabrica.heartbeat.get_backend")
    def test_dispatched_record_is_polled(self, mock_get_backend, active_relay):
        packet, intent, record = active_relay

        mock_backend = MagicMock()
        mock_backend.check_status.return_value = DispatchRecord(
            id=record.id,
            task_id=record.task_id,
            intent_id=record.intent_id,
            backend="copilot",
            target=record.target,
            status=DispatchStatus.IN_PROGRESS,
            dispatched_at=record.dispatched_at,
        )
        mock_get_backend.return_value = mock_backend

        results = poll_active_relays()
        assert len(results) == 1
        assert results[0].changed is True
        assert results[0].old_status == DispatchStatus.DISPATCHED
        assert results[0].new_status == DispatchStatus.IN_PROGRESS

    @patch("organvm_engine.fabrica.heartbeat.get_backend")
    def test_unchanged_record_not_marked_changed(self, mock_get_backend, active_relay):
        packet, intent, record = active_relay

        mock_backend = MagicMock()
        mock_backend.check_status.return_value = DispatchRecord(
            id=record.id,
            task_id=record.task_id,
            intent_id=record.intent_id,
            backend="copilot",
            target=record.target,
            status=DispatchStatus.DISPATCHED,
            dispatched_at=record.dispatched_at,
        )
        mock_get_backend.return_value = mock_backend

        results = poll_active_relays()
        assert len(results) == 1
        assert results[0].changed is False

    @patch("organvm_engine.fabrica.heartbeat.get_backend")
    def test_backend_error_is_captured(self, mock_get_backend, active_relay):
        packet, intent, record = active_relay

        mock_backend = MagicMock()
        mock_backend.check_status.side_effect = RuntimeError("API down")
        mock_get_backend.return_value = mock_backend

        results = poll_active_relays()
        assert len(results) == 1
        assert results[0].error == "API down"
        assert results[0].changed is False

    @patch("organvm_engine.fabrica.heartbeat.get_backend")
    def test_draft_returned_not_polled(self, mock_get_backend, active_relay):
        """DRAFT_RETURNED dispatches await human FORTIFY, not backend polling.

        The _latest_dispatches helper deduplicates by dispatch ID so only
        the most recent state is visible. After updating to DRAFT_RETURNED,
        the original DISPATCHED entry is superseded and no polling occurs.
        """
        packet, intent, record = active_relay

        # Update the record to DRAFT_RETURNED (append-only store)
        returned = DispatchRecord(
            id=record.id,
            task_id=record.task_id,
            intent_id=record.intent_id,
            backend="copilot",
            target=record.target,
            status=DispatchStatus.DRAFT_RETURNED,
            dispatched_at=record.dispatched_at,
            returned_at=time.time(),
        )
        save_dispatch(returned)

        mock_backend = MagicMock()
        mock_backend.check_status.return_value = record
        mock_get_backend.return_value = mock_backend

        results = poll_active_relays()
        # DRAFT_RETURNED is not pollable -- the dedup helper ensures
        # the old DISPATCHED entry is superseded, so nothing is polled
        assert len(results) == 0
        mock_backend.check_status.assert_not_called()


# ---------------------------------------------------------------------------
# transition_completed tests
# ---------------------------------------------------------------------------

class TestTransitionCompleted:
    def test_no_results_no_transitions(self):
        transitions = transition_completed([])
        assert transitions == []

    @patch("organvm_engine.fabrica.heartbeat.get_backend")
    def test_draft_returned_triggers_fortify_ready(self, mock_get_backend, active_relay):
        """When a dispatch transitions to DRAFT_RETURNED and the relay is
        already in FORTIFY, log a fortify_ready event."""
        packet, intent, record = active_relay

        result = PollResult(
            record_id=record.id,
            backend="copilot",
            old_status=DispatchStatus.DISPATCHED,
            new_status=DispatchStatus.DRAFT_RETURNED,
            changed=True,
        )

        # Save the DRAFT_RETURNED version so transition_completed sees it
        returned = DispatchRecord(
            id=record.id,
            task_id=record.task_id,
            intent_id=record.intent_id,
            backend="copilot",
            target=record.target,
            status=DispatchStatus.DRAFT_RETURNED,
            dispatched_at=record.dispatched_at,
            returned_at=time.time(),
        )
        save_dispatch(returned)

        transitions = transition_completed([result])
        # Should have at least one transition about fortify readiness
        assert len(transitions) >= 1
        events = [t["event"] for t in transitions]
        assert "fortify_ready" in events

    def test_unchanged_results_no_transitions(self, active_relay):
        """Unchanged poll results should not trigger any transitions."""
        _, _, record = active_relay

        result = PollResult(
            record_id=record.id,
            backend="copilot",
            old_status=DispatchStatus.DISPATCHED,
            new_status=DispatchStatus.DISPATCHED,
            changed=False,
        )
        transitions = transition_completed([result])
        assert transitions == []

    def test_handoff_to_fortify_transition(self):
        """When a dispatch returns and the relay is still in HANDOFF,
        the heartbeat should advance it to FORTIFY."""
        packet = RelayPacket(raw_text="Handoff test", source="cli", timestamp=3000.0)
        save_packet(packet)
        log_transition(packet.id, RelayPhase.RELEASE, RelayPhase.CATCH)

        vector = ApproachVector(packet_id=packet.id, thesis="approach", selected=True)
        save_vector(vector)
        log_transition(packet.id, RelayPhase.CATCH, RelayPhase.HANDOFF)

        intent = RelayIntent(vector_id=vector.id, packet_id=packet.id)
        save_intent(intent)

        record = DispatchRecord(
            task_id="task-ho",
            intent_id=intent.id,
            backend="human",
            target="dry-run://org/repo",
            status=DispatchStatus.DRAFT_RETURNED,
            dispatched_at=time.time() - 60,
            returned_at=time.time(),
        )
        save_dispatch(record)

        result = PollResult(
            record_id=record.id,
            backend="human",
            old_status=DispatchStatus.DISPATCHED,
            new_status=DispatchStatus.DRAFT_RETURNED,
            changed=True,
        )
        transitions = transition_completed([result])
        assert any(t["event"] == "handoff_to_fortify" for t in transitions)

        # Verify the transition was logged
        trans_log = load_transitions(packet_id=packet.id)
        phases = [t["to"] for t in trans_log]
        assert "fortify" in phases


# ---------------------------------------------------------------------------
# generate_health_report tests
# ---------------------------------------------------------------------------

class TestGenerateHealthReport:
    def test_empty_report(self):
        report = generate_health_report([], [], time.time())
        assert report.active_intents == 0
        assert report.total_dispatches == 0
        assert report.polled == 0
        assert report.changed == 0

    def test_report_counts_poll_results(self, active_relay):
        _, intent, record = active_relay
        results = [
            PollResult(
                record_id=record.id,
                backend="copilot",
                old_status=DispatchStatus.DISPATCHED,
                new_status=DispatchStatus.IN_PROGRESS,
                changed=True,
            ),
        ]
        report = generate_health_report(results, [], time.time() - 1.5)
        assert report.polled == 1
        assert report.changed == 1
        assert report.active_intents == 1
        assert report.total_dispatches >= 1
        assert report.duration_seconds >= 1.0

    def test_report_counts_errors(self, active_relay):
        _, _, record = active_relay
        results = [
            PollResult(
                record_id=record.id,
                backend="copilot",
                old_status=DispatchStatus.DISPATCHED,
                new_status=DispatchStatus.DISPATCHED,
                changed=False,
                error="Timeout",
            ),
        ]
        report = generate_health_report(results, [], time.time())
        assert report.errors == 1

    def test_report_counts_completed_and_failed(self):
        """Set up dispatches with mixed terminal states."""
        packet = RelayPacket(raw_text="Multi dispatch", source="cli", timestamp=5000.0)
        save_packet(packet)
        vector = ApproachVector(packet_id=packet.id, thesis="multi", selected=True)
        save_vector(vector)
        intent = RelayIntent(vector_id=vector.id, packet_id=packet.id)
        save_intent(intent)

        # One merged
        save_dispatch(DispatchRecord(
            task_id="t1", intent_id=intent.id, backend="copilot",
            target="u1", status=DispatchStatus.MERGED,
        ))
        # One rejected
        save_dispatch(DispatchRecord(
            task_id="t2", intent_id=intent.id, backend="copilot",
            target="u2", status=DispatchStatus.REJECTED,
        ))
        # One fortified
        save_dispatch(DispatchRecord(
            task_id="t3", intent_id=intent.id, backend="human",
            target="u3", status=DispatchStatus.FORTIFIED,
        ))

        report = generate_health_report([], [], time.time())
        assert report.completed == 2  # MERGED + FORTIFIED
        assert report.failed == 1    # REJECTED


# ---------------------------------------------------------------------------
# run_heartbeat integration test
# ---------------------------------------------------------------------------

class TestRunHeartbeat:
    def test_heartbeat_empty_system(self):
        """Heartbeat on an empty fabrica store completes without error."""
        report = run_heartbeat(quiet=True, json_output=False)
        assert report.active_intents == 0
        assert report.polled == 0
        assert report.errors == 0

    @patch("organvm_engine.fabrica.heartbeat.get_backend")
    def test_heartbeat_with_active_dispatch(self, mock_get_backend, active_relay):
        packet, intent, record = active_relay

        mock_backend = MagicMock()
        mock_backend.check_status.return_value = DispatchRecord(
            id=record.id,
            task_id=record.task_id,
            intent_id=record.intent_id,
            backend="copilot",
            target=record.target,
            status=DispatchStatus.IN_PROGRESS,
            dispatched_at=record.dispatched_at,
        )
        mock_get_backend.return_value = mock_backend

        report = run_heartbeat(quiet=True, json_output=False)
        assert report.polled == 1
        assert report.changed == 1

    @patch("organvm_engine.fabrica.heartbeat.get_backend")
    def test_heartbeat_json_output(self, mock_get_backend, active_relay, capsys):
        packet, intent, record = active_relay

        mock_backend = MagicMock()
        mock_backend.check_status.return_value = DispatchRecord(
            id=record.id,
            task_id=record.task_id,
            intent_id=record.intent_id,
            backend="copilot",
            target=record.target,
            status=DispatchStatus.DISPATCHED,
            dispatched_at=record.dispatched_at,
        )
        mock_get_backend.return_value = mock_backend

        run_heartbeat(quiet=False, json_output=True)
        output = json.loads(capsys.readouterr().out)
        assert output["type"] == "heartbeat_report"
        assert "polled" in output

    def test_heartbeat_report_persisted(self, tmp_path, monkeypatch):
        """Verify the heartbeat report is saved to the fabrica directory."""
        fab_dir = tmp_path / "fabrica"
        monkeypatch.setenv("ORGANVM_FABRICA_DIR", str(fab_dir))

        run_heartbeat(quiet=True, json_output=False)

        report_path = fab_dir / "logs" / "heartbeat-latest.json"
        assert report_path.exists()
        data = json.loads(report_path.read_text())
        assert data["type"] == "heartbeat_report"

        log_path = fab_dir / "logs" / "heartbeat.jsonl"
        assert log_path.exists()
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) >= 1


# ---------------------------------------------------------------------------
# Plist generation tests
# ---------------------------------------------------------------------------

class TestPlistGeneration:
    def test_generate_plist_default_interval(self):
        plist = generate_plist()
        assert plist["Label"] == PLIST_LABEL
        assert plist["StartInterval"] == DEFAULT_INTERVAL_SECONDS
        assert plist["RunAtLoad"] is False
        assert plist["ProcessType"] == "Background"
        assert plist["Nice"] == 10
        assert plist["LowPriorityIO"] is True
        assert plist["ExecTimeout"] == 300

    def test_generate_plist_custom_interval(self):
        plist = generate_plist(interval=60)
        assert plist["StartInterval"] == 60

    def test_generate_plist_program_arguments(self):
        plist = generate_plist()
        prog = plist["ProgramArguments"]
        assert len(prog) == 3
        # prog[0] is the python interpreter path
        assert prog[1] == "-m"
        assert prog[2] == "organvm_engine.fabrica.heartbeat"

    def test_generate_plist_log_paths(self):
        plist = generate_plist()
        assert "heartbeat-stdout.log" in plist["StandardOutPath"]
        assert "heartbeat-stderr.log" in plist["StandardErrorPath"]

    def test_generate_plist_environment(self):
        plist = generate_plist()
        env = plist["EnvironmentVariables"]
        assert "PATH" in env
        assert "HOME" in env
        assert "/opt/homebrew/bin" in env["PATH"]


# ---------------------------------------------------------------------------
# LaunchAgent install/uninstall tests
# ---------------------------------------------------------------------------

class TestLaunchAgentManagement:
    @patch("organvm_engine.fabrica.heartbeat.subprocess.run")
    @patch("organvm_engine.fabrica.heartbeat._plist_dir")
    def test_install_creates_plist(self, mock_plist_dir, mock_run, tmp_path):
        from organvm_engine.fabrica.heartbeat import install_launchagent

        agent_dir = tmp_path / "LaunchAgents"
        agent_dir.mkdir()
        mock_plist_dir.return_value = agent_dir
        mock_run.return_value = MagicMock(returncode=0)

        result = install_launchagent(interval=120)
        assert result.exists()
        assert result.suffix == ".plist"

        # Verify launchctl load was called
        load_calls = [c for c in mock_run.call_args_list if "load" in str(c)]
        assert len(load_calls) >= 1

    @patch("organvm_engine.fabrica.heartbeat.subprocess.run")
    @patch("organvm_engine.fabrica.heartbeat._plist_dir")
    def test_uninstall_removes_plist(self, mock_plist_dir, mock_run, tmp_path):
        import plistlib

        from organvm_engine.fabrica.heartbeat import uninstall_launchagent

        agent_dir = tmp_path / "LaunchAgents"
        agent_dir.mkdir()
        mock_plist_dir.return_value = agent_dir

        # Create a dummy plist
        plist_path = agent_dir / f"{PLIST_LABEL}.plist"
        with plist_path.open("wb") as f:
            plistlib.dump({"Label": PLIST_LABEL}, f)

        mock_run.return_value = MagicMock(returncode=0)

        uninstall_launchagent()
        assert not plist_path.exists()

    @patch("organvm_engine.fabrica.heartbeat.subprocess.run")
    @patch("organvm_engine.fabrica.heartbeat._plist_dir")
    def test_uninstall_no_plist_is_safe(self, mock_plist_dir, mock_run, tmp_path, capsys):
        from organvm_engine.fabrica.heartbeat import uninstall_launchagent

        agent_dir = tmp_path / "LaunchAgents"
        agent_dir.mkdir()
        mock_plist_dir.return_value = agent_dir
        mock_run.return_value = MagicMock(returncode=0)

        uninstall_launchagent()
        out = capsys.readouterr().out
        assert "No plist found" in out


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestFabricaHeartbeatCLI:
    def test_heartbeat_parser_exists(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["fabrica", "heartbeat"])
        assert args.command == "fabrica"
        assert args.subcommand == "heartbeat"

    def test_heartbeat_install_flag(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["fabrica", "heartbeat", "--install"])
        assert args.install is True

    def test_heartbeat_uninstall_flag(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["fabrica", "heartbeat", "--uninstall"])
        assert args.uninstall is True

    def test_heartbeat_interval_flag(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["fabrica", "heartbeat", "--interval", "60"])
        assert args.interval == 60

    def test_heartbeat_json_flag(self):
        from organvm_engine.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["fabrica", "heartbeat", "--json"])
        assert args.json is True

    def test_heartbeat_cmd_runs_cycle(self):
        from organvm_engine.cli.fabrica import cmd_fabrica_heartbeat

        args = argparse.Namespace(
            install=False,
            uninstall=False,
            interval=900,
            json=False,
        )
        rc = cmd_fabrica_heartbeat(args)
        assert rc == 0

    def test_heartbeat_cmd_json_output(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_heartbeat

        args = argparse.Namespace(
            install=False,
            uninstall=False,
            interval=900,
            json=True,
        )
        rc = cmd_fabrica_heartbeat(args)
        assert rc == 0
        output = json.loads(capsys.readouterr().out)
        assert output["type"] == "heartbeat_report"

    def test_heartbeat_cmd_install_uninstall_conflict(self, capsys):
        from organvm_engine.cli.fabrica import cmd_fabrica_heartbeat

        args = argparse.Namespace(
            install=True,
            uninstall=True,
            interval=900,
            json=False,
        )
        rc = cmd_fabrica_heartbeat(args)
        assert rc == 1

    @patch("organvm_engine.fabrica.heartbeat.install_launchagent")
    def test_heartbeat_cmd_install(self, mock_install):
        from organvm_engine.cli.fabrica import cmd_fabrica_heartbeat

        mock_install.return_value = Path("/tmp/test.plist")
        args = argparse.Namespace(
            install=True,
            uninstall=False,
            interval=120,
            json=False,
        )
        rc = cmd_fabrica_heartbeat(args)
        assert rc == 0
        mock_install.assert_called_once_with(interval=120)

    @patch("organvm_engine.fabrica.heartbeat.uninstall_launchagent")
    def test_heartbeat_cmd_uninstall(self, mock_uninstall):
        from organvm_engine.cli.fabrica import cmd_fabrica_heartbeat

        args = argparse.Namespace(
            install=False,
            uninstall=True,
            interval=900,
            json=False,
        )
        rc = cmd_fabrica_heartbeat(args)
        assert rc == 0
        mock_uninstall.assert_called_once()


# ---------------------------------------------------------------------------
# Webhook notification tests
# ---------------------------------------------------------------------------

class TestWebhookNotification:
    @patch("urllib.request.urlopen")
    def test_webhook_sent_on_changes(self, mock_urlopen, monkeypatch):
        from organvm_engine.fabrica.heartbeat import _send_webhook

        monkeypatch.setenv("ORGANVM_HEARTBEAT_WEBHOOK", "https://hooks.example.com/test")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        report = HeartbeatReport(changed=1, polled=1)
        _send_webhook(report)
        mock_urlopen.assert_called_once()

    def test_webhook_skipped_without_env(self, monkeypatch):
        from organvm_engine.fabrica.heartbeat import _send_webhook

        monkeypatch.delenv("ORGANVM_HEARTBEAT_WEBHOOK", raising=False)
        report = HeartbeatReport(changed=1)
        # Should not raise
        _send_webhook(report)

    @patch("urllib.request.urlopen")
    def test_webhook_failure_is_logged_not_raised(self, mock_urlopen, monkeypatch):
        from organvm_engine.fabrica.heartbeat import _send_webhook

        monkeypatch.setenv("ORGANVM_HEARTBEAT_WEBHOOK", "https://hooks.example.com/fail")
        mock_urlopen.side_effect = Exception("Network error")

        report = HeartbeatReport(changed=1)
        # Should not raise
        _send_webhook(report)
