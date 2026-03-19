"""Organ placement scoring and audit — validates repo-to-organ affinity.

Uses organ-definitions.json to score how well each repo fits its current organ,
and can recommend alternative placements when affinity is low.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PlacementScore:
    """Score of a repo's fit within a specific organ."""

    organ: str
    score: int  # 0-100
    matched_inclusion: list[str] = field(default_factory=list)
    triggered_exclusion: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "organ": self.organ,
            "score": self.score,
            "matched_inclusion": self.matched_inclusion,
            "triggered_exclusion": self.triggered_exclusion,
            "notes": self.notes,
        }


@dataclass
class PlacementRecommendation:
    """Placement recommendation for a single repo."""

    repo_name: str
    current_organ: str
    scores: list[PlacementScore] = field(default_factory=list)
    flagged: bool = False

    def to_dict(self) -> dict:
        return {
            "repo_name": self.repo_name,
            "current_organ": self.current_organ,
            "scores": [s.to_dict() for s in self.scores],
            "flagged": self.flagged,
        }


@dataclass
class PlacementAudit:
    """Result of auditing all repo placements."""

    total_repos: int = 0
    well_placed: int = 0
    questionable: list[PlacementRecommendation] = field(default_factory=list)
    misplaced: list[PlacementRecommendation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_repos": self.total_repos,
            "well_placed": self.well_placed,
            "questionable": [r.to_dict() for r in self.questionable],
            "misplaced": [r.to_dict() for r in self.misplaced],
        }


def load_organ_definitions(path: Path | None = None) -> dict:
    """Load organ-definitions.json from the corpus directory."""
    if path is None:
        from organvm_engine.paths import corpus_dir

        path = corpus_dir() / "organ-definitions.json"

    if not path.exists():
        return {}

    with path.open() as f:
        return json.load(f)


# ── Keyword heuristics for scoring ──────────────────────────────

# Map organ keys to keyword signals that suggest affinity
_ORGAN_KEYWORDS: dict[str, list[str]] = {
    "ORGAN-I": [
        "engine", "framework", "theory", "ontolog", "recursive", "symbolic",
        "knowledge", "epistemo", "conceptual", "algorithm",
    ],
    "ORGAN-II": [
        "art", "generative", "creative", "performance", "visual", "audio",
        "interactive", "installation", "aesthetic", "poiesis",
    ],
    "ORGAN-III": [
        "product", "saas", "tool", "utility", "marketplace", "api",
        "service", "commerce", "app", "platform", "scrapper", "scraper",
    ],
    "ORGAN-IV": [
        "orchestrat", "agent", "workflow", "routing", "conductor",
        "skill", "taxis", "coordinat",
    ],
    "ORGAN-V": [
        "essay", "editorial", "publication", "discourse", "logos",
        "public-process", "writing", "blog",
    ],
    "ORGAN-VI": [
        "community", "forum", "salon", "reading-group", "koinonia",
        "learning", "cohort",
    ],
    "ORGAN-VII": [
        "distribut", "syndicat", "posse", "announcement", "kerygma",
        "newsletter", "broadcast",
    ],
    "META-ORGANVM": [
        "registry", "schema", "dashboard", "corpus", "engine", "mcp",
        "governance", "pipeline", "meta",
    ],
}


def _keyword_score(repo: dict, organ_key: str) -> int:
    """Score 0-30 based on keyword matches in repo name and description."""
    keywords = _ORGAN_KEYWORDS.get(organ_key, [])
    if not keywords:
        return 15  # neutral

    name = repo.get("name", "").lower()
    desc = repo.get("description", "").lower()
    text = f"{name} {desc}"

    matches = sum(1 for kw in keywords if kw in text)
    # Max 30 points, scaled by match ratio
    return min(30, matches * 10)


