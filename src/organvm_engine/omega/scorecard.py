"""Omega scorecard — 19 criteria for system completion.

Evaluates the 19 omega criteria defined in there+back-again.md.
Criteria that can be auto-assessed from soak data or registry are
evaluated automatically; others report their manual status.

Constitutional amendment (2026-03-20): Old #9 (revenue_status: live)
and #10 (MRR ≥ costs) replaced with craft-first criteria:
  #9  → ≥3 products at stranger-ready polish
  #10 → ≥100 unique visitors/month (organic discovery)
  #18 → First organic revenue (gated behind #9 + #10)
Revenue follows traffic follows quality follows craft.

Amendment (2026-03-21): #19 — Network Testament health check.
  network_density >= 0.5 AND engagement_velocity > 0
  AND ≥1 milestone in testament/milestones/.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from organvm_engine.paths import corpus_dir as _default_corpus_dir
from organvm_engine.paths import soak_dir as _default_soak_dir
from organvm_engine.paths import workspace_root as _default_workspace_root

# ── Soak streak analysis ────────────────────────────────────────────


@dataclass
class SoakStreak:
    """Result of analyzing soak test data for consecutive-day streak."""

    total_snapshots: int = 0
    streak_days: int = 0
    first_date: str = ""
    last_date: str = ""
    gaps: list[str] = field(default_factory=list)
    critical_incidents: int = 0
    target_days: int = 30
    start_date: str = "2026-02-16"

    @property
    def days_remaining(self) -> int:
        return max(0, self.target_days - self.streak_days)

    @property
    def target_met(self) -> bool:
        return self.streak_days >= self.target_days and self.critical_incidents <= 3


def analyze_soak_streak(soak_dir: Path | str | None = None) -> SoakStreak:
    """Analyze soak test daily snapshots for consecutive-day streak.

    Reads daily-*.json files, calculates the longest consecutive streak
    ending at the most recent date, identifies gaps, and counts critical
    incidents (days where validation failed).
    """
    d = Path(soak_dir) if soak_dir else _default_soak_dir()
    result = SoakStreak()

    if not d.is_dir():
        return result

    snapshots = []
    for path in sorted(d.glob("daily-*.json")):
        with path.open() as f:
            snapshots.append(json.load(f))

    if not snapshots:
        return result

    result.total_snapshots = len(snapshots)
    result.first_date = snapshots[0].get("date", "")
    result.last_date = snapshots[-1].get("date", "")

    # Parse dates and find gaps
    dates = []
    for snap in snapshots:
        date_str = snap.get("date", "")
        try:
            dates.append(date.fromisoformat(date_str))
        except ValueError:
            continue

    if not dates:
        return result

    dates.sort()

    # Find gaps
    for i in range(1, len(dates)):
        delta = (dates[i] - dates[i - 1]).days
        if delta > 1:
            for gap_day in range(1, delta):
                gap_date = dates[i - 1] + timedelta(days=gap_day)
                result.gaps.append(gap_date.isoformat())

    # Calculate consecutive streak ending at the latest date
    streak = 1
    for i in range(len(dates) - 1, 0, -1):
        if (dates[i] - dates[i - 1]).days == 1:
            streak += 1
        else:
            break
    result.streak_days = streak

    # Count critical incidents (days where validation had operational issues).
    # Schema-only registry failures (missing fields) are metadata gaps, not
    # operational incidents — exclude them from the incident count.
    for snap in snapshots:
        validation = snap.get("validation", {})
        if not validation.get("dependency_pass", True):
            result.critical_incidents += 1
            continue
        if not validation.get("registry_pass", True):
            issues = validation.get("registry_issues", [])
            has_operational_issue = any(
                "missing field" not in issue for issue in issues
            )
            if has_operational_issue:
                result.critical_incidents += 1

    return result


# ── Omega criteria definitions ──────────────────────────────────────


@dataclass
class OmegaCriterion:
    """A single omega criterion."""

    id: int
    name: str
    horizon: str
    measurement: str
    auto: bool
    status: str  # NOT_MET, IN_PROGRESS, MET
    value: str
    evidence: str = ""


@dataclass
class OmegaScorecard:
    """Complete omega scorecard with all 19 criteria."""

    criteria: list[OmegaCriterion]
    soak: SoakStreak
    generated: str = ""

    @property
    def met_count(self) -> int:
        return sum(1 for c in self.criteria if c.status == "MET")

    @property
    def in_progress_count(self) -> int:
        return sum(1 for c in self.criteria if c.status == "IN_PROGRESS")

    @property
    def total(self) -> int:
        return len(self.criteria)

    def summary(self) -> str:
        """Human-readable summary for terminal output."""
        lines = []
        lines.append(f"Omega Scorecard: {self.met_count}/{self.total} MET")
        lines.append(f"{'─' * 60}")

        for c in self.criteria:
            marker = "■" if c.status == "MET" else ("▪" if c.status == "IN_PROGRESS" else "□")
            status_str = f"{c.status:<12}"
            lines.append(f"  {marker} #{c.id:<3} {c.name:<45} {status_str} {c.value}")

        lines.append(f"{'─' * 60}")
        lines.append(
            f"  {self.met_count} MET, {self.in_progress_count} IN PROGRESS, "
            f"{self.total - self.met_count - self.in_progress_count} NOT MET",
        )

        if self.soak.total_snapshots > 0:
            lines.append("")
            lines.append("  Soak Test Streak")
            lines.append(f"  {'─' * 40}")
            lines.append(f"    Consecutive days: {self.soak.streak_days}/{self.soak.target_days}")
            lines.append(f"    Days remaining:   {self.soak.days_remaining}")
            lines.append(f"    Data range:       {self.soak.first_date} → {self.soak.last_date}")
            lines.append(f"    Snapshots:        {self.soak.total_snapshots}")
            lines.append(f"    Critical incidents: {self.soak.critical_incidents}")
            if self.soak.gaps:
                lines.append(f"    Gaps:             {', '.join(self.soak.gaps[:5])}")
                if len(self.soak.gaps) > 5:
                    lines.append(f"                      ... and {len(self.soak.gaps) - 5} more")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Machine-readable dict for JSON output."""
        return {
            "score": self.met_count,
            "total": self.total,
            "in_progress": self.in_progress_count,
            "generated": self.generated,
            "criteria": [asdict(c) for c in self.criteria],
            "soak": asdict(self.soak),
        }


