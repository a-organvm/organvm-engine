"""Tests for fabrica dispatch backends (SPEC-024 Phase 3).

Backend modules are tested in dry-run mode (no real GitHub API calls)
and with mocked subprocess for integration paths. Each backend must
produce a valid DispatchRecord and handle status checks gracefully.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from organvm_engine.fabrica.backends import VALID_BACKENDS, get_backend
from organvm_engine.fabrica.models import DispatchRecord, DispatchStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_fabrica(tmp_path, monkeypatch):
    """Redirect all fabrica I/O to a temp directory."""
    monkeypatch.setenv("ORGANVM_FABRICA_DIR", str(tmp_path / "fabrica"))


# ---------------------------------------------------------------------------
# Backend registry tests
# ---------------------------------------------------------------------------

class TestBackendRegistry:
    def test_all_six_backends_registered(self):
        expected = frozenset({
            "copilot", "jules", "actions", "claude", "launchagent", "human",
        })
        assert expected == VALID_BACKENDS

    def test_get_backend_returns_module(self):
        for name in VALID_BACKENDS:
            backend = get_backend(name)
            assert hasattr(backend, "dispatch")
            assert hasattr(backend, "check_status")
            assert hasattr(backend, "BACKEND_NAME")
            assert name == backend.BACKEND_NAME

    def test_get_backend_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown backend"):
            get_backend("nonexistent")


# ---------------------------------------------------------------------------
# Copilot backend
# ---------------------------------------------------------------------------

class TestCopilotBackend:
    def test_dry_run_dispatch(self):
        backend = get_backend("copilot")
        record = backend.dispatch(
            task_id="task001",
            intent_id="intent001",
            repo="meta-organvm/organvm-engine",
            title="Test task",
            body="Implement the thing",
            dry_run=True,
        )
        assert isinstance(record, DispatchRecord)
        assert record.backend == "copilot"
        assert record.status == DispatchStatus.DISPATCHED
        assert record.target.startswith("dry-run://")

    def test_dry_run_check_status_noop(self):
        backend = get_backend("copilot")
        record = DispatchRecord(
            task_id="t1", intent_id="i1", backend="copilot",
            target="dry-run://meta-organvm/organvm-engine",
        )
        updated = backend.check_status(record)
        assert updated.status == record.status

    @patch("organvm_engine.fabrica.backends.copilot.create_issue")
    def test_live_dispatch_creates_issue(self, mock_create):
        from organvm_engine.fabrica.backends._gh import GHIssue

        mock_create.return_value = GHIssue(
            number=42,
            url="https://github.com/meta-organvm/organvm-engine/issues/42",
            state="OPEN",
            title="[fabrica] Test task",
        )
        backend = get_backend("copilot")
        record = backend.dispatch(
            task_id="task002",
            intent_id="intent002",
            repo="meta-organvm/organvm-engine",
            title="Test task",
            body="Implement the thing",
            dry_run=False,
        )
        assert record.backend == "copilot"
        assert record.status == DispatchStatus.DISPATCHED
        assert "issues/42" in record.target
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert "copilot" in call_kwargs.kwargs.get("assignees", call_kwargs[1].get("assignees", []))


# ---------------------------------------------------------------------------
# Jules backend
# ---------------------------------------------------------------------------

class TestJulesBackend:
    def test_dry_run_dispatch(self):
        backend = get_backend("jules")
        record = backend.dispatch(
            task_id="task010",
            intent_id="intent010",
            repo="meta-organvm/organvm-engine",
            title="Jules test",
            body="Implement via Jules",
            dry_run=True,
        )
        assert record.backend == "jules"
        assert record.status == DispatchStatus.DISPATCHED
        assert record.target.startswith("dry-run://")

    @patch("organvm_engine.fabrica.backends.jules.create_issue")
    def test_live_dispatch_assigns_jules(self, mock_create):
        from organvm_engine.fabrica.backends._gh import GHIssue

        mock_create.return_value = GHIssue(
            number=99,
            url="https://github.com/org/repo/issues/99",
            state="OPEN",
            title="[fabrica] Jules test",
        )
        backend = get_backend("jules")
        record = backend.dispatch(
            task_id="task011",
            intent_id="intent011",
            repo="org/repo",
            title="Jules test",
            body="spec",
            dry_run=False,
        )
        assert record.backend == "jules"
        call_kwargs = mock_create.call_args
        assignees = call_kwargs.kwargs.get("assignees", call_kwargs[1].get("assignees", []))
        assert "jules-google" in assignees


# ---------------------------------------------------------------------------
# Actions backend
# ---------------------------------------------------------------------------

class TestActionsBackend:
    def test_dry_run_dispatch(self):
        backend = get_backend("actions")
        record = backend.dispatch(
            task_id="task020",
            intent_id="intent020",
            repo="meta-organvm/organvm-engine",
            title="Actions test",
            body="Run the workflow",
            dry_run=True,
        )
        assert record.backend == "actions"
        assert record.status == DispatchStatus.DISPATCHED
        assert "dry-run://" in record.target
        assert "fabrica-dispatch.yml" in record.target

    @patch("organvm_engine.fabrica.backends.actions.get_latest_workflow_run")
    @patch("organvm_engine.fabrica.backends.actions.trigger_workflow")
    def test_live_dispatch_triggers_workflow(self, mock_trigger, mock_run):
        mock_trigger.return_value = ""
        mock_run.return_value = {
            "databaseId": 12345,
            "status": "queued",
            "conclusion": None,
            "url": "https://github.com/org/repo/actions/runs/12345",
        }
        backend = get_backend("actions")
        record = backend.dispatch(
            task_id="task021",
            intent_id="intent021",
            repo="org/repo",
            title="Actions test",
            body="Run it",
            dry_run=False,
        )
        assert record.backend == "actions"
        assert record.status == DispatchStatus.DISPATCHED
        mock_trigger.assert_called_once()

    def test_check_status_dry_run_noop(self):
        backend = get_backend("actions")
        record = DispatchRecord(
            task_id="t", intent_id="i", backend="actions",
            target="dry-run://org/repo/fabrica-dispatch.yml@main",
        )
        updated = backend.check_status(record)
        assert updated.status == record.status

    @patch("organvm_engine.fabrica.backends.actions.get_latest_workflow_run")
    def test_check_status_completed_success(self, mock_run):
        mock_run.return_value = {
            "status": "completed",
            "conclusion": "success",
            "url": "https://github.com/org/repo/actions/runs/123",
        }
        backend = get_backend("actions")
        record = DispatchRecord(
            task_id="t", intent_id="i", backend="actions",
            target="https://github.com/org/repo/actions/runs/123",
            status=DispatchStatus.IN_PROGRESS,
        )
        updated = backend.check_status(record)
        assert updated.status == DispatchStatus.DRAFT_RETURNED

    @patch("organvm_engine.fabrica.backends.actions.get_latest_workflow_run")
    def test_check_status_completed_failure(self, mock_run):
        mock_run.return_value = {
            "status": "completed",
            "conclusion": "failure",
            "url": "https://github.com/org/repo/actions/runs/123",
        }
        backend = get_backend("actions")
        record = DispatchRecord(
            task_id="t", intent_id="i", backend="actions",
            target="https://github.com/org/repo/actions/runs/123",
            status=DispatchStatus.IN_PROGRESS,
        )
        updated = backend.check_status(record)
        assert updated.status == DispatchStatus.REJECTED


# ---------------------------------------------------------------------------
# Claude backend
# ---------------------------------------------------------------------------

class TestClaudeBackend:
    def test_dry_run_dispatch(self):
        backend = get_backend("claude")
        record = backend.dispatch(
            task_id="task030",
            intent_id="intent030",
            repo="/tmp/test-repo",
            title="Claude test",
            body="Implement the module",
            dry_run=True,
        )
        assert record.backend == "claude"
        assert record.status == DispatchStatus.DISPATCHED
        assert record.target.startswith("dry-run://")

    def test_check_status_dry_run_noop(self):
        backend = get_backend("claude")
        record = DispatchRecord(
            task_id="t", intent_id="i", backend="claude",
            target="dry-run:///tmp/worktree",
        )
        updated = backend.check_status(record)
        assert updated.status == record.status

    def test_check_status_missing_worktree(self):
        backend = get_backend("claude")
        record = DispatchRecord(
            task_id="t", intent_id="i", backend="claude",
            target="/nonexistent/worktree/path",
            status=DispatchStatus.IN_PROGRESS,
        )
        updated = backend.check_status(record)
        assert updated.status == DispatchStatus.TIMED_OUT


# ---------------------------------------------------------------------------
# LaunchAgent backend
# ---------------------------------------------------------------------------

class TestLaunchAgentBackend:
    def test_dry_run_dispatch(self):
        backend = get_backend("launchagent")
        record = backend.dispatch(
            task_id="task040",
            intent_id="intent040",
            repo="ignored",
            title="LaunchAgent test",
            body="echo hello world",
            dry_run=True,
        )
        assert record.backend == "launchagent"
        assert record.status == DispatchStatus.DISPATCHED
        assert record.target.startswith("dry-run://")

    def test_check_status_dry_run_noop(self):
        backend = get_backend("launchagent")
        record = DispatchRecord(
            task_id="t", intent_id="i", backend="launchagent",
            target="dry-run:///path/to/plist",
        )
        updated = backend.check_status(record)
        assert updated.status == record.status


# ---------------------------------------------------------------------------
# Human backend
# ---------------------------------------------------------------------------

class TestHumanBackend:
    def test_dry_run_dispatch(self):
        backend = get_backend("human")
        record = backend.dispatch(
            task_id="task050",
            intent_id="intent050",
            repo="meta-organvm/organvm-engine",
            title="Human review needed",
            body="Please review this design decision",
            dry_run=True,
        )
        assert record.backend == "human"
        assert record.status == DispatchStatus.DISPATCHED
        assert record.target.startswith("dry-run://")

    @patch("organvm_engine.fabrica.backends.human.create_issue")
    def test_live_dispatch_uses_needs_review_label(self, mock_create):
        from organvm_engine.fabrica.backends._gh import GHIssue

        mock_create.return_value = GHIssue(
            number=7,
            url="https://github.com/org/repo/issues/7",
            state="OPEN",
            title="[review] Human review",
        )
        backend = get_backend("human")
        record = backend.dispatch(
            task_id="task051",
            intent_id="intent051",
            repo="org/repo",
            title="Human review",
            body="Review this",
            dry_run=False,
        )
        assert record.backend == "human"
        call_kwargs = mock_create.call_args
        labels = call_kwargs.kwargs.get("labels", call_kwargs[1].get("labels", []))
        assert "needs-review" in labels


# ---------------------------------------------------------------------------
# Cross-backend integration
# ---------------------------------------------------------------------------

class TestBackendIntegration:
    @pytest.mark.parametrize("backend_name", sorted(VALID_BACKENDS))
    def test_all_backends_produce_valid_dispatch_record(self, backend_name):
        """Every backend's dry-run dispatch returns a valid DispatchRecord."""
        backend = get_backend(backend_name)
        record = backend.dispatch(
            task_id="cross-test",
            intent_id="cross-intent",
            repo="meta-organvm/organvm-engine",
            title="Cross-backend test",
            body="Test body",
            dry_run=True,
        )
        assert isinstance(record, DispatchRecord)
        assert record.backend == backend_name
        assert record.task_id == "cross-test"
        assert record.intent_id == "cross-intent"
        assert record.status == DispatchStatus.DISPATCHED

    @pytest.mark.parametrize("backend_name", sorted(VALID_BACKENDS))
    def test_all_backends_handle_dry_run_status_check(self, backend_name):
        """Every backend's check_status handles dry-run records without error."""
        backend = get_backend(backend_name)
        record = DispatchRecord(
            task_id="t", intent_id="i", backend=backend_name,
            target="dry-run://test",
        )
        updated = backend.check_status(record)
        assert isinstance(updated, DispatchRecord)
