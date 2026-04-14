"""Shared GitHub CLI helpers for dispatch backends.

Thin wrapper around ``gh`` that backends use to create issues,
assign agents, trigger workflows, and query PR/issue state.
All functions raise ``BackendError`` on failure.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


class BackendError(Exception):
    """Raised when a backend operation fails."""


@dataclass
class GHIssue:
    """Minimal representation of a GitHub issue."""

    number: int
    url: str
    state: str  # "OPEN" | "CLOSED"
    title: str


@dataclass
class GHPullRequest:
    """Minimal representation of a GitHub pull request."""

    number: int
    url: str
    state: str  # "OPEN" | "CLOSED" | "MERGED"
    title: str
    head_branch: str


def _run_gh(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a ``gh`` CLI command and return the result.

    Raises BackendError if the command fails and *check* is True.
    """
    cmd = ["gh", *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        raise BackendError(
            "GitHub CLI (gh) not found. Install it: https://cli.github.com/",
        ) from None
    except subprocess.TimeoutExpired as exc:
        raise BackendError(f"gh command timed out: {' '.join(cmd)}") from exc

    if check and result.returncode != 0:
        raise BackendError(
            f"gh command failed (exit {result.returncode}):\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}",
        )
    return result


def create_issue(
    repo: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
) -> GHIssue:
    """Create a GitHub issue and return its metadata."""
    cmd = [
        "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
    ]
    for label in labels or []:
        cmd.extend(["--label", label])
    for assignee in assignees or []:
        cmd.extend(["--assignee", assignee])
    # Return JSON so we can parse it
    cmd.append("--json")
    cmd.append("number,url,state,title")

    # gh issue create doesn't support --json output, so parse the URL from stdout
    # Actually, gh issue create prints the URL on stdout
    result = _run_gh(["issue", "create", "--repo", repo, "--title", title,
                       "--body", body]
                      + [arg for label in (labels or []) for arg in ("--label", label)]
                      + [arg for assignee in (assignees or []) for arg in ("--assignee", assignee)])

    # gh issue create prints the issue URL on stdout
    url = result.stdout.strip()
    # Extract issue number from URL: https://github.com/org/repo/issues/42
    try:
        number = int(url.rstrip("/").rsplit("/", 1)[-1])
    except (ValueError, IndexError):
        number = 0

    return GHIssue(number=number, url=url, state="OPEN", title=title)


def get_issue(repo: str, number: int) -> GHIssue:
    """Fetch an issue's current state."""
    result = _run_gh([
        "issue", "view", str(number),
        "--repo", repo,
        "--json", "number,url,state,title",
    ])
    data = json.loads(result.stdout)
    return GHIssue(
        number=data["number"],
        url=data["url"],
        state=data["state"],
        title=data["title"],
    )


def find_linked_pr(repo: str, issue_number: int) -> GHPullRequest | None:
    """Find a PR that references the given issue number.

    Searches for PRs whose body or title mentions ``#<number>``.
    Returns None if no linked PR is found.
    """
    result = _run_gh([
        "pr", "list",
        "--repo", repo,
        "--search", f"#{issue_number}",
        "--json", "number,url,state,title,headRefName",
        "--limit", "1",
    ], check=False)

    if result.returncode != 0 or not result.stdout.strip():
        return None

    prs = json.loads(result.stdout)
    if not prs:
        return None

    pr = prs[0]
    return GHPullRequest(
        number=pr["number"],
        url=pr["url"],
        state=pr["state"],
        title=pr["title"],
        head_branch=pr.get("headRefName", ""),
    )


def trigger_workflow(
    repo: str,
    workflow: str,
    ref: str = "main",
    inputs: dict[str, str] | None = None,
) -> str:
    """Trigger a workflow_dispatch event and return a confirmation string.

    Args:
        repo: Owner/repo string.
        workflow: Workflow filename or ID.
        ref: Git ref to run against.
        inputs: Key-value pairs passed as workflow inputs.

    Returns:
        The stdout from ``gh workflow run``.
    """
    cmd = [
        "workflow", "run", workflow,
        "--repo", repo,
        "--ref", ref,
    ]
    for key, val in (inputs or {}).items():
        cmd.extend(["--field", f"{key}={val}"])

    result = _run_gh(cmd)
    return result.stdout.strip()


def get_latest_workflow_run(repo: str, workflow: str) -> dict | None:
    """Get the most recent run of a workflow.

    Returns a dict with id, status, conclusion, url, or None.
    """
    result = _run_gh([
        "run", "list",
        "--repo", repo,
        "--workflow", workflow,
        "--limit", "1",
        "--json", "databaseId,status,conclusion,url",
    ], check=False)

    if result.returncode != 0 or not result.stdout.strip():
        return None

    runs = json.loads(result.stdout)
    if not runs:
        return None

    return runs[0]
