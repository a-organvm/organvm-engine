"""Backflow pipeline — route knowledge from contributions back into organs.

Thesis (essay-8): one contribution generates seven typed returns.
Each contribution is classified by knowledge type and routed to the
appropriate organ for capture.

Signal types and their destination organs:
- THEORY: Formal patterns, algorithms, proofs → ORGAN-I
- GENERATIVE: Creative artifacts, visualizations → ORGAN-II
- SHIPPED_CODE: Production patterns, APIs → ORGAN-III
- ORCHESTRATION: Governance insights, tooling → ORGAN-IV
- NARRATIVE: Case studies, essays, public process → ORGAN-V
- COMMUNITY: Relationship capital, reputation → ORGAN-VI
- DISTRIBUTION: Announcement material, social proof → ORGAN-VII
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from organvm_engine.contrib.discover import ContribRepo
from organvm_engine.contrib.status import ContribStatus, PRState


class SignalType(Enum):
    """Knowledge signal types routed through the backflow pipeline."""

    THEORY = "theory"
    GENERATIVE = "generative"
    SHIPPED_CODE = "shipped_code"
    ORCHESTRATION = "orchestration"
    NARRATIVE = "narrative"
    COMMUNITY = "community"
    DISTRIBUTION = "distribution"


# Signal type → destination organ mapping
SIGNAL_ORGAN_MAP: dict[SignalType, str] = {
    SignalType.THEORY: "I",
    SignalType.GENERATIVE: "II",
    SignalType.SHIPPED_CODE: "III",
    SignalType.ORCHESTRATION: "IV",
    SignalType.NARRATIVE: "V",
    SignalType.COMMUNITY: "VI",
    SignalType.DISTRIBUTION: "VII",
}


@dataclass
class BackflowSignal:
    """A typed knowledge signal from a contribution."""

    source: ContribRepo
    signal_type: SignalType
    destination_organ: str
    content: str
    confidence: float = 1.0
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def organ_key(self) -> str:
        return SIGNAL_ORGAN_MAP.get(self.signal_type, "IV")


def classify_contribution(status: ContribStatus) -> list[BackflowSignal]:
    """Classify a contribution into backflow signals.

    Every contribution generates at minimum:
    - COMMUNITY signal (relationship capital from the interaction)
    - DISTRIBUTION signal (announcement material)

    Merged contributions additionally generate:
    - SHIPPED_CODE signal (the code pattern was accepted)
    - NARRATIVE signal (case study material)

    Language-specific heuristics add THEORY signals for formal languages
    and GENERATIVE signals for creative tooling.

    Args:
        status: The contribution's current status.

    Returns:
        List of BackflowSignal objects to be routed.
    """
    signals: list[BackflowSignal] = []
    repo = status.repo

    # Every contribution generates community capital
    signals.append(BackflowSignal(
        source=repo,
        signal_type=SignalType.COMMUNITY,
        destination_organ="VI",
        content=f"Contribution to {repo.target_repo}: {status.title}",
        metadata={"pr_state": status.state.value},
    ))

    # Every open or merged PR is distribution material
    if status.state in (PRState.OPEN, PRState.MERGED):
        signals.append(BackflowSignal(
            source=repo,
            signal_type=SignalType.DISTRIBUTION,
            destination_organ="VII",
            content=f"PR #{repo.target_pr} on {repo.target_repo}: {status.title}",
            metadata={"pr_url": repo.pr_url or ""},
        ))

    # Merged PRs generate shipped code signals
    if status.state == PRState.MERGED:
        signals.append(BackflowSignal(
            source=repo,
            signal_type=SignalType.SHIPPED_CODE,
            destination_organ="III",
            content=f"Merged: {status.title} ({repo.language or 'unknown'})",
            confidence=1.0,
        ))

        # Merged PRs are also narrative material (case study)
        signals.append(BackflowSignal(
            source=repo,
            signal_type=SignalType.NARRATIVE,
            destination_organ="V",
            content=f"Case study: contribution to {repo.target_repo}",
            metadata={"essay_candidate": "true"},
        ))

    # Language-based heuristics for theory signals
    if repo.language and repo.language.lower() in ("haskell", "coq", "lean", "agda", "idris"):
        signals.append(BackflowSignal(
            source=repo,
            signal_type=SignalType.THEORY,
            destination_organ="I",
            content=f"Formal language contribution: {repo.language}",
            confidence=0.7,
        ))

    # Orchestration signals from governance/infra contributions
    if any(kw in (status.title or "").lower() for kw in ("governance", "workflow", "ci", "action")):
        signals.append(BackflowSignal(
            source=repo,
            signal_type=SignalType.ORCHESTRATION,
            destination_organ="IV",
            content=f"Orchestration pattern: {status.title}",
            confidence=0.6,
        ))

    return signals


def generate_backflow_report(statuses: list[ContribStatus]) -> dict[str, list[BackflowSignal]]:
    """Generate a full backflow report grouped by destination organ.

    Args:
        statuses: List of contribution statuses to process.

    Returns:
        Dict mapping organ key to list of signals destined for that organ.
    """
    all_signals: dict[str, list[BackflowSignal]] = {
        "I": [], "II": [], "III": [], "IV": [],
        "V": [], "VI": [], "VII": [],
    }

    for status in statuses:
        signals = classify_contribution(status)
        for signal in signals:
            organ = SIGNAL_ORGAN_MAP.get(signal.signal_type, "IV")
            all_signals[organ].append(signal)

    return all_signals


def write_backflow_manifest(
    report: dict[str, list[BackflowSignal]],
    output_dir: Path,
) -> Path:
    """Write the backflow report as a YAML manifest.

    Args:
        report: Backflow report from generate_backflow_report.
        output_dir: Directory to write the manifest.

    Returns:
        Path to the written manifest file.
    """
    import yaml
    from datetime import datetime, timezone

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_signals": sum(len(signals) for signals in report.values()),
        "organs": {},
    }

    for organ, signals in report.items():
        if signals:
            manifest["organs"][f"ORGAN-{organ}"] = [
                {
                    "source": s.source.name,
                    "type": s.signal_type.value,
                    "content": s.content,
                    "confidence": s.confidence,
                    **({"metadata": s.metadata} if s.metadata else {}),
                }
                for s in signals
            ]

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "backflow-manifest.yaml"
    manifest_path.write_text(yaml.dump(manifest, default_flow_style=False, sort_keys=False))
    return manifest_path
