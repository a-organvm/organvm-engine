"""Check upstream PR status for contribution repos.

Uses the GitHub CLI (``gh``) to query PR state without requiring a token
in the environment — leverages the user's existing ``gh auth`` session.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from enum import Enum

from organvm_engine.contrib.discover import ContribRepo


class PRState(Enum):
    """Upstream PR state."""

    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
    UNKNOWN = "unknown"
    NO_PR = "no_pr"


@dataclass
class ContribStatus:
    """Status of a contribution repo's upstream PR."""

    repo: ContribRepo
    state: PRState
    title: str = ""
    review_decision: str = ""
    mergeable: str = ""
    checks_passing: bool | None = None
    updated_at: str = ""
    labels: list[str] | None = None

    @property
    def is_actionable(self) -> bool:
        """True if the PR needs attention (review requested, changes needed)."""
        return self.state == PRState.OPEN and self.review_decision in (
            "CHANGES_REQUESTED",
            "REVIEW_REQUIRED",
        )

    @property
    def is_landed(self) -> bool:
        """True if the contribution was accepted upstream."""
        return self.state == PRState.MERGED


def check_pr_status(repo: ContribRepo) -> ContribStatus:
    """Check the upstream PR status for a contrib repo.

    Args:
        repo: ContribRepo with target_repo and target_pr set.

    Returns:
        ContribStatus with current state from GitHub.
    """
    if repo.target_pr is None:
        return ContribStatus(repo=repo, state=PRState.NO_PR)

    pr_url = f"https://github.com/{repo.target_repo}/pull/{repo.target_pr}"

    try:
        result = subprocess.run(
            [
                "gh", "pr", "view", pr_url,
                "--json", "state,title,reviewDecision,mergeable,statusCheckRollup,updatedAt,labels",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ContribStatus(repo=repo, state=PRState.UNKNOWN)

    if result.returncode != 0:
        return ContribStatus(repo=repo, state=PRState.UNKNOWN)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ContribStatus(repo=repo, state=PRState.UNKNOWN)

    state_str = data.get("state", "").upper()
    if state_str == "MERGED":
        state = PRState.MERGED
    elif state_str == "CLOSED":
        state = PRState.CLOSED
    elif state_str == "OPEN":
        state = PRState.OPEN
    else:
        state = PRState.UNKNOWN

    # Check if all status checks pass
    checks = data.get("statusCheckRollup", [])
    checks_passing = None
    if checks:
        checks_passing = all(
            c.get("conclusion") == "SUCCESS" or c.get("state") == "SUCCESS"
            for c in checks
            if c.get("conclusion") or c.get("state")
        )

    labels = [lbl.get("name", "") for lbl in data.get("labels", [])]

    return ContribStatus(
        repo=repo,
        state=state,
        title=data.get("title", ""),
        review_decision=data.get("reviewDecision", "") or "",
        mergeable=data.get("mergeable", ""),
        checks_passing=checks_passing,
        updated_at=data.get("updatedAt", ""),
        labels=labels,
    )


def check_all_statuses(repos: list[ContribRepo]) -> list[ContribStatus]:
    """Check status for all contrib repos. Sequential to respect rate limits."""
    return [check_pr_status(repo) for repo in repos if repo.target_pr is not None]
