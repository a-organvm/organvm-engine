"""Claude dispatch backend — worktree-isolated Claude Code subagent.

Spawns a Claude Code session in a git worktree so the main branch
stays clean while the agent works. The worktree is created under
``<repo>/.worktrees/fabrica-<task_id[:8]>/`` and the agent runs
with a prompt derived from the task body.

Status is tracked through the existence of the worktree and any
commits or branches it produces.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from organvm_engine.fabrica.models import DispatchRecord, DispatchStatus

BACKEND_NAME = "claude"


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
    """Spawn a Claude Code subagent in a worktree.

    Args:
        task_id: Atom/task identifier from the planning pipeline.
        intent_id: RelayIntent that authorised this dispatch.
        repo: Filesystem path to the git repository (not owner/repo).
        title: Summary passed to the agent prompt.
        body: Full specification passed to the agent prompt.
        labels: Ignored.
        branch: Branch name for the worktree (default derived from task_id).
        dry_run: If True, do not create worktree or spawn agent.

    Returns:
        DispatchRecord tracking the dispatched work.
    """
    repo_path = Path(repo).expanduser()
    branch_name = branch or f"fabrica/{task_id[:8]}"
    worktree_path = repo_path / ".worktrees" / f"fabrica-{task_id[:8]}"

    if dry_run:
        return DispatchRecord(
            task_id=task_id,
            intent_id=intent_id,
            backend=BACKEND_NAME,
            target=f"dry-run://{worktree_path}",
            status=DispatchStatus.DISPATCHED,
        )

    # Create the worktree
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git(repo_path, ["worktree", "add", "-b", branch_name, str(worktree_path)])
    except _GitError as exc:
        # Branch may already exist — try without -b
        try:
            _git(repo_path, ["worktree", "add", str(worktree_path), branch_name])
        except _GitError:
            return DispatchRecord(
                task_id=task_id,
                intent_id=intent_id,
                backend=BACKEND_NAME,
                target=str(worktree_path),
                status=DispatchStatus.REJECTED,
                verdict=f"Failed to create worktree: {exc}",
            )

    # Write the agent prompt to the worktree
    prompt_path = worktree_path / ".fabrica-prompt.md"
    prompt_path.write_text(
        f"# Fabrica Dispatch: {title}\n\n"
        f"**task_id**: `{task_id}`\n"
        f"**intent_id**: `{intent_id}`\n\n"
        f"## Specification\n\n{body}\n\n"
        f"## Instructions\n\n"
        f"Implement the specification above in this worktree. "
        f"Commit your work when done. Do not push.\n",
    )

    # Spawn the Claude Code agent asynchronously
    try:
        _spawn_claude_agent(worktree_path, prompt_path)
    except _AgentError as exc:
        return DispatchRecord(
            task_id=task_id,
            intent_id=intent_id,
            backend=BACKEND_NAME,
            target=str(worktree_path),
            status=DispatchStatus.DISPATCHED,
            verdict=f"Agent spawn warning: {exc}",
            dispatched_at=time.time(),
        )

    return DispatchRecord(
        task_id=task_id,
        intent_id=intent_id,
        backend=BACKEND_NAME,
        target=str(worktree_path),
        status=DispatchStatus.DISPATCHED,
        dispatched_at=time.time(),
    )


def check_status(record: DispatchRecord) -> DispatchRecord:
    """Check whether the worktree has new commits.

    Looks for commits on the worktree's branch that are ahead of
    the base branch. If commits exist, the task is considered
    DRAFT_RETURNED and ready for FORTIFY.
    """
    if record.target.startswith("dry-run://"):
        return record

    worktree_path = Path(record.target)
    if not worktree_path.exists():
        return DispatchRecord(
            id=record.id,
            task_id=record.task_id,
            intent_id=record.intent_id,
            backend=BACKEND_NAME,
            target=record.target,
            status=DispatchStatus.TIMED_OUT,
            dispatched_at=record.dispatched_at,
            returned_at=time.time(),
            verdict="Worktree no longer exists",
        )

    # Check for commits ahead of main
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "main..HEAD"],
            capture_output=True,
            text=True,
            cwd=worktree_path,
            timeout=10,
            check=False,
        )
        commits = [line for line in result.stdout.strip().splitlines() if line]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return record

    new_status = record.status
    returned_at = record.returned_at

    if commits:
        new_status = DispatchStatus.DRAFT_RETURNED
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
        pr_url=record.pr_url,
        verdict=record.verdict,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _GitError(Exception):
    pass


class _AgentError(Exception):
    pass


def _git(cwd: Path, args: list[str]) -> str:
    """Run a git command in the given directory."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise _GitError(result.stderr.strip())
    return result.stdout.strip()


def _spawn_claude_agent(worktree_path: Path, prompt_path: Path) -> None:
    """Spawn a Claude Code process in the background.

    The agent reads the prompt file and works in the worktree directory.
    Uses ``claude --print`` with the prompt piped via stdin for
    non-interactive execution.
    """
    prompt_text = prompt_path.read_text()

    try:
        subprocess.Popen(
            ["claude", "--print", "--dangerously-skip-permissions"],
            cwd=worktree_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        ).communicate(input=prompt_text.encode(), timeout=1)
    except FileNotFoundError:
        raise _AgentError("claude CLI not found") from None
    except subprocess.TimeoutExpired:
        # Expected — the agent continues in the background after
        # Popen.communicate's timeout. The detached session keeps it alive.
        pass
    except OSError as exc:
        raise _AgentError(f"Failed to spawn agent: {exc}") from exc
