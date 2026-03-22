"""Epoch definitions — geological periods of the ORGANVM system's history.

Each epoch has a start/end date, a dominant Jungian archetype, and an optional
secondary archetype. Timestamps are assigned to epochs by date comparison.
Session boundary detection groups sorted timestamps into sessions using a
configurable inactivity gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from organvm_engine.fossil.stratum import Archetype


@dataclass(frozen=True)
class Epoch:
    """A named geological period of the system's history."""

    id: str
    name: str
    start: date
    end: date
    dominant_archetype: Archetype
    secondary_archetype: Optional[Archetype]
    description: str


DECLARED_EPOCHS: list[Epoch] = [
    Epoch(
        id="EPOCH-001",
        name="Genesis",
        start=date(2026, 1, 22),
        end=date(2026, 2, 7),
        dominant_archetype=Archetype.SELF,
        secondary_archetype=None,
        description="The system emerges from nothing; foundational architecture laid.",
    ),
    Epoch(
        id="EPOCH-002",
        name="The Naming",
        start=date(2026, 2, 8),
        end=date(2026, 2, 9),
        dominant_archetype=Archetype.FATHER,
        secondary_archetype=None,
        description="Ontological naming conventions and organ structure established.",
    ),
    Epoch(
        id="EPOCH-003",
        name="The Bronze Sprint",
        start=date(2026, 2, 10),
        end=date(2026, 2, 10),
        dominant_archetype=Archetype.MOTHER,
        secondary_archetype=None,
        description="Initial rapid build-out; nurturing the core scaffolding.",
    ),
    Epoch(
        id="EPOCH-004",
        name="The Silver Sprint",
        start=date(2026, 2, 10),
        end=date(2026, 2, 11),
        dominant_archetype=Archetype.ANIMUS,
        secondary_archetype=None,
        description="Assertive structural consolidation; schemas and governance.",
    ),
    Epoch(
        id="EPOCH-005",
        name="The Gold Sprint",
        start=date(2026, 2, 10),
        end=date(2026, 2, 11),
        dominant_archetype=Archetype.ANIMA,
        secondary_archetype=None,
        description="Intuitive integration; bridging engine with corpus.",
    ),
    Epoch(
        id="EPOCH-006",
        name="Launch",
        start=date(2026, 2, 11),
        end=date(2026, 2, 11),
        dominant_archetype=Archetype.INDIVIDUATION,
        secondary_archetype=None,
        description="The system becomes whole; public graduation of core repos.",
    ),
    Epoch(
        id="EPOCH-007",
        name="The Gap-Fill",
        start=date(2026, 2, 12),
        end=date(2026, 2, 17),
        dominant_archetype=Archetype.SHADOW,
        secondary_archetype=None,
        description="Addressing hidden debt; filling gaps exposed by launch.",
    ),
    Epoch(
        id="EPOCH-008",
        name="The Quiet Growth",
        start=date(2026, 2, 18),
        end=date(2026, 3, 7),
        dominant_archetype=Archetype.MOTHER,
        secondary_archetype=Archetype.ANIMUS,
        description="Steady, nurturing expansion; organs cultivated in parallel.",
    ),
    Epoch(
        id="EPOCH-009",
        name="The Research Tsunami",
        start=date(2026, 3, 8),
        end=date(2026, 3, 19),
        dominant_archetype=Archetype.ANIMA,
        secondary_archetype=Archetype.TRICKSTER,
        description="Massive knowledge ingestion; research dissolves old boundaries.",
    ),
    Epoch(
        id="EPOCH-010",
        name="The Reckoning",
        start=date(2026, 3, 20),
        end=date(2026, 3, 20),
        dominant_archetype=Archetype.SELF,
        secondary_archetype=None,
        description="Confronting system state; honest audit of what exists.",
    ),
    Epoch(
        id="EPOCH-011",
        name="The Engine Expansion",
        start=date(2026, 3, 20),
        end=date(2026, 3, 21),
        dominant_archetype=Archetype.ANIMUS,
        secondary_archetype=Archetype.MOTHER,
        description="Assertive engine growth; fossil and new modules added.",
    ),
    Epoch(
        id="EPOCH-012",
        name="The Contribution Engine",
        start=date(2026, 3, 21),
        end=date(2026, 3, 22),
        dominant_archetype=Archetype.INDIVIDUATION,
        secondary_archetype=Archetype.ANIMUS,
        description="The system generates outward; contribution loops activated.",
    ),
]


def assign_epoch(dt: datetime) -> Epoch | None:
    """Return the epoch a datetime falls into, or None if outside all epochs.

    Comparison is date-based. When multiple epochs overlap on the same date
    (e.g. Bronze/Silver/Gold all share 2026-02-10), the last declared epoch
    whose range contains the date is returned — reflecting the most advanced
    phase active on that day.
    """
    target = dt.date() if dt.tzinfo is not None else dt.date()
    result: Epoch | None = None
    for epoch in DECLARED_EPOCHS:
        if epoch.start <= target <= epoch.end:
            result = epoch
    return result


def detect_session_boundaries(
    timestamps: list[datetime],
    gap_minutes: int = 90,
) -> list[list[datetime]]:
    """Group sorted timestamps into sessions separated by inactivity gaps.

    Two consecutive timestamps belong to the same session when the gap between
    them is strictly less than ``gap_minutes``. A gap >= ``gap_minutes``
    starts a new session.

    Args:
        timestamps: Datetime objects (need not be pre-sorted; function sorts them).
        gap_minutes: Minimum inactivity gap (in minutes) that breaks a session.

    Returns:
        A list of sessions, each session being a list of datetime objects.
    """
    if not timestamps:
        return []

    sorted_ts = sorted(timestamps)
    gap = timedelta(minutes=gap_minutes)

    sessions: list[list[datetime]] = [[sorted_ts[0]]]
    for ts in sorted_ts[1:]:
        if ts - sessions[-1][-1] >= gap:
            sessions.append([ts])
        else:
            sessions[-1].append(ts)

    return sessions
