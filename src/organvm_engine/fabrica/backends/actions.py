"""Actions dispatch backend — GitHub Actions workflow_dispatch.

Triggers a ``workflow_dispatch`` event on a repository workflow via
``gh workflow run``. Designed for heavier automation tasks that need
a full CI environment (builds, integration tests, multi-step scripts).

Status polling queries the most recent workflow run to check whether
it has completed, and if so, whether it succeeded.
"""

from __future__ import annotations

import time

from organvm_engine.fabrica.backends._gh import (
    BackendError,
    get_latest_workflow_run,
    trigger_workflow,
)
from organvm_engine.fabrica.models import DispatchRecord, DispatchStatus

BACKEND_NAME = "actions"

_DEFAULT_WORKFLOW = "fabrica-dispatch.yml"


def dispatch(
    task_id: str,
    intent_id: str,
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
    branch: str | None = None,
    dry_run: bool = True,
) -> DispatchRecord:
    """Trigger a workflow_dispatch event on the target repo.

    Args:
        task_id: Atom/task identifier from the planning pipeline.
        intent_id: RelayIntent that authorised this dispatch.
        repo: Owner/repo (e.g. ``meta-organvm/organvm-engine``).
        title: Used as the ``task_title`` workflow input.
        body: Used as the ``task_body`` workflow input.
        labels: Ignored (workflows don't have labels).
        branch: Git ref to run the workflow against (default ``main``).
        dry_run: If True, do not actually trigger the workflow.

    Returns:
        DispatchRecord tracking the dispatched work.
    """
    ref = branch or "main"

    if dry_run:
        return DispatchRecord(
            task_id=task_id,
            intent_id=intent_id,
            backend=BACKEND_NAME,
            target=f"dry-run://{repo}/{_DEFAULT_WORKFLOW}@{ref}",
            status=DispatchStatus.DISPATCHED,
        )

    inputs = {
        "task_id": task_id,
        "intent_id": intent_id,
        "task_title": title,
        "task_body": body,
    }

    try:
        trigger_workflow(
            repo=repo,
            workflow=_DEFAULT_WORKFLOW,
            ref=ref,
            inputs=inputs,
        )
    except BackendError as exc:
        return DispatchRecord(
            task_id=task_id,
            intent_id=intent_id,
            backend=BACKEND_NAME,
            target=f"error://{repo}/{_DEFAULT_WORKFLOW}",
            status=DispatchStatus.REJECTED,
            verdict=str(exc),
        )

    # After triggering, attempt to get the run ID for tracking
    run = get_latest_workflow_run(repo, _DEFAULT_WORKFLOW)
    target = run["url"] if run else f"https://github.com/{repo}/actions"

    return DispatchRecord(
        task_id=task_id,
        intent_id=intent_id,
        backend=BACKEND_NAME,
        target=target,
        status=DispatchStatus.DISPATCHED,
        dispatched_at=time.time(),
    )


def check_status(record: DispatchRecord) -> DispatchRecord:
    """Poll the workflow run for completion.

    Returns a new DispatchRecord with updated status.
    """
    if record.target.startswith("dry-run://") or record.target.startswith("error://"):
        return record

    # Extract repo from target URL
    repo = _extract_repo_from_url(record.target)
    if repo is None:
        return record

    try:
        run = get_latest_workflow_run(repo, _DEFAULT_WORKFLOW)
    except BackendError:
        return record

    if run is None:
        return record

    new_status = record.status
    returned_at = record.returned_at

    gh_status = run.get("status", "")
    conclusion = run.get("conclusion", "")

    if gh_status == "completed":
        returned_at = returned_at or time.time()
        if conclusion == "success":
            new_status = DispatchStatus.DRAFT_RETURNED
        elif conclusion in ("failure", "cancelled", "timed_out"):
            new_status = DispatchStatus.REJECTED
        else:
            new_status = DispatchStatus.DRAFT_RETURNED
    elif gh_status in ("in_progress", "queued", "waiting"):
        new_status = DispatchStatus.IN_PROGRESS

    return DispatchRecord(
        id=record.id,
        task_id=record.task_id,
        intent_id=record.intent_id,
        backend=BACKEND_NAME,
        target=record.target,
        status=new_status,
        dispatched_at=record.dispatched_at,
        returned_at=returned_at,
        pr_url=record.pr_url,
        verdict=record.verdict,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_repo_from_url(url: str) -> str | None:
    """Extract owner/repo from a GitHub URL.

    Handles:
      https://github.com/owner/repo/actions/runs/12345
      https://github.com/owner/repo/actions
    """
    if "github.com/" not in url:
        return None
    parts = url.split("github.com/", 1)[-1].split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return None
