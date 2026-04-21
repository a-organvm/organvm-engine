"""PRIM-INST-016 — The Archivist.

Captures institutional memory (decisions, precedents, outcomes, patterns,
lessons) and retrieves it for downstream primitives.  The archivist is the
system's long-term memory — every formation output can be archived, and
every counselor invocation can query for precedent.

Storage: append-only JSONL + companion tag/category index for fast lookup.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.types import (
    ExecutionMode,
    Frame,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)

_DEFAULT_BASE = Path.home() / ".organvm" / "institutional" / "archivist"


# ---------------------------------------------------------------------------
# Archivist-specific types
# ---------------------------------------------------------------------------


@dataclass
class MemoryRecord:
    """A single institutional memory entry."""

    record_id: str = field(
        default_factory=lambda: f"MEM-{uuid.uuid4().hex[:12]}",
    )
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    category: str = ""  # decision, precedent, outcome, pattern, lesson
    summary: str = ""
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    tags: list[str] = field(default_factory=list)
    formation_id: str = ""
    related_records: list[str] = field(default_factory=list)
    search_text: str = ""


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


class ArchivistStore:
    """Append-only JSONL + index for institutional memory."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base = base_path or _DEFAULT_BASE
        self._memory_path = self._base / "memory.jsonl"
        self._index_path = self._base / "index.json"

    def _ensure_dirs(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)

    # -- write -------------------------------------------------------------

    def append(self, record: MemoryRecord) -> None:
        """Append a record and update the index."""
        self._ensure_dirs()
        with self._memory_path.open("a") as f:
            f.write(json.dumps(asdict(record)) + "\n")
        self._update_index(record)

    def _update_index(self, record: MemoryRecord) -> None:
        idx = self._load_index()
        # index by category
        cat_key = f"cat:{record.category}"
        idx.setdefault(cat_key, [])
        if record.record_id not in idx[cat_key]:
            idx[cat_key].append(record.record_id)
        # index by tags
        for tag in record.tags:
            tag_key = f"tag:{tag}"
            idx.setdefault(tag_key, [])
            if record.record_id not in idx[tag_key]:
                idx[tag_key].append(record.record_id)
        with self._index_path.open("w") as f:
            json.dump(idx, f, indent=2)

    def _load_index(self) -> dict[str, list[str]]:
        if self._index_path.exists():
            with self._index_path.open() as f:
                return json.load(f)
        return {}

    # -- read --------------------------------------------------------------

    def load_all(self) -> list[MemoryRecord]:
        """Load all records from the JSONL file."""
        if not self._memory_path.exists():
            return []
        records: list[MemoryRecord] = []
        with self._memory_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(MemoryRecord(**json.loads(line)))
        return records

    def search(
        self,
        *,
        tags: list[str] | None = None,
        category: str = "",
        text: str = "",
        limit: int = 20,
    ) -> list[MemoryRecord]:
        """Search records by tags, category, and/or free text."""
        idx = self._load_index()
        candidate_ids: set[str] | None = None

        # narrow by category
        if category:
            cat_ids = set(idx.get(f"cat:{category}", []))
            candidate_ids = cat_ids

        # narrow by tags (intersection)
        if tags:
            for tag in tags:
                tag_ids = set(idx.get(f"tag:{tag}", []))
                if candidate_ids is None:
                    candidate_ids = tag_ids
                else:
                    candidate_ids &= tag_ids

        # load candidates
        all_records = self.load_all()
        if candidate_ids is not None:
            all_records = [r for r in all_records if r.record_id in candidate_ids]

        # free text filter
        if text:
            text_lower = text.lower()
            all_records = [
                r for r in all_records
                if text_lower in r.search_text.lower()
                or text_lower in r.summary.lower()
            ]

        return all_records[-limit:]


# ---------------------------------------------------------------------------
# The Archivist primitive
# ---------------------------------------------------------------------------


class Archivist(InstitutionalPrimitive):
    """PRIM-INST-016 — captures and retrieves institutional memory."""

    PRIMITIVE_ID = "PRIM-INST-016"
    PRIMITIVE_NAME = "archivist"
    CLUSTER = "epistemic"
    DEFAULT_STAKES = StakesLevel.ROUTINE

    def __init__(self, store: ArchivistStore | None = None) -> None:
        self._store = store or ArchivistStore()

    def invoke(
        self,
        context: InstitutionalContext,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        mode = context.data.get("mode", "retrieve")
        if mode == "capture":
            return self._capture(context, frame)
        return self._retrieve(context, frame)

    # -- capture -----------------------------------------------------------

    def _capture(
        self,
        context: InstitutionalContext,
        frame: Frame,
    ) -> PrimitiveOutput:
        record = MemoryRecord(
            category=context.data.get("category", "decision"),
            summary=context.data.get("summary", context.situation),
            context_snapshot=context.data.get("context_snapshot", {}),
            outcome=context.data.get("outcome", ""),
            tags=context.data.get("tags", context.tags),
            formation_id=context.data.get("formation_id", ""),
            related_records=context.data.get("related_records", []),
        )
        # pre-compute search text
        parts = [record.summary, record.outcome, record.category]
        parts.extend(record.tags)
        record.search_text = " ".join(parts).lower()

        self._store.append(record)

        exe_mode = ExecutionMode.PROTOCOL_STRUCTURED
        audit = self._make_audit_entry(
            operation="capture",
            rationale="Institutional memory preservation",
            inputs_summary=f"category={record.category}",
            output_summary=f"record_id={record.record_id}",
            execution_mode=exe_mode,
            confidence=1.0,
        )
        return PrimitiveOutput(
            output=asdict(record),
            confidence=1.0,
            escalation_flag=False,
            audit_trail=[audit],
            execution_mode=exe_mode,
            stakes=StakesLevel.ROUTINE,
            context_id=context.context_id,
            primitive_id=self.PRIMITIVE_ID,
        )

    # -- retrieve ----------------------------------------------------------

    def _retrieve(
        self,
        context: InstitutionalContext,
        frame: Frame,
    ) -> PrimitiveOutput:
        results = self._store.search(
            tags=context.data.get("search_tags"),
            category=context.data.get("search_category", ""),
            text=context.data.get("search_text", ""),
            limit=context.data.get("limit", 20),
        )
        confidence = 0.8 if results else 0.3
        exe_mode = self.determine_execution_mode(confidence, self.DEFAULT_STAKES)

        audit = self._make_audit_entry(
            operation="retrieve",
            rationale="Precedent search for downstream primitives",
            inputs_summary=f"text={context.data.get('search_text', '')!r}",
            output_summary=f"{len(results)} records found",
            execution_mode=exe_mode,
            confidence=confidence,
        )
        return PrimitiveOutput(
            output=[asdict(r) for r in results],
            confidence=confidence,
            escalation_flag=confidence < 0.5,
            audit_trail=[audit],
            execution_mode=exe_mode,
            stakes=self.DEFAULT_STAKES,
            context_id=context.context_id,
            primitive_id=self.PRIMITIVE_ID,
        )
