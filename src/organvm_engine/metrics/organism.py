"""SystemOrganism — unified hierarchical snapshot of the entire system.

Single computation path: registry + filesystem + omega -> one object.
All consumers (dashboard, MCP, CLI, portal, pitch) get projections from this.

Access modes:
    Full:          compute_organism(reg, workspace) — ~3s, for CLI/batch
    Registry-only: compute_organism(reg) — sub-second, for MCP/API
    Cached:        get_organism(ttl=30) — dashboard/API, auto-invalidating
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from organvm_engine.metrics.gates import (
    GATE_ORDER,
    RepoProgress,
    evaluate_all,
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GateStats:
    """Aggregate pass rate for a single gate across repos."""

    name: str
    applicable: int = 0
    passed: int = 0

    @property
    def failed(self) -> int:
        return self.applicable - self.passed

    @property
    def rate(self) -> int:
        return int(self.passed / self.applicable * 100) if self.applicable else 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "applicable": self.applicable,
            "passed": self.passed,
            "failed": self.failed,
            "rate": self.rate,
        }


@dataclass
class OrganOrganism:
    """Aggregated state for a single organ."""

    organ_id: str
    organ_name: str
    repos: list[RepoProgress]

    @property
    def count(self) -> int:
        return len(self.repos)

    @property
    def avg_pct(self) -> int:
        if not self.repos:
            return 0
        return int(sum(r.pct for r in self.repos) / len(self.repos))

    @property
    def promo_ready_count(self) -> int:
        return sum(1 for r in self.repos if r.promo_ready)

    @property
    def stale_count(self) -> int:
        return sum(1 for r in self.repos if r.is_stale)

    def to_dict(self) -> dict:
        return {
            "organ_id": self.organ_id,
            "organ_name": self.organ_name,
            "count": self.count,
            "avg_pct": self.avg_pct,
            "promo_ready": self.promo_ready_count,
            "stale": self.stale_count,
            "repos": [r.to_dict() for r in self.repos],
        }


@dataclass
class SystemOrganism:
    """Complete hierarchical system snapshot."""

    organs: list[OrganOrganism]
    generated: str = ""
    omega: dict | None = None
    network: dict | None = None

    @property
    def all_repos(self) -> list[RepoProgress]:
        return [r for o in self.organs for r in o.repos]

    @property
    def total_repos(self) -> int:
        return sum(o.count for o in self.organs)

    @property
    def sys_pct(self) -> int:
        repos = self.all_repos
        if not repos:
            return 0
        return int(sum(r.pct for r in repos) / len(repos))

    @property
    def total_promo_ready(self) -> int:
        return sum(o.promo_ready_count for o in self.organs)

    @property
    def total_stale(self) -> int:
        return sum(o.stale_count for o in self.organs)

    def profile_counts(self) -> dict[str, int]:
        return dict(
            Counter(r.profile for r in self.all_repos).most_common(),
        )

    def promo_counts(self) -> dict[str, int]:
        return dict(
            Counter(r.promo for r in self.all_repos).most_common(),
        )

    def lang_counts(self, top_n: int = 6) -> dict[str, int]:
        return dict(
            Counter(
                r.primary_lang for r in self.all_repos
                if r.primary_lang != "none"
            ).most_common(top_n),
        )

    def gate_stats(self) -> list[GateStats]:
        repos = self.all_repos
        stats = []
        for g in GATE_ORDER:
            gs = GateStats(name=g)
            for r in repos:
                gate = next(
                    (x for x in r.gates if x.name == g), None,
                )
                if gate and gate.applicable:
                    gs.applicable += 1
                    if gate.passed:
                        gs.passed += 1
            stats.append(gs)
        return stats

    def total_discrepancies(self) -> int:
        return sum(len(r.discrepancies) for r in self.all_repos)

    def find_repo(self, name: str) -> RepoProgress | None:
        for r in self.all_repos:
            if r.repo == name:
                return r
        return None

    def find_organ(self, organ_id: str) -> OrganOrganism | None:
        for o in self.organs:
            if o.organ_id == organ_id:
                return o
        return None

    def to_dict(self) -> dict:
        return {
            "total_repos": self.total_repos,
            "sys_pct": self.sys_pct,
            "total_promo_ready": self.total_promo_ready,
            "total_stale": self.total_stale,
            "profiles": self.profile_counts(),
            "promo_distribution": self.promo_counts(),
            "languages": self.lang_counts(),
            "gate_stats": [gs.to_dict() for gs in self.gate_stats()],
            "total_discrepancies": self.total_discrepancies(),
            "organs": [o.to_dict() for o in self.organs],
            "omega": self.omega,
            "network": self.network,
            "generated": self.generated,
        }


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

_ORGAN_ORDER = [
    "ORGAN-I", "ORGAN-II", "ORGAN-III", "ORGAN-IV",
    "ORGAN-V", "ORGAN-VI", "ORGAN-VII", "META-ORGANVM",
]


def compute_organism(
    registry: dict,
    workspace: Path | None = None,
    include_omega: bool = False,
) -> SystemOrganism:
    """Compute the full system organism from registry + filesystem.

    Args:
        registry: Loaded registry dict.
        workspace: Workspace root for filesystem checks. None = fast mode.
        include_omega: Include omega scorecard in the result.

    Returns:
        SystemOrganism with hierarchical repo/organ/system data.
    """
    all_progress = evaluate_all(registry, workspace)

    # Group by organ
    by_organ: dict[str, list[RepoProgress]] = {}
    organ_names: dict[str, str] = {}
    for rp in all_progress:
        by_organ.setdefault(rp.organ, []).append(rp)
        organ_names[rp.organ] = rp.organ_name

    # Build organ organisms in canonical order
    organs = []
    seen = set()
    for oid in _ORGAN_ORDER:
        if oid in by_organ:
            organs.append(OrganOrganism(
                organ_id=oid,
                organ_name=organ_names[oid],
                repos=sorted(
                    by_organ[oid],
                    key=lambda x: (-x.pct, -x.score, x.repo),
                ),
            ))
            seen.add(oid)
    # Append any organs not in canonical order (e.g. PERSONAL)
    for oid in sorted(by_organ.keys()):
        if oid not in seen:
            organs.append(OrganOrganism(
                organ_id=oid,
                organ_name=organ_names[oid],
                repos=sorted(
                    by_organ[oid],
                    key=lambda x: (-x.pct, -x.score, x.repo),
                ),
            ))

    omega = None
    if include_omega:
        from organvm_engine.omega.scorecard import evaluate as eval_omega
        scorecard = eval_omega(registry=registry)
        omega = scorecard.to_dict()

    # Compute network metrics if workspace available
    network_data = None
    if workspace:
        try:
            from organvm_engine.network.ledger import ledger_summary
            from organvm_engine.network.mapper import discover_network_maps
            from organvm_engine.network.metrics import (
                convergence_points,
                mirror_coverage,
                network_density,
            )

            pairs = discover_network_maps(workspace)
            maps = [m for _, m in pairs]
            active = sum(1 for o in organs for r in o.repos if r.promo != "ARCHIVED")
            density = network_density(maps, active) if active else 0.0
            coverage = mirror_coverage(maps)
            summary = ledger_summary()
            conv = convergence_points(maps)

            network_data = {
                "density": round(density, 3),
                "coverage": {k: round(v, 3) for k, v in coverage.items()},
                "maps_count": len(maps),
                "total_mirrors": sum(m.mirror_count for m in maps),
                "convergence_points": len(conv),
                "engagement_actions": summary.get("total_actions", 0),
            }
        except Exception:
            pass

    organism = SystemOrganism(
        organs=organs,
        generated=datetime.now(timezone.utc).isoformat(),
        omega=omega,
        network=network_data,
    )

    # Emit organism computed event
    try:
        from organvm_engine.pulse.emitter import emit_engine_event
        from organvm_engine.pulse.types import ORGANISM_COMPUTED

        emit_engine_event(
            event_type=ORGANISM_COMPUTED,
            source="metrics",
            payload={
                "sys_pct": organism.sys_pct,
                "total_repos": organism.total_repos,
                "total_stale": organism.total_stale,
                "total_promo_ready": organism.total_promo_ready,
            },
        )
    except Exception:
        pass

    return organism


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_ORGANISM_CACHE: dict[str, object] = {
    "organism": None,
    "loaded_at": 0.0,
    "registry_mtime": None,
}
_ORGANISM_CACHE_LOCK = Lock()


def _get_registry_mtime(path: Path | None = None) -> float | None:
    from organvm_engine.paths import registry_path
    try:
        target = path if path is not None else registry_path()
        return target.stat().st_mtime
    except OSError:
        return None


def get_organism(
    registry: dict | None = None,
    workspace: Path | None = None,
    ttl: int = 30,
    include_omega: bool = False,
    registry_file: Path | None = None,
) -> SystemOrganism:
    """Get a cached SystemOrganism, recomputing if stale.

    Args:
        registry: Loaded registry dict. If None, loaded from default path.
        workspace: Workspace root.
        ttl: Cache TTL in seconds.
        include_omega: Include omega scorecard.

    Returns:
        SystemOrganism (possibly cached).
    """
    now = time.monotonic()
    current_mtime = _get_registry_mtime(registry_file)

    with _ORGANISM_CACHE_LOCK:
        cached = _ORGANISM_CACHE["organism"]
        loaded_at_raw = _ORGANISM_CACHE["loaded_at"]
        loaded_at = (
            float(loaded_at_raw)
            if isinstance(loaded_at_raw, (float, int))
            else 0.0
        )
        cached_mtime = _ORGANISM_CACHE["registry_mtime"]
        if (
            isinstance(cached, SystemOrganism)
            and now - loaded_at < ttl
            and cached_mtime == current_mtime
        ):
            return cached

    if registry is None:
        from organvm_engine.paths import registry_path
        from organvm_engine.registry.loader import load_registry
        target_registry = registry_file if registry_file is not None else registry_path()
        registry = load_registry(target_registry)

    organism = compute_organism(
        registry, workspace=workspace, include_omega=include_omega,
    )

    with _ORGANISM_CACHE_LOCK:
        _ORGANISM_CACHE["organism"] = organism
        _ORGANISM_CACHE["loaded_at"] = now
        _ORGANISM_CACHE["registry_mtime"] = current_mtime

    return organism


def clear_organism_cache() -> None:
    """Clear the organism cache."""
    with _ORGANISM_CACHE_LOCK:
        _ORGANISM_CACHE["organism"] = None
        _ORGANISM_CACHE["loaded_at"] = 0.0
        _ORGANISM_CACHE["registry_mtime"] = None