# ── Scorecard evaluator ────────────────────────────────────────────


# Criteria that are known to be MET from the roadmap (with evidence)
_KNOWN_MET = {
    1: ("30-day soak test passes", "32/30 days, 0 incidents, passed 2026-03-18"),
    5: ("≥1 application submitted", "Doris Duke / Mozilla AMT, submitted 2026-02-24"),
    6: ("AI-conductor essay published", "public-process essay #9, 2026-02-12"),
    8: ("≥1 ORGAN-III product live", "12 products live across Netlify/Render, 2026-02-28"),
    13: ("≥1 organic inbound link", "LobeHub organic indexing of ORGAN-IV skills, 2026-02-28"),
    15: ("Portfolio updated with validation", "validation page at 4444j99.github.io/portfolio/validation/, 2026-03-19"),
    17: ("System operates 30+ days autonomously", "58+ days autonomous as of 2026-04-14, passed 2026-03-18"),
}


@dataclass
class NetworkTestamentResult:
    """Result of evaluating network testament health."""

    density: float = 0.0
    velocity: float = 0.0
    milestones: int = 0
    maps_found: int = 0
    total_mirrors: int = 0
    ledger_entries: int = 0

    @property
    def met(self) -> bool:
        return self.density >= 0.5 and self.velocity > 0 and self.milestones >= 1


