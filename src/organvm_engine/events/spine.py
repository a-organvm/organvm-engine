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
    """Canonical event types — the unified vocabulary for the entire system.

    Every event emitted anywhere in the engine (constitutional spine, pulse
    bus, engine modules) MUST use a member of this enum.  The string value
    follows the ``domain.action`` convention and is the wire format stored
    in JSONL logs.

    Adding a new member here is an intentional constitutional act — the enum
    is the single source of truth for the event vocabulary.

    Sections below group members by origin:
      * Constitutional — original SPEC-ladder types
      * Testament Protocol — chain/ledger additions
      * Governance — promotion, audit, dependency enforcement
      * Registry — load/update lifecycle
      * Coordination — multi-agent punch-in/out, capacity
      * Metrics / Organism — computed scores, staleness
      * Seed — edge graph mutations
      * Context — CLAUDE.md / AMMOI sync
      * Sensor — filesystem change detection
      * Pulse — heartbeat, AMMOI, inference, advisories, edges, variables
      * Session — agent session lifecycle
      * Density — interconnectedness computation
      * Affective — system mood shifts
    """

    # -- Constitutional (original SPEC-ladder) --------------------------------
    PROMOTION = "governance.promotion"
    DEPENDENCY_CHANGE = "governance.dependency_change"
    SEED_UPDATE = "seed.update"
    GOVERNANCE_AUDIT = "governance.audit"
    METRIC_UPDATE = "metrics.update"
    ENTITY_CREATED = "entity.created"
    ENTITY_ARCHIVED = "entity.archived"
    CONTEXT_SYNC = "context.sync"

    # -- Testament Protocol ---------------------------------------------------
    TESTAMENT_GENESIS = "testament.genesis"
    TESTAMENT_CHECKPOINT = "testament.checkpoint"
    TESTAMENT_VERIFIED = "testament.verified"

    # -- Governance (engine) --------------------------------------------------
    PROMOTION_CHANGED = "governance.promotion_changed"
    GATE_EVALUATED = "governance.gate_evaluated"
    DEPENDENCY_VIOLATION = "governance.dependency_violation"
    AUDIT_COMPLETED = "governance.audit_completed"

    # -- Registry -------------------------------------------------------------
    REGISTRY_UPDATE = "registry.update"
    REGISTRY_UPDATED = "registry.updated"
    REGISTRY_LOADED = "registry.loaded"

    # -- Coordination ---------------------------------------------------------
    AGENT_PUNCH_IN = "agent.punch_in"
    AGENT_PUNCH_OUT = "agent.punch_out"
    AGENT_TOOL_LOCK = "agent.tool_lock"
    AGENT_PUNCHED_IN = "coordination.punch_in"
    AGENT_PUNCHED_OUT = "coordination.punch_out"
    CAPACITY_WARNING = "coordination.capacity_warning"

    # -- Metrics / Organism ---------------------------------------------------
    ORGANISM_COMPUTED = "metrics.organism_computed"
    STALENESS_DETECTED = "metrics.staleness_detected"

    # -- Seed -----------------------------------------------------------------
    SEED_EDGE_ADDED = "seed.edge_added"
    SEED_EDGE_REMOVED = "seed.edge_removed"
    SEED_UNRESOLVED = "seed.unresolved_consumer"

    # -- Context --------------------------------------------------------------
    CONTEXT_SYNCED = "context.synced"
    CONTEXT_AMMOI_DISTRIBUTED = "context.ammoi_distributed"

    # -- Sensor ---------------------------------------------------------------
    SENSOR_SCAN_COMPLETED = "sensor.scan_completed"
    SENSOR_CHANGE_DETECTED = "sensor.change_detected"

    # -- Pulse ----------------------------------------------------------------
    PULSE_HEARTBEAT = "pulse.heartbeat"
    AMMOI_COMPUTED = "pulse.ammoi_computed"
    INFERENCE_COMPLETED = "pulse.inference_completed"
    ADVISORY_GENERATED = "pulse.advisory_generated"
    HEARTBEAT_DIFF = "pulse.heartbeat_diff"
    EDGES_SYNCED = "pulse.edges_synced"
    VARIABLES_SYNCED = "pulse.variables_synced"

    # -- CI -------------------------------------------------------------------
    CI_HEALTH = "ci.health"

    # -- Content --------------------------------------------------------------
    CONTENT_PUBLISHED = "content.published"

    # -- Ecosystem ------------------------------------------------------------
    ECOSYSTEM_MUTATION = "ecosystem.mutation"

    # -- Pitch ----------------------------------------------------------------
    PITCH_GENERATED = "pitch.generated"

    # -- Git ------------------------------------------------------------------
    GIT_SYNC = "git.sync"

    # -- Ontologia ------------------------------------------------------------
    ONTOLOGIA_VARIABLE = "ontologia.variable"

    # -- Session (pulse-origin) -----------------------------------------------
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"

    # -- Density (pulse-origin) -----------------------------------------------
    DENSITY_COMPUTED = "density.computed"

    # -- Affective (pulse-origin) ---------------------------------------------
    MOOD_SHIFTED = "mood.shifted"

    # -- Legacy pulse aliases (kept for string-comparison compatibility) -------
    #    These map to the same domain.action strings that the old
    #    pulse/events.py constants used where they differed from the
    #    engine types.py names.
    GATE_CHANGED = "gate.changed"
    REPO_PROMOTED = "repo.promoted"
    SEED_CHANGED = "seed.changed"


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
        import fcntl

        from organvm_engine.ledger.chain import GENESIS_PREV_HASH, compute_event_hash

        # Normalize enum to string value
        if isinstance(event_type, EventType):
            event_type = event_type.value

        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Acquire exclusive lock for the entire read-compute-write cycle.
        # This prevents concurrent writers from racing on sequence/prev_hash.
        lock_path = self._path.with_suffix(".lock")
        lock_fd = lock_path.open("w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)

            # Under lock: always read the actual last event from disk
            # (cache may be stale if another process wrote since our last emit)
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

            with self._path.open("a") as f:
                f.write(record.to_json() + "\n")

            # Update cache
            self._last_hash = record.hash
            self._last_seq = record.sequence

        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

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