def compute_affinity(
    repo: dict,
    organ_key: str,
    definitions: dict,
) -> PlacementScore:
    """Score a repo's fit in a specific organ (0-100)."""
    organs_defs = definitions.get("organs", {})
    organ_def = organs_defs.get(organ_key)

    if not organ_def:
        return PlacementScore(organ=organ_key, score=50, notes=["No definition found"])

    score = 50  # baseline
    matched_inc: list[str] = []
    triggered_exc: list[str] = []
    notes: list[str] = []

    # ── Revenue signal (strong) ──────────────────────────────────
    revenue = repo.get("revenue_model")
    has_revenue = revenue and revenue not in ("none", "internal")

    if organ_key == "ORGAN-III" and has_revenue:
        score += 20
        matched_inc.append("Has revenue model")
    elif organ_key != "ORGAN-III" and has_revenue:
        score -= 25
        triggered_exc.append(f"Has revenue_model='{revenue}' — belongs in ORGAN-III")

    # ── Tier/type signal ─────────────────────────────────────────
    repo_type = repo.get("type", "")
    canonical_types = organ_def.get("canonical_repo_types", [])
    if repo_type and repo_type.lower() in [t.lower() for t in canonical_types]:
        score += 10
        matched_inc.append(f"Type '{repo_type}' matches canonical types")

    # ── Keyword heuristic ────────────────────────────────────────
    kw_score = _keyword_score(repo, organ_key)
    score += kw_score - 15  # adjust from neutral baseline
    if kw_score >= 20:
        matched_inc.append("Name/description keywords match organ domain")

    # ── CI/implementation signals ────────────────────────────────
    if organ_key == "ORGAN-III" and not repo.get("ci_workflow"):
        score -= 5
        notes.append("ORGAN-III repo without CI")
    if organ_key == "ORGAN-I" and repo.get("ci_workflow"):
        # Theory repos with CI are more likely to be real engines, good fit
        score += 5

    # ── Clamp ────────────────────────────────────────────────────
    score = max(0, min(100, score))

    return PlacementScore(
        organ=organ_key,
        score=score,
        matched_inclusion=matched_inc,
        triggered_exclusion=triggered_exc,
        notes=notes,
    )


def recommend_placement(
    repo: dict,
    definitions: dict,
) -> PlacementRecommendation:
    """Score repo against ALL organs and return ranked recommendations."""
    organs_defs = definitions.get("organs", {})
    current_organ = None

    # Determine current organ from registry context
    org = repo.get("org", "")
    from organvm_engine.organ_config import dir_to_registry_key

    d2r = dir_to_registry_key()
    current_organ = d2r.get(org, "")

    scores: list[PlacementScore] = []
    for organ_key in organs_defs:
        s = compute_affinity(repo, organ_key, definitions)
        scores.append(s)

    scores.sort(key=lambda s: s.score, reverse=True)

    flagged = False
    if current_organ and scores:
        current_score = next(
            (s for s in scores if s.organ == current_organ), None,
        )
        if (current_score and current_score.score < 50) or (
            current_score
            and scores[0].organ != current_organ
            and scores[0].score - current_score.score > 15
        ):
            flagged = True

    return PlacementRecommendation(
        repo_name=repo.get("name", "?"),
        current_organ=current_organ or "unknown",
        scores=scores,
        flagged=flagged,
    )


def audit_all_placements(
    registry: dict,
    definitions: dict,
) -> PlacementAudit:
    """Batch audit all repos for placement affinity."""
    from organvm_engine.registry.query import all_repos

    audit = PlacementAudit()

    for _organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue

        audit.total_repos += 1
        rec = recommend_placement(repo, definitions)

        if not rec.flagged:
            audit.well_placed += 1
        else:
            # Check severity: current organ score < 50 = misplaced
            current_score = next(
                (s for s in rec.scores if s.organ == rec.current_organ),
                None,
            )
            if current_score and current_score.score < 50:
                audit.misplaced.append(rec)
            else:
                audit.questionable.append(rec)

    return audit
