"""Human dispatch backend — GitHub issue tagged needs-review.

Creates a GitHub issue with the ``needs-review`` label to signal that
the task requires human attention rather than automated agent execution.
Used for tasks that exceed agent capability, require subjective
judgement, or involve sensitive operations.

The FORTIFY phase for human-dispatched tasks is the human review itself:
close the issue (REJECTED) or merge the linked PR (MERGED).
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

BACKEND_NAME = "human"

_DEFAULT_LABELS = ["needs-review", "fabrica:dispatch"]


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
    """Create a GitHub issue tagged needs-review for human attention.

    Args:
        task_id: Atom/task identifier from the planning pipeline.
        intent_id: RelayIntent that authorised this dispatch.
        repo: Owner/repo (e.g. ``meta-organvm/organvm-engine``).
        title: Issue title.
        body: Issue body with full context for the human reviewer.
        labels: Extra labels beyond the defaults.
        branch: Optional branch reference for the reviewer.
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

    branch_ref = f"\n\n**Branch**: `{branch}`" if branch else ""

    issue = create_issue(
        repo=repo,
        title=f"[review] {title}",
        body=_build_body(body, task_id, intent_id, branch_ref),
        labels=all_labels,
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
    """Poll the issue for human action.

    Human tasks transition when:
    - The issue is closed → FORTIFIED (awaiting verdict)
    - A linked PR exists and is merged → MERGED
    - A linked PR exists and is closed → REJECTED
    """
    if record.target.startswith("dry-run://"):
        return record

    repo, issue_number = _parse_issue_url(record.target)
    if repo is None:
        return record

    try:
        issue = get_issue(repo, issue_number)
    except BackendError:
        return record

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
        # Issue closed without a PR — human marked it as done or rejected
        new_status = DispatchStatus.FORTIFIED
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

def _build_body(body: str, task_id: str, intent_id: str, branch_ref: str) -> str:
    return (
        f"{body}{branch_ref}\n\n"
        f"---\n"
        f"_Dispatched by ORGANVM fabrica (Cyclic Dispatch Protocol)_\n"
        f"- **task_id**: `{task_id}`\n"
        f"- **intent_id**: `{intent_id}`\n"
        f"- **backend**: `{BACKEND_NAME}`\n"
        f"- **action**: Human review required\n"
    )


def _parse_issue_url(url: str) -> tuple[str | None, int]:
    parts = url.rstrip("/").split("/")
    try:
        idx = parts.index("issues")
        number = int(parts[idx + 1])
        owner = parts[idx - 2]
        repo = parts[idx - 1]
        return f"{owner}/{repo}", number
    except (ValueError, IndexError):
        return None, 0
