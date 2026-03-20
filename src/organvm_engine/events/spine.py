"""Append-only event spine — the constitutional event bus.

Implements: INST-EVENT-SPINE, EVT-001 through EVT-005
Invariants enforced: INV-000-005 (Observability)

Design decisions:
  - Append-only JSONL for durability and auditability.
  - Each EventRecord carries a UUID, ISO timestamp, entity_uid, typed payload,
    the originating spec reference, and the actor (human or agent handle).
  - EventType enum encodes the constitutional event vocabulary; new types
    require an explicit enum addition (no silent invention).
  - query() reads from tail for efficiency; callers paginate via `limit`.
  - snapshot() is O(n) on the log — fine for operational dashboards, not for
    hot-path rendering. Cache externally if needed.
"""

from __future__ import annotations

import enum
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constitutional event types
# ---------------------------------------------------------------------------

class EventType(str, enum.Enum):
    """Canonical event types defined by the SPEC ladder.

    Each value maps to a specific system action that must be observable.
    Adding a new type here is an intentional constitutional act.
    """

    # Original constitutional types
    PROMOTION = "governance.promotion"
    DEPENDENCY_CHANGE = "governance.dependency_change"
    SEED_UPDATE = "seed.update"
    GOVERNANCE_AUDIT = "governance.audit"
    METRIC_UPDATE = "metrics.update"
    ENTITY_CREATED = "entity.created"
    ENTITY_ARCHIVED = "entity.archived"
    CONTEXT_SYNC = "context.sync"
    # Testament Protocol additions
    TESTAMENT_GENESIS = "testament.genesis"
    TESTAMENT_CHECKPOINT = "testament.checkpoint"
    TESTAMENT_VERIFIED = "testament.verified"
    CI_HEALTH = "ci.health"
    CONTENT_PUBLISHED = "content.published"
    ECOSYSTEM_MUTATION = "ecosystem.mutation"
    PITCH_GENERATED = "pitch.generated"
    GIT_SYNC = "git.sync"
    AGENT_PUNCH_IN = "agent.punch_in"
    AGENT_PUNCH_OUT = "agent.punch_out"
    AGENT_TOOL_LOCK = "agent.tool_lock"
    ONTOLOGIA_VARIABLE = "ontologia.variable"
    REGISTRY_UPDATE = "registry.update"


# ---------------------------------------------------------------------------
# Event record
# ---------------------------------------------------------------------------

@dataclass
class EventRecord:
    """A single constitutional event.

    Fields:
        event_id:    Unique identifier (UUID4).
        event_type:  One of the EventType values (stored as string).
        timestamp:   ISO-8601 UTC timestamp.
        entity_uid:  The ontologia entity UID this event concerns.
        payload:     Arbitrary structured data for this event type.
        source_spec: Which spec/invariant triggered this event (e.g. "SPEC-004").
        actor:       Who or what caused the event (agent handle, "cli", "human").

    Chain fields (Testament Protocol):
        sequence:            Monotonic block number (-1 = not yet assigned).
        prev_hash:           SHA-256 hash of the preceding event's hash field.
        hash:                SHA-256 hash of this event (excluding hash itself).
        causal_predecessor:  Event ID of the event that causally triggered this one.
        source_organ:        Organ key (e.g. "META-ORGANVM", "ORGAN-I").
        source_repo:         Repository name within the organ.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    entity_uid: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    source_spec: str = ""
    actor: str = ""
    # Chain fields (Testament Protocol)
    sequence: int = -1
    prev_hash: str = ""
    hash: str = ""
    causal_predecessor: str = ""
    source_organ: str = ""
    source_repo: str = ""

    def to_json(self) -> str:
        """Serialize to compact JSON for JSONL storage."""
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventRecord:
        """Reconstruct from a parsed JSON dict."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=data.get("event_type", ""),
            timestamp=data.get("timestamp", ""),
            entity_uid=data.get("entity_uid", ""),
            payload=data.get("payload", {}),
            source_spec=data.get("source_spec", ""),
            actor=data.get("actor", ""),
            sequence=data.get("sequence", -1),
            prev_hash=data.get("prev_hash", ""),
            hash=data.get("hash", ""),
            causal_predecessor=data.get("causal_predecessor", ""),
            source_organ=data.get("source_organ", ""),
            source_repo=data.get("source_repo", ""),
        )


# ---------------------------------------------------------------------------
# Default path
# ---------------------------------------------------------------------------

_DEFAULT_EVENTS_PATH = Path.home() / ".organvm" / "events.jsonl"


# ---------------------------------------------------------------------------
# EventSpine
# ---------------------------------------------------------------------------

