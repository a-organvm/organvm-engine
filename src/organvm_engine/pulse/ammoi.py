"""AMMOI — Adaptive Macro-Micro Ontological Index.

A compressed multi-scale density index that every node can carry.
Computes density at three scales:
  - Macro: system-wide (the whole ORGANVM)
  - Meso: per-organ (each of the eight organs)
  - Micro: per-entity (individual repos)

The AMMOI snapshot is the system's compressed self-image — small enough
to inject into every context file, rich enough to convey the system's
state at a glance.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class EntityDensity:
    """Micro-scale: density for a single entity."""

    entity_id: str
    entity_name: str
    organ: str
    local_edges: int = 0
    gate_pct: int = 0
    event_frequency_24h: int = 0
    blast_radius: int = 0
    active_claims: int = 0
    density: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrganDensity:
    """Meso-scale: density for an organ."""

    organ_id: str
    organ_name: str
    repo_count: int = 0
    internal_edges: int = 0
    cross_edges: int = 0
    avg_gate_pct: int = 0
    event_frequency_24h: int = 0
    active_agents: int = 0
    tension_count: int = 0
    density: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AMMOI:
    """Adaptive Macro-Micro Ontological Index.

    A compressed image of the whole that can be projected at any scale.
    """

    timestamp: str = ""

    # Macro: system-wide
    system_density: float = 0.0
    total_entities: int = 0
    active_edges: int = 0
    active_loops: int = 0
    tension_count: int = 0
    event_frequency_24h: int = 0

    # Temporal vectors
    density_delta_24h: float = 0.0
    density_delta_7d: float = 0.0
    density_delta_30d: float = 0.0

    # Meso: per-organ
    organs: dict[str, OrganDensity] = field(default_factory=dict)

    # Rhythm
    pulse_count: int = 0
    pulse_interval: int = 900  # default 15min

    # Compressed text (for context injection)
    compressed_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = {
            "timestamp": self.timestamp,
            "system_density": self.system_density,
            "total_entities": self.total_entities,
            "active_edges": self.active_edges,
            "active_loops": self.active_loops,
            "tension_count": self.tension_count,
            "event_frequency_24h": self.event_frequency_24h,
            "density_delta_24h": self.density_delta_24h,
            "density_delta_7d": self.density_delta_7d,
            "density_delta_30d": self.density_delta_30d,
            "organs": {k: v.to_dict() for k, v in self.organs.items()},
            "pulse_count": self.pulse_count,
            "pulse_interval": self.pulse_interval,
            "compressed_text": self.compressed_text,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AMMOI:
        organs = {}
        for k, v in data.get("organs", {}).items():
            organs[k] = OrganDensity(**v)
        return cls(
            timestamp=data.get("timestamp", ""),
            system_density=data.get("system_density", 0.0),
            total_entities=data.get("total_entities", 0),
            active_edges=data.get("active_edges", 0),
            active_loops=data.get("active_loops", 0),
            tension_count=data.get("tension_count", 0),
            event_frequency_24h=data.get("event_frequency_24h", 0),
            density_delta_24h=data.get("density_delta_24h", 0.0),
            density_delta_7d=data.get("density_delta_7d", 0.0),
            density_delta_30d=data.get("density_delta_30d", 0.0),
            organs=organs,
            pulse_count=data.get("pulse_count", 0),
            pulse_interval=data.get("pulse_interval", 900),
            compressed_text=data.get("compressed_text", ""),
        )


# ---------------------------------------------------------------------------
# AMMOI history storage
# ---------------------------------------------------------------------------

def _history_path() -> Path:
    return Path.home() / ".organvm" / "pulse" / "ammoi-history.jsonl"


def _read_history(limit: int = 500) -> list[AMMOI]:
    """Read AMMOI snapshots from history."""
    path = _history_path()
    if not path.is_file():
        return []
    snapshots: list[AMMOI] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            snapshots.append(AMMOI.from_dict(json.loads(line)))
        except (json.JSONDecodeError, TypeError):
            continue
    return snapshots[-limit:]


def _append_history(ammoi: AMMOI) -> None:
    """Append an AMMOI snapshot to history."""
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = json.dumps(ammoi.to_dict(), separators=(",", ":"), default=str)
    with path.open("a") as f:
        f.write(entry + "\n")


def _count_history() -> int:
    """Count total AMMOI snapshots in history (without parsing all)."""
    path = _history_path()
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text().splitlines() if line.strip())


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _count_recent_events(hours: int = 24) -> int:
    """Count events in the last N hours from the engine event log."""
    try:
        from organvm_engine.pulse.events import event_counts

        counts = event_counts()
        return sum(counts.values())
    except Exception:
        return 0


def _compute_temporal_deltas(
    current_density: float,
    history: list[AMMOI],
) -> tuple[float, float, float]:
    """Compute density deltas against 24h, 7d, and 30d ago."""
    if not history:
        return 0.0, 0.0, 0.0

    now = datetime.now(timezone.utc)

    def _find_closest(target_hours: int) -> float | None:
        best: AMMOI | None = None
        best_diff = float("inf")
        for snap in history:
            try:
                ts = datetime.fromisoformat(snap.timestamp)
                diff = abs((now - ts).total_seconds() - target_hours * 3600)
                if diff < best_diff:
                    best_diff = diff
                    best = snap
            except (ValueError, TypeError):
                continue
        if best and best_diff < target_hours * 3600 * 0.5:
            return best.system_density
        return None

    d24 = _find_closest(24)
    d7 = _find_closest(168)
    d30 = _find_closest(720)

    delta_24h = current_density - d24 if d24 is not None else 0.0
    delta_7d = current_density - d7 if d7 is not None else 0.0
    delta_30d = current_density - d30 if d30 is not None else 0.0

    return delta_24h, delta_7d, delta_30d


def _build_compressed_text(ammoi: AMMOI) -> str:
    """Build a ~200 char human-readable summary for context injection."""
    organ_densities = sorted(
        ammoi.organs.items(),
        key=lambda x: x[1].density,
        reverse=True,
    )
    top_organs = ", ".join(
        f"{k}:{v.density:.0%}" for k, v in organ_densities[:3]
    )

    delta_str = ""
    if ammoi.density_delta_24h:
        sign = "+" if ammoi.density_delta_24h > 0 else ""
        delta_str = f" | d24h:{sign}{ammoi.density_delta_24h:.1%}"

    return (
        f"AMMOI:{ammoi.system_density:.0%} "
        f"E:{ammoi.active_edges} "
        f"T:{ammoi.tension_count} "
        f"Ev24h:{ammoi.event_frequency_24h} "
        f"[{top_organs}]"
        f"{delta_str}"
    )


def compute_ammoi(
    registry: dict | None = None,
    workspace: Path | None = None,
    include_events: bool = True,
) -> AMMOI:
    """Compute the full AMMOI snapshot.

    Draws data from:
    - Registry + organism (gate pass rates, repo counts)
    - Seed graph (edges, cross-organ wiring)
    - Density module (interconnection score)
    - Event log (activity frequency)
    - AMMOI history (temporal deltas)
    """
    from organvm_engine.metrics.organism import get_organism
    from organvm_engine.pulse.density import compute_density
    from organvm_engine.seed.graph import build_seed_graph, validate_edge_resolution

    organism = get_organism(registry=registry, include_omega=False)
    ws = workspace or Path.home() / "Workspace"
    graph = build_seed_graph(ws)
    unresolved = validate_edge_resolution(graph)
    dp = compute_density(graph, organism, len(unresolved))

    # Per-organ computation
    organ_densities: dict[str, OrganDensity] = {}
    for organ_org in organism.organs:
        oid = organ_org.organ_id
        oname = organ_org.organ_name

        # Count edges involving this organ
        internal = 0
        cross = 0
        for src, tgt, _ in graph.edges:
            src_org = src.split("/")[0] if "/" in src else src
            tgt_org = tgt.split("/")[0] if "/" in tgt else tgt
            if src_org == oid or tgt_org == oid:
                if src_org == tgt_org:
                    internal += 1
                else:
                    cross += 1

        organ_densities[oid] = OrganDensity(
            organ_id=oid,
            organ_name=oname,
            repo_count=organ_org.count,
            internal_edges=internal,
            cross_edges=cross,
            avg_gate_pct=organ_org.avg_pct,
            density=organ_org.avg_pct / 100.0 if organ_org.count > 0 else 0.0,
        )

    # System density from the DensityProfile composite score
    system_density = dp.interconnection_score / 100.0

    # Event frequency
    event_freq = _count_recent_events() if include_events else 0

    # Temporal deltas from history
    history = _read_history(limit=200)
    d24h, d7d, d30d = _compute_temporal_deltas(system_density, history)

    # Pulse count from history
    pulse_count = len(history)

    ammoi = AMMOI(
        timestamp=datetime.now(timezone.utc).isoformat(),
        system_density=round(system_density, 4),
        total_entities=organism.total_repos,
        active_edges=dp.declared_edges,
        event_frequency_24h=event_freq,
        density_delta_24h=round(d24h, 4),
        density_delta_7d=round(d7d, 4),
        density_delta_30d=round(d30d, 4),
        organs=organ_densities,
        pulse_count=pulse_count,
    )
    ammoi.compressed_text = _build_compressed_text(ammoi)

    return ammoi
