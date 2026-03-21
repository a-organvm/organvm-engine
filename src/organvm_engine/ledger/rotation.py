"""Chain file rotation and index management.

When chain.jsonl exceeds a configurable size threshold (default 100 MB),
rotate it to ``chain.YYYYMMDD-HHMMSS.jsonl`` and start a fresh file.
A ``chain-index.json`` manifest tracks all rotated files with their
entry count and date range for O(1) lookups.

Implements: GitHub issue #56
"""

from __future__ import annotations

import json as _json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# 100 MB default threshold
DEFAULT_MAX_BYTES: int = 100 * 1024 * 1024


@dataclass
class RotatedSegment:
    """Metadata for a single rotated chain file."""

    filename: str
    entry_count: int = 0
    first_sequence: int = -1
    last_sequence: int = -1
    first_timestamp: str = ""
    last_timestamp: str = ""
    last_hash: str = ""
    byte_size: int = 0


@dataclass
class ChainIndex:
    """Manifest of all rotated chain segments plus the active file."""

    segments: list[RotatedSegment] = field(default_factory=list)
    active_file: str = "chain.jsonl"
    total_events: int = 0

    def to_dict(self) -> dict:
        return {
            "segments": [asdict(s) for s in self.segments],
            "active_file": self.active_file,
            "total_events": self.total_events,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChainIndex:
        segments = [
            RotatedSegment(**s) for s in data.get("segments", [])
        ]
        return cls(
            segments=segments,
            active_file=data.get("active_file", "chain.jsonl"),
            total_events=data.get("total_events", 0),
        )


def _index_path(chain_dir: Path) -> Path:
    """Return the path to chain-index.json in the given directory."""
    return chain_dir / "chain-index.json"


def load_index(chain_dir: Path) -> ChainIndex:
    """Load the chain index from disk, or return a fresh empty index."""
    idx_path = _index_path(chain_dir)
    if idx_path.is_file():
        try:
            data = _json.loads(idx_path.read_text(encoding="utf-8"))
            return ChainIndex.from_dict(data)
        except (_json.JSONDecodeError, TypeError, KeyError):
            logger.warning("Corrupt chain-index.json; rebuilding")
    return ChainIndex()


def save_index(chain_dir: Path, index: ChainIndex) -> None:
    """Persist the chain index to disk."""
    idx_path = _index_path(chain_dir)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(
        _json.dumps(index.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _scan_segment(path: Path) -> RotatedSegment:
    """Read a JSONL chain file and extract segment metadata."""
    seg = RotatedSegment(filename=path.name, byte_size=path.stat().st_size)
    first_ts: str | None = None
    last_ts: str | None = None
    first_seq: int | None = None
    last_seq: int | None = None
    last_hash = ""

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = _json.loads(line)
        except _json.JSONDecodeError:
            continue

        seg.entry_count += 1
        seq = event.get("sequence", -1)
        ts = event.get("timestamp", "")
        h = event.get("hash", "")

        if first_seq is None:
            first_seq = seq
        last_seq = seq

        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        if h:
            last_hash = h

    seg.first_sequence = first_seq if first_seq is not None else -1
    seg.last_sequence = last_seq if last_seq is not None else -1
    seg.first_timestamp = first_ts or ""
    seg.last_timestamp = last_ts or ""
    seg.last_hash = last_hash
    return seg


def needs_rotation(chain_path: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> bool:
    """Check whether the active chain file exceeds the rotation threshold."""
    if not chain_path.is_file():
        return False
    return chain_path.stat().st_size >= max_bytes


def rotate_chain(
    chain_path: Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    now: datetime | None = None,
) -> RotatedSegment | None:
    """Rotate the active chain file if it exceeds the size threshold.

    The current ``chain.jsonl`` is renamed to
    ``chain.YYYYMMDD-HHMMSS.jsonl``, a fresh empty ``chain.jsonl``
    is created, and the chain index is updated.

    Args:
        chain_path: Path to the active chain.jsonl.
        max_bytes:  Rotation threshold in bytes (default 100 MB).
        now:        Override for the rotation timestamp (testing).

    Returns:
        The RotatedSegment metadata if rotation occurred, None otherwise.
    """
    if not needs_rotation(chain_path, max_bytes):
        return None

    ts = now or datetime.now(timezone.utc)
    stamp = ts.strftime("%Y%m%d-%H%M%S")
    rotated_name = f"chain.{stamp}.jsonl"
    rotated_path = chain_path.parent / rotated_name

    # Avoid collisions (two rotations in the same second)
    suffix = 1
    while rotated_path.exists():
        rotated_name = f"chain.{stamp}-{suffix}.jsonl"
        rotated_path = chain_path.parent / rotated_name
        suffix += 1

    # Rename active -> rotated
    chain_path.rename(rotated_path)

    # Create a fresh empty chain.jsonl
    chain_path.touch()

    # Scan the rotated file for metadata
    segment = _scan_segment(rotated_path)

    # Update the index
    chain_dir = chain_path.parent
    index = load_index(chain_dir)
    index.segments.append(segment)
    index.total_events = sum(s.entry_count for s in index.segments)
    save_index(chain_dir, index)

    logger.info(
        "Rotated chain: %s (%d events, %d bytes)",
        rotated_name,
        segment.entry_count,
        segment.byte_size,
    )
    return segment


def rebuild_index(chain_dir: Path) -> ChainIndex:
    """Rebuild chain-index.json by scanning all chain files on disk.

    Discovers rotated segment files (``chain.*.jsonl``) and the active
    ``chain.jsonl``, recomputes entry counts and date ranges, and writes
    a fresh index.

    Args:
        chain_dir: Directory containing chain.jsonl and rotated segments.

    Returns:
        The rebuilt ChainIndex.
    """
    index = ChainIndex()

    # Find all rotated segments (chain.YYYYMMDD-HHMMSS.jsonl)
    rotated_files = sorted(chain_dir.glob("chain.*.jsonl"))
    for rpath in rotated_files:
        seg = _scan_segment(rpath)
        index.segments.append(seg)

    # Count active file events too
    active_path = chain_dir / "chain.jsonl"
    active_count = 0
    if active_path.is_file():
        for line in active_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                _json.loads(line)
                active_count += 1
            except _json.JSONDecodeError:
                continue

    index.total_events = sum(s.entry_count for s in index.segments) + active_count
    save_index(chain_dir, index)
    return index


def all_chain_files(chain_dir: Path) -> list[Path]:
    """Return all chain files in chronological order (rotated first, active last).

    Ordering uses the chain index when available (preserves insertion
    order), falling back to lexicographic filename sort.  Useful for
    ``verify_chain()`` to walk the entire history across rotation
    boundaries.
    """
    active = chain_dir / "chain.jsonl"

    # Use index order if available — it records segments in rotation order
    idx = load_index(chain_dir)
    if idx.segments:
        ordered: list[Path] = []
        for seg in idx.segments:
            p = chain_dir / seg.filename
            if p.is_file():
                ordered.append(p)
        if active.is_file() and active.stat().st_size > 0:
            ordered.append(active)
        return ordered

    # Fallback: glob + sort (works when no index exists)
    rotated = sorted(chain_dir.glob("chain.*.jsonl"))
    result = list(rotated)
    if active.is_file() and active.stat().st_size > 0:
        result.append(active)
    return result
