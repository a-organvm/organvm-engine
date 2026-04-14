"""Copilot dispatch backend — GitHub issue + @copilot assignment.

Creates a GitHub issue in the target repo and assigns it to the
``copilot`` agent. Copilot Workspace then picks up the issue and
produces a PR.

Status polling checks whether a linked PR has appeared and whether
the issue has been closed.
"""

from __future__ import annotations

import time

from organvm_engine.fabrica.backends._gh import (
    BackendError,
    create_issue,
    find_linked_pr,
    get_issue,
)
from organvm_engine.fabrica.models import DispatchRecord, DispatchStatus

BACKEND_NAME = "copilot"

_DEFAULT_LABELS = ["agent:copilot", "fabrica:dispatch"]


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
    """Create a GitHub issue assigned to @copilot.

    Args:
        task_id: Atom/task identifier from the planning pipeline.
        intent_id: RelayIntent that authorised this dispatch.
        repo: Owner/repo (e.g. ``meta-organvm/organvm-engine``).
        title: Issue title.
        body: Issue body (markdown). Should include implementation spec.
        labels: Extra labels beyond the defaults.
        branch: Ignored (Copilot creates its own branch).
        dry_run: If True, do not actually create the issue.

    Returns:
        DispatchRecord tracking the dispatched work.
    """
    all_labels = list(_DEFAULT_LABELS) + (labels or [])

    if dry_run:
        return DispatchRecord(
            task_id=task_id,
            intent_id=intent_id,
            backend=BACKEND_NAME,
            target=f"dry-run://{repo}",
            status=DispatchStatus.DISPATCHED,
        )

    issue = create_issue(
        repo=repo,
        title=f"[fabrica] {title}",
        body=_build_body(body, task_id, intent_id),
        labels=all_labels,
        assignees=["copilot"],
    )

    return DispatchRecord(
        task_id=task_id,
        intent_id=intent_id,
        backend=BACKEND_NAME,
        target=issue.url,
        status=DispatchStatus.DISPATCHED,
        dispatched_at=time.time(),
    )


def check_status(record: DispatchRecord) -> DispatchRecord:
    """Poll the issue and any linked PR for status updates.

    Returns a new DispatchRecord with updated fields.
    """
    if record.target.startswith("dry-run://"):
        return record

    # Extract repo and issue number from the URL
    repo, issue_number = _parse_issue_url(record.target)
    if repo is None:
        return record

    try:
        issue = get_issue(repo, issue_number)
    except BackendError:
        return record

    # Check for a linked PR
    pr = find_linked_pr(repo, issue_number)

    new_status = record.status
    pr_url = record.pr_url
    returned_at = record.returned_at

    if pr is not None:
        pr_url = pr.url
        if pr.state == "MERGED":
            new_status = DispatchStatus.MERGED
            returned_at = returned_at or time.time()
        elif pr.state == "CLOSED":
            new_status = DispatchStatus.REJECTED
            returned_at = returned_at or time.time()
        else:
            new_status = DispatchStatus.DRAFT_RETURNED
    elif issue.state == "CLOSED":
        new_status = DispatchStatus.REJECTED
        returned_at = returned_at or time.time()
    else:
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
        pr_url=pr_url,
        verdict=record.verdict,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_body(body: str, task_id: str, intent_id: str) -> str:
    """Wrap the user-supplied body with fabrica metadata."""
    return (
        f"{body}\n\n"
        f"---\n"
        f"_Dispatched by ORGANVM fabrica (Cyclic Dispatch Protocol)_\n"
        f"- **task_id**: `{task_id}`\n"
        f"- **intent_id**: `{intent_id}`\n"
        f"- **backend**: `{BACKEND_NAME}`\n"
    )


def _parse_issue_url(url: str) -> tuple[str | None, int]:
    """Extract (owner/repo, issue_number) from a GitHub issue URL."""
    # https://github.com/owner/repo/issues/42
    parts = url.rstrip("/").split("/")
    try:
        idx = parts.index("issues")
        number = int(parts[idx + 1])
        owner = parts[idx - 2]
        repo = parts[idx - 1]
        return f"{owner}/{repo}", number
    except (ValueError, IndexError):
        return None, 0
