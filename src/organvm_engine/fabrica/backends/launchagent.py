"""LaunchAgent dispatch backend — macOS plist generation + launchctl.

Generates a macOS LaunchAgent plist that runs a script implementing
the dispatched task. Suitable for persistent background tasks,
scheduled jobs, and filesystem watchers that should survive reboots.

The plist is written to ``~/Library/LaunchAgents/`` and loaded via
``launchctl bootstrap``. Status polling checks whether the agent
is currently loaded.
"""

from __future__ import annotations

import plistlib
import subprocess
import time
from pathlib import Path

from organvm_engine.fabrica.models import DispatchRecord, DispatchStatus

BACKEND_NAME = "launchagent"

_PLIST_DIR = Path.home() / "Library" / "LaunchAgents"
_SCRIPT_DIR = Path.home() / ".organvm" / "fabrica" / "scripts"


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
    """Generate a LaunchAgent plist and load it.

    Args:
        task_id: Atom/task identifier from the planning pipeline.
        intent_id: RelayIntent that authorised this dispatch.
        repo: Ignored (LaunchAgents are system-level).
        title: Used to derive the plist label.
        body: Script content to execute. Must be a valid shell script.
        labels: Ignored.
        branch: Ignored.
        dry_run: If True, generate but do not write or load the plist.

    Returns:
        DispatchRecord tracking the dispatched work.
    """
    label = f"com.organvm.fabrica.{task_id[:8]}"
    plist_path = _PLIST_DIR / f"{label}.plist"
    script_path = _SCRIPT_DIR / f"{task_id[:8]}.sh"

    plist_data = _build_plist(label, script_path, title)

    if dry_run:
        return DispatchRecord(
            task_id=task_id,
            intent_id=intent_id,
            backend=BACKEND_NAME,
            target=f"dry-run://{plist_path}",
            status=DispatchStatus.DISPATCHED,
        )

    # Write the script
    _SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    script_path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n\n{body}\n")
    script_path.chmod(0o755)

    # Write the plist
    _PLIST_DIR.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as f:
        plistlib.dump(plist_data, f)

    # Load the agent
    try:
        _launchctl_bootstrap(plist_path)
    except _LaunchCtlError as exc:
        return DispatchRecord(
            task_id=task_id,
            intent_id=intent_id,
            backend=BACKEND_NAME,
            target=str(plist_path),
            status=DispatchStatus.DISPATCHED,
            verdict=f"launchctl warning: {exc}",
            dispatched_at=time.time(),
        )

    return DispatchRecord(
        task_id=task_id,
        intent_id=intent_id,
        backend=BACKEND_NAME,
        target=str(plist_path),
        status=DispatchStatus.DISPATCHED,
        dispatched_at=time.time(),
    )


def check_status(record: DispatchRecord) -> DispatchRecord:
    """Check whether the LaunchAgent is loaded and running.

    Returns a new DispatchRecord with updated status.
    """
    if record.target.startswith("dry-run://"):
        return record

    plist_path = Path(record.target)
    label = plist_path.stem  # com.organvm.fabrica.<hash>

    loaded = _is_agent_loaded(label)

    new_status = record.status
    returned_at = record.returned_at

    if not plist_path.exists():
        new_status = DispatchStatus.TIMED_OUT
        returned_at = returned_at or time.time()
    elif loaded:
        new_status = DispatchStatus.IN_PROGRESS
    else:
        # Agent was loaded but has exited — treat as draft returned
        new_status = DispatchStatus.DRAFT_RETURNED
        returned_at = returned_at or time.time()

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

class _LaunchCtlError(Exception):
    pass


def _build_plist(label: str, script_path: Path, title: str) -> dict:
    """Build the plist dictionary for a LaunchAgent."""
    log_dir = Path.home() / ".organvm" / "fabrica" / "logs"
    return {
        "Label": label,
        "ProgramArguments": [str(script_path)],
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(log_dir / f"{label}.out.log"),
        "StandardErrorPath": str(log_dir / f"{label}.err.log"),
        "EnvironmentVariables": {
            "FABRICA_TASK_TITLE": title,
        },
    }


def _launchctl_bootstrap(plist_path: Path) -> None:
    """Load a LaunchAgent plist via launchctl.

    Uses ``launchctl bootstrap gui/<uid>`` on macOS 13+ or
    falls back to ``launchctl load`` on older systems.
    """
    import os

    uid = os.getuid()

    # Try modern launchctl bootstrap first
    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode == 0:
        return

    # Fall back to legacy load
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise _LaunchCtlError(result.stderr.strip())


def _is_agent_loaded(label: str) -> bool:
    """Check whether a LaunchAgent with the given label is loaded."""
    result = subprocess.run(
        ["launchctl", "list"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        return False
    return any(label in line for line in result.stdout.splitlines())
