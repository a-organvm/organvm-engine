"""Append-only engagement ledger for network testament.

The ledger is the raw material of the testament — every genuine
engagement action recorded with full context. Never purged.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.network.schema import EngagementEntry

DEFAULT_LEDGER_PATH = Path.home() / ".organvm" / "network" / "ledger.jsonl"


def log_engagement(
    entry: EngagementEntry,
    ledger_path: Path | None = None,
) -> None:
    """Append an engagement entry to the ledger.

    Creates the ledger file and parent directories if needed.

    Args:
        entry: The engagement action to record.
        ledger_path: Path to ledger file. Defaults to ~/.organvm/network/ledger.jsonl.
    """
    path = ledger_path or DEFAULT_LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(entry.to_dict()) + "\n")


def create_engagement(
    organvm_repo: str,
    external_project: str,
    lens: str,
    action_type: str,
    action_detail: str,
    url: str | None = None,
    outcome: str | None = None,
    tags: list[str] | None = None,
) -> EngagementEntry:
    """Create an EngagementEntry with current timestamp.

    Convenience factory for CLI and MCP tool usage.
    """
    return EngagementEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        organvm_repo=organvm_repo,
        external_project=external_project,
        lens=lens,
        action_type=action_type,
        action_detail=action_detail,
        url=url,
        outcome=outcome,
        tags=tags or [],
    )


def read_ledger(
    ledger_path: Path | None = None,
    repo: str | None = None,
    lens: str | None = None,
    action_type: str | None = None,
    since: str | None = None,
) -> list[EngagementEntry]:
    """Read and optionally filter the engagement ledger.

    Args:
        ledger_path: Path to ledger file.
        repo: Filter by ORGANVM repo name.
        lens: Filter by mirror lens (technical|parallel|kinship).
        action_type: Filter by engagement form (presence|contribution|dialogue|invitation).
        since: ISO 8601 timestamp — only entries after this time.

    Returns:
        List of matching EngagementEntry objects.
    """
    path = ledger_path or DEFAULT_LEDGER_PATH
    if not path.exists():
        return []

    entries: list[EngagementEntry] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entry = EngagementEntry.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                continue

            # Apply filters
            if repo and entry.organvm_repo != repo:
                continue
            if lens and entry.lens != lens:
                continue
            if action_type and entry.action_type != action_type:
                continue
            if since and entry.timestamp < since:
                continue

            entries.append(entry)

    return entries


def ledger_summary(ledger_path: Path | None = None) -> dict:
    """Compute summary statistics from the ledger.

    Returns:
        Dict with total_actions, by_lens, by_form, by_repo, unique_projects,
        earliest, latest.
    """
    entries = read_ledger(ledger_path)
    if not entries:
        return {
            "total_actions": 0,
            "by_lens": {},
            "by_form": {},
            "by_repo": {},
            "unique_projects": 0,
            "earliest": None,
            "latest": None,
        }

    by_lens: dict[str, int] = {}
    by_form: dict[str, int] = {}
    by_repo: dict[str, int] = {}
    projects: set[str] = set()

    for e in entries:
        by_lens[e.lens] = by_lens.get(e.lens, 0) + 1
        by_form[e.action_type] = by_form.get(e.action_type, 0) + 1
        by_repo[e.organvm_repo] = by_repo.get(e.organvm_repo, 0) + 1
        projects.add(e.external_project)

    return {
        "total_actions": len(entries),
        "by_lens": by_lens,
        "by_form": by_form,
        "by_repo": by_repo,
        "unique_projects": len(projects),
        "earliest": entries[0].timestamp,
        "latest": entries[-1].timestamp,
    }
