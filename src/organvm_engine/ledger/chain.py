"""Hash computation and chain verification for the Testament Protocol.

Each event's hash is computed over all fields (excluding ``hash`` itself),
using SHA-256 on the canonical JSON serialization (sorted keys, no whitespace).
The chain invariant: event[n].prev_hash == event[n-1].hash.
"""

from __future__ import annotations

import hashlib
import json as _json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GENESIS_PREV_HASH = "sha256:" + "0" * 64


def compute_event_hash(event: dict[str, Any]) -> str:
    """Compute SHA-256 hash of an event, excluding the hash field itself.

    Args:
        event: Event dict. The 'hash' key, if present, is excluded.

    Returns:
        Hash string in format ``sha256:<64 hex chars>``.
    """
    hashable = {k: v for k, v in event.items() if k != "hash"}
    canonical = _json.dumps(
        hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def verify_hash(event: dict[str, Any]) -> bool:
    """Verify that an event's hash field matches its computed hash."""
    stored = event.get("hash", "")
    if not stored:
        return False
    return compute_event_hash(event) == stored


def verify_chain_link(
    prev_event: dict[str, Any], curr_event: dict[str, Any],
) -> bool:
    """Verify that curr_event.prev_hash == prev_event.hash."""
    return curr_event.get("prev_hash", "") == prev_event.get("hash", "")


# ---------------------------------------------------------------------------
# Full chain verification
# ---------------------------------------------------------------------------

@dataclass
class ChainVerificationResult:
    """Result of a full chain verification."""

    valid: bool = True
    event_count: int = 0
    errors: list[str] = field(default_factory=list)
    last_sequence: int = -1
    last_hash: str = ""


def verify_chain(path: Path | str) -> ChainVerificationResult:
    """Walk the entire chain from genesis, verifying every hash and link.

    Args:
        path: Path to the JSONL chain file.

    Returns:
        ChainVerificationResult with validity status and any errors found.
    """
    path = Path(path)
    result = ChainVerificationResult()

    if not path.is_file():
        return result

    prev_hash = GENESIS_PREV_HASH
    prev_seq = -1

    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            event = _json.loads(line)
        except _json.JSONDecodeError:
            result.valid = False
            result.errors.append(f"Line {lineno}: invalid JSON")
            continue

        result.event_count += 1
        seq = event.get("sequence", -1)

        # Check hash integrity
        if not verify_hash(event):
            result.valid = False
            result.errors.append(
                f"Sequence {seq}: hash mismatch (event tampered)",
            )

        # Check chain link
        if event.get("prev_hash", "") != prev_hash:
            result.valid = False
            result.errors.append(
                f"Sequence {seq}: chain link broken "
                f"(prev_hash != predecessor's hash)",
            )

        # Check sequence monotonicity
        expected_seq = prev_seq + 1
        if seq != expected_seq:
            result.valid = False
            result.errors.append(f"Sequence {seq}: expected {expected_seq}")

        prev_hash = event.get("hash", "")
        prev_seq = seq

    result.last_sequence = prev_seq
    result.last_hash = prev_hash
    return result


def repair_chain(path: Path | str) -> dict[str, Any]:
    """Repair a corrupted chain by recomputing hashes and fixing sequence gaps.

    Walks every event, assigns correct sequence numbers, recomputes prev_hash
    and hash fields. Writes repaired chain to a new file, then replaces the
    original. The original is preserved as ``chain.jsonl.pre-repair``.

    Args:
        path: Path to the JSONL chain file.

    Returns:
        Dict with repair stats: events_read, events_repaired, errors.
    """
    path = Path(path)
    if not path.is_file():
        return {"events_read": 0, "events_repaired": 0, "errors": ["File not found"]}

    events: list[dict[str, Any]] = []
    parse_errors = 0

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(_json.loads(line))
        except _json.JSONDecodeError:
            parse_errors += 1

    if not events:
        return {"events_read": 0, "events_repaired": 0, "errors": ["No events found"]}

    # Repair: reassign sequences and recompute hashes
    repaired = 0
    prev_h = GENESIS_PREV_HASH

    for i, event in enumerate(events):
        changed = False

        if event.get("sequence") != i:
            event["sequence"] = i
            changed = True

        if event.get("prev_hash") != prev_h:
            event["prev_hash"] = prev_h
            changed = True

        # Recompute hash
        new_hash = compute_event_hash(event)
        if event.get("hash") != new_hash:
            event["hash"] = new_hash
            changed = True

        if changed:
            repaired += 1

        prev_h = event["hash"]

    # Write repaired chain
    backup = path.with_suffix(".jsonl.pre-repair")
    if not backup.exists():
        import shutil
        shutil.copy2(path, backup)

    with path.open("w") as f:
        for event in events:
            f.write(_json.dumps(event, separators=(",", ":")) + "\n")

    return {
        "events_read": len(events),
        "events_repaired": repaired,
        "parse_errors": parse_errors,
        "backup": str(backup),
    }