def _check_network_testament(
    workspace_root: Path | str | None = None,
    corpus_dir: Path | str | None = None,
) -> NetworkTestamentResult:
    """Check network testament health for omega criterion #19.

    Evaluates three conditions:
    1. network_density >= 0.5 (majority of active repos have mirrors)
    2. engagement_velocity > 0 (at least one engagement action recorded)
    3. ≥1 milestone file in corpus data/testament/milestones/

    Returns:
        NetworkTestamentResult with all measured values.
    """
    result = NetworkTestamentResult()

    # 1. Network density — discover maps and compute coverage
    try:
        from organvm_engine.network.mapper import discover_network_maps
        from organvm_engine.network.metrics import engagement_velocity, network_density

        ws = Path(workspace_root) if workspace_root else _default_workspace_root()
        maps_with_paths = discover_network_maps(ws)
        maps = [nmap for _, nmap in maps_with_paths]
        result.maps_found = len(maps)
        result.total_mirrors = sum(m.mirror_count for m in maps)

        # Use maps_found as proxy for total active repos with network maps
        # A density of 0.5 means at least half of repos with maps have mirrors
        total_repos_with_maps = len(maps)
        if total_repos_with_maps > 0:
            result.density = network_density(maps, total_repos_with_maps)
        else:
            result.density = 0.0
    except Exception:
        pass

    # 2. Engagement velocity — read ledger and check for any activity
    try:
        from organvm_engine.network.ledger import read_ledger

        entries = read_ledger()
        result.ledger_entries = len(entries)
        result.velocity = engagement_velocity(entries, period_days=30) if entries else 0.0
    except Exception:
        pass

    # 3. Milestones — check for testament milestone files
    try:
        cd = Path(corpus_dir) if corpus_dir else _default_corpus_dir()
        milestones_dir = cd / "data" / "testament" / "milestones"
        if milestones_dir.is_dir():
            result.milestones = sum(
                1 for f in milestones_dir.iterdir()
                if f.is_file() and f.suffix in (".md", ".json", ".yaml", ".yml")
            )
    except Exception:
        pass

    return result


