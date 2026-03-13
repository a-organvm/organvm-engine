"""Tests for organvm_engine.pulse.heartbeat — organism diffing."""

from __future__ import annotations

from organvm_engine.metrics.gates import GateResult, RepoProgress, ScaffoldInfo
from organvm_engine.metrics.organism import GateStats, OrganOrganism, SystemOrganism
from organvm_engine.pulse.heartbeat import (
    GateDelta,
    PulseSnapshot,
    RepoDelta,
    compute_pulse,
)


# ---------------------------------------------------------------------------
# Helper: build minimal RepoProgress / SystemOrganism
# ---------------------------------------------------------------------------

def _gate(name: str, passed: bool = True) -> GateResult:
    return GateResult(name=name, passed=passed, applicable=True)


def _repo(
    name: str = "test-repo",
    organ: str = "ORGAN-I",
    pct: int = 50,
    promo: str = "CANDIDATE",
    gates: list[GateResult] | None = None,
) -> RepoProgress:
    default_gates = gates or [
        _gate("SEED"), _gate("SCAFFOLD"), _gate("CI"),
        _gate("TESTS", False), _gate("DOCS", False),
        _gate("PROTO"), _gate("CAND"), _gate("DEPLOY", False),
        _gate("GRAD", False), _gate("OMEGA", False),
    ]
    score = sum(1 for g in default_gates if g.applicable and g.passed)
    total = sum(1 for g in default_gates if g.applicable)
    return RepoProgress(
        repo=name,
        organ=organ,
        organ_name="Theory",
        tier="standard",
        profile="code-full",
        promo=promo,
        impl="ACTIVE",
        description="test",
        deployment_url="",
        platinum=False,
        revenue_model="",
        revenue_status="",
        gates=default_gates,
        score=score,
        total=total,
        pct=pct,
        languages={},
        primary_lang="Python",
        stale_days=0,
        is_stale=False,
        is_warn_stale=False,
        scaffold=ScaffoldInfo(),
        promo_ready=False,
        next_promo="PUBLIC_PROCESS",
    )


def _organism(
    repos: list[RepoProgress] | None = None,
    sys_pct: int | None = None,
) -> SystemOrganism:
    """Build a minimal SystemOrganism.

    If sys_pct is given, adjust repo pcts so the computed sys_pct matches.
    """
    if repos is None:
        repos = [_repo()]

    # Group by organ
    by_organ: dict[str, list[RepoProgress]] = {}
    for r in repos:
        by_organ.setdefault(r.organ, []).append(r)

    organs = [
        OrganOrganism(organ_id=oid, organ_name="Test", repos=rlist)
        for oid, rlist in by_organ.items()
    ]
    org = SystemOrganism(organs=organs, generated="2026-01-01T00:00:00+00:00")

    # If caller wants a specific sys_pct, override all repos to match
    if sys_pct is not None and repos:
        for r in repos:
            object.__setattr__(r, "pct", sys_pct)
    return org


# ---------------------------------------------------------------------------
# GateDelta
# ---------------------------------------------------------------------------

class TestGateDelta:
    def test_gate_delta_properties(self):
        """delta and direction are computed correctly."""
        gd = GateDelta(gate="CI", prev_rate=40, curr_rate=60)
        assert gd.delta == 20
        assert gd.direction == "up"

    def test_gate_delta_down(self):
        gd = GateDelta(gate="TESTS", prev_rate=80, curr_rate=60)
        assert gd.delta == -20
        assert gd.direction == "down"

    def test_gate_delta_stable(self):
        """Same rate produces direction='flat'."""
        gd = GateDelta(gate="DOCS", prev_rate=50, curr_rate=50)
        assert gd.delta == 0
        assert gd.direction == "flat"

    def test_gate_delta_to_dict(self):
        gd = GateDelta(gate="CI", prev_rate=40, curr_rate=60)
        d = gd.to_dict()
        assert d["gate"] == "CI"
        assert d["delta"] == 20
        assert d["direction"] == "up"


# ---------------------------------------------------------------------------
# RepoDelta
# ---------------------------------------------------------------------------

