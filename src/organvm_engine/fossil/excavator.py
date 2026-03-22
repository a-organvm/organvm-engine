"""Git history crawler — walks repos and yields classified FossilRecord objects.

Reconstructs fossil records from git log output, classifying each commit
with Jungian archetypes and assigning it to a named epoch.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterator

from organvm_engine.fossil.classifier import classify_commit
from organvm_engine.fossil.epochs import assign_epoch
from organvm_engine.fossil.stratum import FossilRecord, Provenance, compute_record_hash
from organvm_engine.organ_config import ORGANS

# ---------------------------------------------------------------------------
# Conventional commit prefix regex
# ---------------------------------------------------------------------------
_CC_PREFIX_RE = re.compile(r"^(\w+)(?:\(.+?\))?[!]?:\s")


def parse_commit_type(message: str) -> str:
    """Extract the conventional commit type prefix from a message.

    Returns:
        The type string (e.g. "feat", "fix", "chore") if a conventional prefix
        is found. Returns "merge" for messages starting with "Merge ",
        "revert" for messages starting with "Revert ", and "" otherwise.
    """
    if re.match(r"^Merge\b", message):
        return "merge"
    if re.match(r"^Revert\b", message):
        return "revert"
    m = _CC_PREFIX_RE.match(message)
    if m:
        return m.group(1)
    return ""


def parse_numstat(numstat_output: str) -> tuple[int, int, int]:
    """Parse ``git diff --numstat`` output into (files_changed, insertions, deletions).

    Each line has the form ``<add>\\t<del>\\t<path>``. The add/del columns may
    be ``-`` for binary files, which are counted as a changed file but
    contribute 0 to insertion/deletion totals.

    Returns:
        (files_changed, insertions, deletions)
    """
    files = 0
    insertions = 0
    deletions = 0
    for line in numstat_output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        files += 1
        add_raw, del_raw = parts[0], parts[1]
        insertions += 0 if add_raw == "-" else int(add_raw)
        deletions += 0 if del_raw == "-" else int(del_raw)
    return files, insertions, deletions


def detect_organ_from_path(repo_path: Path, workspace_root: Path) -> str:
    """Determine the organ short key from the repo path relative to the workspace root.

    Matches the first path component against the ``dir`` field of each entry
    in :data:`organvm_engine.organ_config.ORGANS`.

    Args:
        repo_path: Absolute path to the repo directory.
        workspace_root: Absolute path to the workspace root.

    Returns:
        An organ short key (e.g. "I", "META", "LIMINAL") or "UNKNOWN" if the
        directory does not match any known organ.
    """
    try:
        rel = repo_path.relative_to(workspace_root)
    except ValueError:
        return "UNKNOWN"

    parts = rel.parts
    if not parts:
        return "UNKNOWN"

    top_dir = parts[0]
    # Build a reverse map: dir name → organ key
    dir_to_key: dict[str, str] = {meta["dir"]: key for key, meta in ORGANS.items()}
    return dir_to_key.get(top_dir, "UNKNOWN")


def excavate_repo(
    repo_path: Path,
    *,
    workspace_root: Path,
    since: str | None = None,
    existing_shas: frozenset[str] | None = None,
) -> Iterator[FossilRecord]:
    """Walk a git repo and yield classified FossilRecord objects in chronological order.

    Runs ``git log --reverse`` to obtain commits oldest-first, then for each
    new commit fetches ``git diff --numstat`` statistics, classifies the commit
    with Jungian archetypes, and assigns it to a named epoch.

    Args:
        repo_path: Absolute path to the git repo.
        workspace_root: Workspace root (used for organ detection).
        since: Optional ``--since`` argument forwarded to ``git log``
            (e.g. ``"2026-01-01"``).
        existing_shas: SHAs to skip (already in the record store).

    Yields:
        :class:`~organvm_engine.fossil.stratum.FossilRecord` objects in
        ascending timestamp order.
    """
    if existing_shas is None:
        existing_shas = frozenset()

    repo_name = repo_path.name
    organ = detect_organ_from_path(repo_path, workspace_root)

    # Build git log command
    log_cmd = [
        "git",
        "log",
        "--reverse",
        "--format=%H|%aI|%an|%s",
    ]
    if since:
        log_cmd.append(f"--since={since}")

    try:
        log_result = subprocess.run(
            log_cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return

    prev_hash = ""
    from datetime import datetime

    for raw_line in log_result.stdout.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        parts = raw_line.split("|", 3)
        if len(parts) < 4:
            continue

        sha, ts_raw, author, message = parts[0], parts[1], parts[2], parts[3]

        if sha in existing_shas:
            continue

        # Parse ISO 8601 timestamp
        try:
            timestamp = datetime.fromisoformat(ts_raw)
        except ValueError:
            continue

        # Get numstat — handle first commit (no parent)
        numstat_output = ""
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--numstat", f"{sha}^..{sha}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            numstat_output = diff_result.stdout
        except subprocess.CalledProcessError:
            # First commit has no parent — diff against empty tree
            try:
                diff_result = subprocess.run(
                    ["git", "diff", "--numstat", f"{sha}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                numstat_output = diff_result.stdout
            except (subprocess.CalledProcessError, FileNotFoundError):
                numstat_output = ""

        files_changed, insertions, deletions = parse_numstat(numstat_output)
        conventional_type = parse_commit_type(message)
        archetypes = classify_commit(message, conventional_type, repo_name, organ)
        epoch_obj = assign_epoch(timestamp)
        epoch_id = epoch_obj.id if epoch_obj is not None else None
        tags: list[str] = []

        record = FossilRecord(
            commit_sha=sha,
            timestamp=timestamp,
            author=author,
            organ=organ,
            repo=repo_name,
            message=message,
            conventional_type=conventional_type,
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
            archetypes=archetypes,
            provenance=Provenance.RECONSTRUCTED,
            session_id=None,
            epoch=epoch_id,
            tags=tags,
            prev_hash=prev_hash,
        )
        prev_hash = compute_record_hash(record)
        yield record