class EventSpine:
    """Append-only JSONL event store.

    The spine writes to a single JSONL file. It never modifies or deletes
    existing lines — append-only by constitutional mandate (INV-000-005).

    Args:
        path: Path to the JSONL file. Defaults to ~/.organvm/events.jsonl.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else _DEFAULT_EVENTS_PATH
        # Cache for O(1) chain-linking on emit (avoids scanning the full file)
        self._last_hash: str | None = None
        self._last_seq: int | None = None

    @property
    def path(self) -> Path:
        """The JSONL file path this spine writes to."""
        return self._path

    # -- Write ---------------------------------------------------------------

    def emit(
        self,
        event_type: str | EventType,
        entity_uid: str,
        payload: dict[str, Any] | None = None,
        source_spec: str = "",
        actor: str = "",
        source_organ: str = "",
        source_repo: str = "",
        causal_predecessor: str = "",
    ) -> EventRecord:
        """Append a new event to the spine with hash-chain linking.

        The event is assigned the next sequence number, its prev_hash is set
        to the hash of the preceding event (or GENESIS_PREV_HASH for the first
        event), and its own hash is computed over all fields.

        Args:
            event_type: Constitutional event type (string or EventType enum).
            entity_uid: The entity this event concerns.
            payload: Additional structured data.
            source_spec: Originating specification reference.
            actor: Who/what caused this event.
            source_organ: Organ key (e.g. "META-ORGANVM").
            source_repo: Repository name within the organ.
            causal_predecessor: Event ID of the triggering event.

        Returns:
            The persisted EventRecord.
        """
        from organvm_engine.ledger.chain import GENESIS_PREV_HASH, compute_event_hash

        # Normalize enum to string value
        if isinstance(event_type, EventType):
            event_type = event_type.value

        # Determine sequence and prev_hash — use cache if available,
        # otherwise scan the file (happens once per EventSpine instance
        # or when a different process appended to the same file).
        if self._last_hash is not None and self._last_seq is not None:
            last_hash = self._last_hash
            last_seq = self._last_seq
        else:
            last_hash = GENESIS_PREV_HASH
            last_seq = -1
            if self._path.is_file():
                for line in self._path.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        h = data.get("hash", "")
                        if h:
                            last_hash = h
                        s = data.get("sequence", -1)
                        if s >= 0:
                            last_seq = s
                    except json.JSONDecodeError:
                        continue

        record = EventRecord(
            event_type=event_type,
            entity_uid=entity_uid,
            payload=payload or {},
            source_spec=source_spec,
            actor=actor,
            source_organ=source_organ,
            source_repo=source_repo,
            causal_predecessor=causal_predecessor,
            sequence=last_seq + 1,
            prev_hash=last_hash,
        )

        # Compute hash over all fields except hash itself
        event_dict = asdict(record)
        record.hash = compute_event_hash(event_dict)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a") as f:
            f.write(record.to_json() + "\n")

        # Update cache for O(1) next emit
        self._last_hash = record.hash
        self._last_seq = record.sequence

        return record

    # -- Read ----------------------------------------------------------------

    def query(
        self,
        event_type: str | EventType | None = None,
        entity_uid: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[EventRecord]:
        """Query events from the spine.

        Filters are AND-combined. Returns most recent events last,
        capped at `limit`.

        Args:
            event_type: Filter by event type.
            entity_uid: Filter by entity UID.
            since: ISO timestamp — only return events strictly after this time.
            limit: Maximum number of results to return.

        Returns:
            List of matching EventRecords, oldest first, capped at limit.
        """
        if not self._path.is_file():
            return []

        # Normalize enum to string value
        if isinstance(event_type, EventType):
            event_type = event_type.value

        records: list[EventRecord] = []
        for line in self._path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Apply filters
            if event_type and data.get("event_type") != event_type:
                continue
            if entity_uid and data.get("entity_uid") != entity_uid:
                continue
            if since and data.get("timestamp", "") <= since:
                continue

            records.append(EventRecord.from_dict(data))

        # Return the last `limit` records
        return records[-limit:]

    def snapshot(self) -> dict[str, Any]:
        """Return a summary of the current spine state.

        Returns:
            Dict with 'event_count' and 'latest_timestamp' (or None if empty).
        """
        if not self._path.is_file():
            return {"event_count": 0, "latest_timestamp": None}

        count = 0
        latest_ts: str | None = None

        for line in self._path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            ts = data.get("timestamp", "")
            if ts and (latest_ts is None or ts > latest_ts):
                latest_ts = ts

        return {"event_count": count, "latest_timestamp": latest_ts}