class TestRepoDelta:
    def test_repo_delta_promoted(self):
        """Different promotion states produce promoted=True."""
        rd = RepoDelta(
            repo="r1", organ="ORGAN-I",
            prev_pct=50, curr_pct=60,
            prev_promo="CANDIDATE", curr_promo="PUBLIC_PROCESS",
        )
        assert rd.promoted is True
        assert rd.pct_delta == 10

    def test_repo_delta_not_promoted(self):
        """Same promotion state produces promoted=False."""
        rd = RepoDelta(
            repo="r1", organ="ORGAN-I",
            prev_pct=50, curr_pct=60,
            prev_promo="CANDIDATE", curr_promo="CANDIDATE",
        )
        assert rd.promoted is False

    def test_repo_delta_to_dict(self):
        rd = RepoDelta(
            repo="r1", organ="ORGAN-I",
            prev_pct=50, curr_pct=70,
            prev_promo="LOCAL", curr_promo="CANDIDATE",
        )
        d = rd.to_dict()
        assert d["repo"] == "r1"
        assert d["pct_delta"] == 20
        assert d["promoted"] is True


# ---------------------------------------------------------------------------
# PulseSnapshot
# ---------------------------------------------------------------------------

class TestPulseSnapshot:
    def test_pulse_no_changes(self):
        """Identical organisms produce has_changes=False."""
        r = _repo(pct=50, promo="CANDIDATE")
        org = _organism(repos=[r])
        pulse = compute_pulse(org, org)
        assert pulse.has_changes is False

    def test_pulse_sys_pct_change(self):
        """Different repo pcts result in a non-zero sys_pct_delta."""
        r1 = _repo(name="r1", pct=40)
        r2 = _repo(name="r1", pct=60)
        prev = _organism(repos=[r1])
        curr = _organism(repos=[r2])
        pulse = compute_pulse(prev, curr)
        assert pulse.sys_pct_delta == 20
        assert pulse.has_changes is True

    def test_pulse_gate_changes(self):
        """Different gate rates produce gate_deltas."""
        g_prev = [_gate("SEED"), _gate("CI", False)]
        g_curr = [_gate("SEED"), _gate("CI", True)]
        r_prev = _repo(name="r1", gates=g_prev, pct=50)
        r_curr = _repo(name="r1", gates=g_curr, pct=60)
        prev = _organism(repos=[r_prev])
        curr = _organism(repos=[r_curr])
        pulse = compute_pulse(prev, curr)
        # Gate-level deltas are based on aggregate gate_stats, which come from
        # the repo gates. With a single repo changing CI from fail to pass,
        # the CI gate aggregate goes from 0% to 100%.
        ci_deltas = [gd for gd in pulse.gate_deltas if gd.gate == "CI"]
        assert len(ci_deltas) == 1
        assert ci_deltas[0].direction == "up"

    def test_pulse_repo_promotion(self):
        """A repo promotion appears in repo_deltas with promoted=True."""
        r_prev = _repo(name="r1", pct=50, promo="CANDIDATE")
        r_curr = _repo(name="r1", pct=50, promo="PUBLIC_PROCESS")
        prev = _organism(repos=[r_prev])
        curr = _organism(repos=[r_curr])
        pulse = compute_pulse(prev, curr)
        promoted = [rd for rd in pulse.repo_deltas if rd.promoted]
        assert len(promoted) == 1
        assert promoted[0].repo == "r1"

    def test_pulse_new_repos(self):
        """A repo present in curr but not prev appears in new_repos."""
        r1 = _repo(name="r1")
        r2 = _repo(name="r2")
        prev = _organism(repos=[r1])
        curr = _organism(repos=[r1, r2])
        pulse = compute_pulse(prev, curr)
        assert "r2" in pulse.new_repos

    def test_pulse_significant_changes(self):
        """significant_changes() returns human-readable strings."""
        r_prev = _repo(name="r1", pct=40, promo="LOCAL")
        r_curr = _repo(name="r1", pct=60, promo="CANDIDATE")
        prev = _organism(repos=[r_prev])
        curr = _organism(repos=[r_curr])
        pulse = compute_pulse(prev, curr)
        changes = pulse.significant_changes()
        assert len(changes) >= 1
        # Should mention the promotion
        promo_changes = [c for c in changes if "promoted" in c.lower()]
        assert len(promo_changes) >= 1

    def test_pulse_to_dict(self):
        """to_dict() serializes all expected keys."""
        r = _repo()
        org = _organism(repos=[r])
        pulse = compute_pulse(org, org)
        d = pulse.to_dict()
        expected_keys = {
            "timestamp", "prev_sys_pct", "curr_sys_pct", "sys_pct_delta",
            "total_repos", "stale", "promo_ready", "has_changes",
            "gate_deltas", "repo_deltas", "new_repos", "removed_repos",
            "significant_changes",
        }
        assert expected_keys.issubset(set(d.keys()))
