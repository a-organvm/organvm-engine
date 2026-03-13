"""Organism diffing — detect what changed between two system snapshots.

Compares two SystemOrganism instances and produces a PulseSnapshot
summarising gate-level and repo-level deltas.  The snapshot feeds
the temporal and affective layers so they can detect trends and mood.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from organvm_engine.metrics.organism import SystemOrganism

# ---------------------------------------------------------------------------
# Delta dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GateDelta:
    """Change in a single gate's aggregate pass rate between two snapshots."""

    gate: str
    prev_rate: int
    curr_rate: int

    @property
    def delta(self) -> int:
        return self.curr_rate - self.prev_rate

    @property
    def direction(self) -> str:
        if self.delta > 0:
            return "up"
        if self.delta < 0:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "prev_rate": self.prev_rate,
            "curr_rate": self.curr_rate,
            "delta": self.delta,
            "direction": self.direction,
        }


@dataclass
class RepoDelta:
    """Change in a single repo's progress between two snapshots."""

    repo: str
    organ: str
    prev_pct: int
    curr_pct: int
    prev_promo: str
    curr_promo: str

    @property
    def pct_delta(self) -> int:
        return self.curr_pct - self.prev_pct

    @property
    def promoted(self) -> bool:
        return self.curr_promo != self.prev_promo

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "organ": self.organ,
            "prev_pct": self.prev_pct,
            "curr_pct": self.curr_pct,
            "pct_delta": self.pct_delta,
            "prev_promo": self.prev_promo,
            "curr_promo": self.curr_promo,
            "promoted": self.promoted,
        }


# ---------------------------------------------------------------------------
# Pulse snapshot
# ---------------------------------------------------------------------------

@dataclass
class PulseSnapshot:
    """Summary of what changed between two organism snapshots."""

    timestamp: str
    prev_sys_pct: int
    curr_sys_pct: int
    total_repos: int
    stale: int
    promo_ready: int
    gate_deltas: list[GateDelta] = field(default_factory=list)
    repo_deltas: list[RepoDelta] = field(default_factory=list)
    new_repos: list[str] = field(default_factory=list)
    removed_repos: list[str] = field(default_factory=list)

    @property
    def sys_pct_delta(self) -> int:
        return self.curr_sys_pct - self.prev_sys_pct

    @property
    def stale_delta(self) -> int:
        """Not meaningful without prev_stale stored — returns current count."""
        return self.stale

    @property
    def has_changes(self) -> bool:
        return bool(
            self.sys_pct_delta
            or self.gate_deltas
            or self.repo_deltas
            or self.new_repos
            or self.removed_repos,
        )

    def significant_changes(self) -> list[str]:
        """Human-readable list of noteworthy changes."""
        changes: list[str] = []
        if self.sys_pct_delta:
            direction = "up" if self.sys_pct_delta > 0 else "down"
            changes.append(
                f"System health {direction} {abs(self.sys_pct_delta)}pp "
                f"({self.prev_sys_pct}% -> {self.curr_sys_pct}%)",
            )
        for gd in self.gate_deltas:
            if gd.delta != 0:
                changes.append(
                    f"Gate {gd.gate} {gd.direction} {abs(gd.delta)}pp "
                    f"({gd.prev_rate}% -> {gd.curr_rate}%)",
                )
        for rd in self.repo_deltas:
            if rd.promoted:
                changes.append(
                    f"{rd.repo} promoted: {rd.prev_promo} -> {rd.curr_promo}",
                )
            elif rd.pct_delta != 0:
                direction = "improved" if rd.pct_delta > 0 else "regressed"
                changes.append(
                    f"{rd.repo} {direction} {abs(rd.pct_delta)}pp",
                )
        for name in self.new_repos:
            changes.append(f"New repo: {name}")
        for name in self.removed_repos:
            changes.append(f"Removed repo: {name}")
        return changes

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "prev_sys_pct": self.prev_sys_pct,
            "curr_sys_pct": self.curr_sys_pct,
            "sys_pct_delta": self.sys_pct_delta,
            "total_repos": self.total_repos,
            "stale": self.stale,
            "promo_ready": self.promo_ready,
            "has_changes": self.has_changes,
            "gate_deltas": [gd.to_dict() for gd in self.gate_deltas],
            "repo_deltas": [rd.to_dict() for rd in self.repo_deltas],
            "new_repos": self.new_repos,
            "removed_repos": self.removed_repos,
            "significant_changes": self.significant_changes(),
        }


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def compute_pulse(prev: SystemOrganism, curr: SystemOrganism) -> PulseSnapshot:
    """Diff two organism snapshots and produce a pulse summary.

    Args:
        prev: Earlier SystemOrganism snapshot.
        curr: Later SystemOrganism snapshot.

    Returns:
        PulseSnapshot describing everything that changed.
    """
    # Gate-level diffs
    prev_gates = {gs.name: gs.rate for gs in prev.gate_stats()}
    curr_gates = {gs.name: gs.rate for gs in curr.gate_stats()}
    gate_deltas: list[GateDelta] = []
    for name, cr in curr_gates.items():
        pr = prev_gates.get(name, 0)
        if pr != cr:
            gate_deltas.append(GateDelta(gate=name, prev_rate=pr, curr_rate=cr))

    # Repo-level diffs
    prev_repos = {r.repo: r for r in prev.all_repos}
    curr_repos = {r.repo: r for r in curr.all_repos}

    repo_deltas: list[RepoDelta] = []
    for name, cr in curr_repos.items():
        pr = prev_repos.get(name)
        if pr is None:
            continue  # new repo — handled below
        if cr.pct != pr.pct or cr.promo != pr.promo:
            repo_deltas.append(RepoDelta(
                repo=name,
                organ=cr.organ,
                prev_pct=pr.pct,
                curr_pct=cr.pct,
                prev_promo=pr.promo,
                curr_promo=cr.promo,
            ))

    new_repos = sorted(set(curr_repos) - set(prev_repos))
    removed_repos = sorted(set(prev_repos) - set(curr_repos))

    return PulseSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        prev_sys_pct=prev.sys_pct,
        curr_sys_pct=curr.sys_pct,
        total_repos=curr.total_repos,
        stale=curr.total_stale,
        promo_ready=curr.total_promo_ready,
        gate_deltas=gate_deltas,
        repo_deltas=repo_deltas,
        new_repos=new_repos,
        removed_repos=removed_repos,
    )
