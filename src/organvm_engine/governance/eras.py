"""Era tracker — temporal governance epochs.

Implements: INST-ERA, ERA-001 through ERA-005

An era is a named temporal epoch in the system's life. Each era has a
deep-structure dict describing its character and a transition_reason
recording why the previous era ended.

ERA-001: pre-flood (proliferation, 52+ repos)
ERA-002: flood (structural consolidation, materia-collider dissolution)
ERA-003: post-flood (constitutional governance, registry as source of truth)
ERA-004: reserved for future transitions
ERA-005: reserved for future transitions

The EraTracker reads/writes a simple JSON file tracking era history.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Era dataclass
# ---------------------------------------------------------------------------


@dataclass
class Era:
    """A single temporal era in the system's life.

    Fields:
        era_id: Unique identifier (e.g., "ERA-001").
        title: Human-readable era name.
        started_at: ISO-8601 timestamp when the era began.
        ended_at: ISO-8601 timestamp when the era ended (empty if current).
        deep_structure: Arbitrary metadata describing the era's character.
        transition_reason: Why the previous era ended / this one began.
    """

    era_id: str = ""
    title: str = ""
    started_at: str = ""
    ended_at: str = ""
    deep_structure: dict[str, Any] = field(default_factory=dict)
    transition_reason: str = ""

    def is_active(self) -> bool:
        """Return True if this era has not ended."""
        return not self.ended_at

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Era:
        return cls(
            era_id=data.get("era_id", ""),
            title=data.get("title", ""),
            started_at=data.get("started_at", ""),
            ended_at=data.get("ended_at", ""),
            deep_structure=data.get("deep_structure", {}),
            transition_reason=data.get("transition_reason", ""),
        )


# ---------------------------------------------------------------------------
# Default eras
# ---------------------------------------------------------------------------

_DEFAULT_ERAS: list[Era] = [
    Era(
        era_id="ERA-001",
        title="Pre-Flood",
        started_at="2025-01-01T00:00:00+00:00",
        ended_at="2025-12-01T00:00:00+00:00",
        deep_structure={"character": "proliferation", "repo_count": 52},
        transition_reason="System reached unsustainable complexity",
    ),
    Era(
        era_id="ERA-002",
        title="The Flood",
        started_at="2025-12-01T00:00:00+00:00",
        ended_at="2026-01-15T00:00:00+00:00",
        deep_structure={"character": "consolidation", "dissolved_repos": 52},
        transition_reason="materia-collider dissolution, structural reconstitution",
    ),
    Era(
        era_id="ERA-003",
        title="Post-Flood",
        started_at="2026-01-15T00:00:00+00:00",
        ended_at="",
        deep_structure={
            "character": "constitutional governance",
            "registry_as_source_of_truth": True,
        },
        transition_reason="Registry ratified, governance engine operational",
    ),
]


# ---------------------------------------------------------------------------
# EraTracker
# ---------------------------------------------------------------------------

class EraTracker:
    """Tracks era history via a simple JSON file.

    Args:
        path: Path to the era history JSON file. If None, uses an
              in-memory store seeded with default eras.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._eras: list[Era] = []
        self._load()

    def _load(self) -> None:
        """Load eras from disk, or seed with defaults."""
        if self._path is not None and self._path.is_file():
            data = json.loads(self._path.read_text())
            self._eras = [Era.from_dict(e) for e in data.get("eras", [])]
        else:
            self._eras = list(_DEFAULT_ERAS)

    def _save(self) -> None:
        """Persist eras to disk (if path is set)."""
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {"eras": [e.to_dict() for e in self._eras]}
            self._path.write_text(json.dumps(data, indent=2) + "\n")

    def all_eras(self) -> list[Era]:
        """Return all eras in chronological order."""
        return list(self._eras)

    def current_era(self) -> Era | None:
        """Return the current (active) era, or None."""
        for era in reversed(self._eras):
            if era.is_active():
                return era
        return None

    def is_in_transition(self) -> bool:
        """Return True if no era is currently active (between eras)."""
        return self.current_era() is None

    def record_transition(
        self,
        new_era_id: str,
        new_title: str,
        transition_reason: str,
        deep_structure: dict[str, Any] | None = None,
    ) -> Era:
        """Close the current era and open a new one.

        Args:
            new_era_id: ID for the new era (e.g., "ERA-004").
            new_title: Human-readable title.
            transition_reason: Why the transition is happening.
            deep_structure: Metadata for the new era.

        Returns:
            The newly created Era.

        Raises:
            ValueError: If new_era_id already exists.
        """
        # Check for duplicate IDs
        existing_ids = {e.era_id for e in self._eras}
        if new_era_id in existing_ids:
            raise ValueError(f"Era '{new_era_id}' already exists")

        # Close the current era
        now = datetime.now(timezone.utc).isoformat()
        current = self.current_era()
        if current is not None:
            current.ended_at = now

        # Create new era
        new_era = Era(
            era_id=new_era_id,
            title=new_title,
            started_at=now,
            ended_at="",
            deep_structure=deep_structure or {},
            transition_reason=transition_reason,
        )
        self._eras.append(new_era)
        self._save()
        return new_era

    def get_era(self, era_id: str) -> Era | None:
        """Look up an era by ID."""
        for era in self._eras:
            if era.era_id == era_id:
                return era
        return None