def evaluate(
    registry: dict | None = None,
    soak_dir: Path | str | None = None,
    workspace_root: Path | str | None = None,
    corpus_dir: Path | str | None = None,
) -> OmegaScorecard:
    """Evaluate all 19 omega criteria.

    Auto-assesses criteria from soak data and registry where possible.
    Returns the complete scorecard.
    """
    soak = analyze_soak_streak(soak_dir)

    # Check if engagement baseline is established (30+ days of data)
    engagement_baseline = soak.total_snapshots >= 30
    soak_value = f"{soak.streak_days}/{soak.target_days} days, {soak.critical_incidents} incidents"

    # Evaluate network testament health
    net = _check_network_testament(
        workspace_root=workspace_root,
        corpus_dir=corpus_dir,
    )

    criteria = [
        OmegaCriterion(
            id=1,
            name="30-day soak test passes (≤3 incidents)",
            horizon="H1",
            measurement="Soak test report",
            auto=True,
            status="MET"
            if soak.target_met
            else ("IN_PROGRESS" if soak.total_snapshots > 0 else "NOT_MET"),
            value=soak_value,
        ),
        OmegaCriterion(
            id=2,
            name="Stranger test score ≥80%",
            horizon="H1",
            measurement="Test protocol results",
            auto=False,
            status="NOT_MET",
            value="Protocol ready, no participant",
        ),
        OmegaCriterion(
            id=3,
            name="Engagement baseline (30 days of data)",
            horizon="H1",
            measurement="Engagement report",
            auto=True,
            status="MET"
            if engagement_baseline
            else ("IN_PROGRESS" if soak.total_snapshots > 0 else "NOT_MET"),
            value=f"{soak.total_snapshots} days of data",
        ),
        OmegaCriterion(
            id=4,
            name="Runbooks validated by second operator",
            horizon="H1",
            measurement="Validation log",
            auto=False,
            status="NOT_MET",
            value="Runbooks written, not validated",
        ),
        OmegaCriterion(
            id=5,
            name="≥1 application submitted",
            horizon="H2",
            measurement="Application tracker",
            auto=False,
            status="MET",
            value="1 submitted (Doris Duke / Mozilla AMT)",
            evidence="Doris Duke / Mozilla AMT, submitted 2026-02-24",
        ),
        OmegaCriterion(
            id=6,
            name="AI-conductor essay published",
            horizon="H2",
            measurement="Public-process URL",
            auto=False,
            status="MET",
            value="Essay #9 published",
            evidence="public-process essay #9, 2026-02-12",
        ),
        OmegaCriterion(
            id=7,
            name="≥3 external feedback collected",
            horizon="H2",
            measurement="Feedback synthesis doc",
            auto=False,
            status="NOT_MET",
            value="0 feedback",
        ),
        OmegaCriterion(
            id=8,
            name="≥1 ORGAN-III product live",
            horizon="H3",
            measurement="Product URL + user count",
            auto=False,
            status="MET",
            value="12 products live across Netlify/Render",
            evidence=_KNOWN_MET[8][1],
        ),
        OmegaCriterion(
            id=9,
            name="≥3 products at stranger-ready polish",
            horizon="H3",
            measurement="Stranger test per product (UI, docs, onboarding, zero rough edges)",
            auto=False,
            status="NOT_MET",
            value="Products live but polish not validated",
            evidence="Replaces old #9 (premature revenue). Craft before commerce.",
        ),
        OmegaCriterion(
            id=10,
            name="≥100 unique visitors/month (organic discovery)",
            horizon="H3",
            measurement="Analytics across portfolio + portal + products",
            auto=False,
            status="NOT_MET",
            value="No analytics tracking configured",
            evidence="Replaces old #10 (premature MRR). Traffic before monetization.",
        ),
        OmegaCriterion(
            id=11,
            name="≥2 salons/events with external participants",
            horizon="H4",
            measurement="Event records",
            auto=False,
            status="NOT_MET",
            value="Infrastructure only",
        ),
        OmegaCriterion(
            id=12,
            name="≥3 external contributions",
            horizon="H4",
            measurement="GitHub activity",
            auto=False,
            status="NOT_MET",
            value="5 good-first-issues created",
        ),
        OmegaCriterion(
            id=13,
            name="≥1 organic inbound link",
            horizon="H4",
            measurement="Analytics",
            auto=False,
            status="MET",
            value="LobeHub organic indexing of ORGAN-IV skills",
            evidence=_KNOWN_MET[13][1],
        ),
        OmegaCriterion(
            id=14,
            name="≥1 recognition event",
            horizon="H5",
            measurement="Evidence URL",
            auto=False,
            status="NOT_MET",
            value="0 external recognition",
        ),
        OmegaCriterion(
            id=15,
            name="Portfolio updated with validation",
            horizon="H5",
            measurement="Portfolio site",
            auto=False,
            status="MET",
            value="Validation page live at portfolio/validation/",
            evidence=_KNOWN_MET[15][1],
        ),
        OmegaCriterion(
            id=16,
            name="Bus factor >1 (validated)",
            horizon="H1+H4",
            measurement="Second operator log",
            auto=False,
            status="NOT_MET",
            value="Runbooks written, not tested",
        ),
        OmegaCriterion(
            id=17,
            name="System operates 30+ days autonomously",
            horizon="H1",
            measurement="Soak test data",
            auto=True,
            status="MET"
            if soak.target_met
            else ("IN_PROGRESS" if soak.total_snapshots > 0 else "NOT_MET"),
            value=f"{soak.streak_days}/{soak.target_days} days",
        ),
        OmegaCriterion(
            id=18,
            name="First organic revenue (inquiry → payment)",
            horizon="H5",
            measurement="Payment record from someone who found the work organically",
            auto=False,
            status="NOT_MET",
            value="Gated behind #9 (product quality) and #10 (organic traffic)",
            evidence="Constitutional amendment: craft → traffic → inquiry → revenue. "
            "Revenue is an outcome, not a feature to bolt on.",
        ),
        OmegaCriterion(
            id=19,
            name="Network Testament health (density + engagement + milestones)",
            horizon="H3",
            measurement="network_density >= 0.5, engagement_velocity > 0, ≥1 milestone",
            auto=True,
            status="MET" if net.met else (
                "IN_PROGRESS"
                if net.maps_found > 0 or net.ledger_entries > 0
                else "NOT_MET"
            ),
            value=(
                f"density={net.density:.2f}, velocity={net.velocity:.2f}, "
                f"milestones={net.milestones}, maps={net.maps_found}, "
                f"mirrors={net.total_mirrors}"
            ),
            evidence="Network testament tracks external mirror coverage, "
            "engagement velocity, and accumulated milestones.",
        ),
    ]

    scorecard = OmegaScorecard(
        criteria=criteria,
        soak=soak,
        generated=datetime.now().isoformat(timespec="seconds"),
    )

    # Emit to Testament Chain if any criteria flipped
    from organvm_engine.ledger.emit import testament_emit
    met = [c for c in criteria if c.status == "MET"]
    testament_emit(
        event_type="metrics.update",
        source_organ="META-ORGANVM",
        source_repo="organvm-engine",
        actor="cli",
        payload={
            "metric": "omega",
            "met_count": len(met),
            "total": len(criteria),
            "met_ids": [c.id for c in met],
        },
    )

    return scorecard


# ── Snapshot writer ──────────────────────────────────────────────


def write_snapshot(
    scorecard: OmegaScorecard,
    corpus_dir: Path | str | None = None,
) -> Path:
    """Write an omega status snapshot to the corpus data directory.

    Creates data/omega/omega-status-{date}.json for longitudinal tracking.

    Returns:
        Path to the written file.
    """
    d = Path(corpus_dir) if corpus_dir else _default_corpus_dir()
    omega_dir = d / "data" / "omega"
    omega_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    path = omega_dir / f"omega-status-{today}.json"
    path.write_text(json.dumps(scorecard.to_dict(), indent=2, default=str) + "\n")
    return path


def diff_snapshots(
    current: OmegaScorecard,
    corpus_dir: Path | str | None = None,
) -> list[str]:
    """Compare current scorecard to most recent snapshot and report changes.

    Returns:
        List of human-readable change descriptions.
    """
    d = Path(corpus_dir) if corpus_dir else _default_corpus_dir()
    omega_dir = d / "data" / "omega"

    if not omega_dir.is_dir():
        return ["No previous snapshots found."]

    snapshots = sorted(omega_dir.glob("omega-status-*.json"))
    if not snapshots:
        return ["No previous snapshots found."]

    with snapshots[-1].open() as f:
        prev = json.load(f)

    changes = []
    prev_score = prev.get("score", 0)
    curr_score = current.met_count

    if curr_score != prev_score:
        changes.append(f"Score changed: {prev_score} → {curr_score}")

    # Compare individual criteria
    prev_criteria = {c["id"]: c for c in prev.get("criteria", [])}
    for c in current.criteria:
        pc = prev_criteria.get(c.id)
        if pc and pc.get("status") != c.status:
            changes.append(f"  #{c.id} {c.name}: {pc['status']} → {c.status}")

    # Soak streak changes
    prev_streak = prev.get("soak", {}).get("streak_days", 0)
    if current.soak.streak_days != prev_streak:
        changes.append(f"Soak streak: {prev_streak} → {current.soak.streak_days} days")

    if not changes:
        changes.append("No changes since last snapshot.")

    return changes
