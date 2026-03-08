"""Operational pattern definitions and taxonomy for prompt distillation.

Defines 15 recurring workflow patterns identified from clipboard prompt analysis.
Each pattern has regex signals, keyword signals, and category affinities for scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OperationalPattern:
    """A recurring operational workflow pattern extracted from prompt analysis."""

    id: str
    label: str
    tier: str  # T1 (operational) | T2 (system) | T3 (organ) | T4 (repo)
    phase: str  # genesis | foundation | hardening | graduation | sustaining | any
    scope: str  # system | organ | repo
    regex_signals: tuple[re.Pattern[str], ...] = field(default_factory=tuple)
    keyword_signals: tuple[str, ...] = field(default_factory=tuple)
    category_affinity: tuple[str, ...] = field(default_factory=tuple)
    sop_name_hint: str = ""
    sop_name_aliases: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""


def _compile(*patterns: str) -> tuple[re.Pattern[str], ...]:
    """Compile regex patterns with IGNORECASE."""
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


OPERATIONAL_PATTERNS: dict[str, OperationalPattern] = {
    "scaffold": OperationalPattern(
        id="scaffold",
        label="Project Initialization / Scaffolding",
        tier="T2",
        phase="genesis",
        scope="system",
        regex_signals=_compile(
            r"skeleton\s+structure",
            r"scaffold",
            r"/init\b",
            r"speckit",
            r"bootstrap",
            r"boilerplate",
            r"starter\s+(template|project)",
        ),
        keyword_signals=(
            "scaffold", "skeleton", "bootstrap", "boilerplate",
            "init", "speckit", "starter", "seed project",
        ),
        category_affinity=("ORGANVM System", "GitHub/CI/CD"),
        sop_name_hint="project-scaffolding",
        sop_name_aliases=("repo-onboarding", "habitat-creation"),
        description="Setting up new projects from templates or conventions.",
    ),
    "ingest": OperationalPattern(
        id="ingest",
        label="Document Ingestion / Full Audit",
        tier="T2",
        phase="foundation",
        scope="system",
        regex_signals=_compile(
            r"ingest",
            r"digest",
            r"100\s*%",
            r"every\s+file",
            r"top\s+to\s+bottom",
            r"thorough\s+(read|audit|review)",
        ),
        keyword_signals=(
            "ingest", "digest", "every file", "top to bottom",
            "thorough", "comprehensive audit", "full read",
        ),
        category_affinity=("Data/Research", "ORGANVM System"),
        sop_name_hint="document-ingestion-and-audit",
        sop_name_aliases=("document-audit-feature-extraction",),
        description="Comprehensive ingestion and audit of document sets.",
    ),
    "eval-cycle": OperationalPattern(
        id="eval-cycle",
        label="Evaluation / Critique / Growth Cycle",
        tier="T1",
        phase="any",
        scope="system",
        regex_signals=_compile(
            r"critique",
            r"reinforcement",
            r"risk\s+analysis",
            r"growth",
            r"evaluation.to.growth",
            r"self.critique",
        ),
        keyword_signals=(
            "critique", "reinforcement", "risk analysis", "growth",
            "evaluation", "self-critique", "feedback loop",
        ),
        category_affinity=(),
        sop_name_hint="evaluation-and-growth-cycle",
        description="Systematic critique → reinforcement → risk → growth cycles.",
    ),
    "plan-roadmap": OperationalPattern(
        id="plan-roadmap",
        label="Planning and Roadmapping",
        tier="T2",
        phase="genesis",
        scope="system",
        regex_signals=_compile(
            r"devise.*plan",
            r"there.*back.*again",
            r"alpha.*omega",
            r"roadmap",
            r"macro.*micro",
            r"extensive.*plan",
            r"exhaustive.*plan",
            r"phased\s+plan",
        ),
        keyword_signals=(
            "plan", "roadmap", "devise", "there and back again",
            "alpha to omega", "macro", "micro", "phased",
            "milestones", "strategy",
        ),
        category_affinity=("ORGANVM System",),
        sop_name_hint="planning-and-roadmapping",
        description="Devising extensive/exhaustive plans with phased execution.",
    ),
    "research": OperationalPattern(
        id="research",
        label="Market / Competitive Research",
        tier="T2",
        phase="genesis",
        scope="system",
        regex_signals=_compile(
            r"market\s+gap",
            r"competitor",
            r"landscape",
            r"research\s+report",
            r"espionage",
            r"competitive\s+analysis",
        ),
        keyword_signals=(
            "market gap", "competitor", "landscape", "research report",
            "espionage", "competitive analysis", "market research",
        ),
        category_affinity=("Data/Research",),
        sop_name_hint="market-and-competitive-research",
        sop_name_aliases=(
            "market-gap-analysis", "research-to-implementation-pipeline",
        ),
        description="Market gap analysis, competitive landscape research.",
    ),
    "manifest": OperationalPattern(
        id="manifest",
        label="Manifest / Annotated Bibliography",
        tier="T3",
        phase="foundation",
        scope="organ",
        regex_signals=_compile(
            r"manifest",
            r"annotated\s+bibliography",
            r"tagged.*annotated",
            r"catalog",
            r"inventory\s+of",
        ),
        keyword_signals=(
            "manifest", "annotated bibliography", "catalog",
            "inventory", "tagged", "annotated",
        ),
        category_affinity=("ORGANVM System", "Data/Research"),
        sop_name_hint="project-manifest-and-bibliography",
        description="Creating annotated bibliography manifests and inventories.",
    ),
    "rename": OperationalPattern(
        id="rename",
        label="Ontological Renaming",
        tier="T3",
        phase="foundation",
        scope="organ",
        regex_signals=_compile(
            r"rename.*ontological",
            r"dense.*meaningful",
            r"latin.*greek",
            r"etymolog",
            r"ontological.*name",
        ),
        keyword_signals=(
            "rename", "ontological", "dense", "meaningful",
            "latin", "greek", "etymological", "nomenclature",
        ),
        category_affinity=("ORGANVM System",),
        sop_name_hint="ontological-renaming",
        description="Dense, meaningful naming with etymological roots.",
    ),
    "commit-push": OperationalPattern(
        id="commit-push",
        label="Commit / Push / Release Workflow",
        tier="T1",
        phase="any",
        scope="repo",
        regex_signals=_compile(
            r"stage\s+all",
            r"commit\s+all",
            r"push.*origin",
            r"brewup",
            r"git\s+push",
        ),
        keyword_signals=(
            "stage all", "commit all", "push origin",
            "git push", "commit and push", "release",
        ),
        category_affinity=("GitHub/CI/CD",),
        sop_name_hint="commit-and-release-workflow",
        description="Staging, committing, pushing, and release workflows.",
    ),
    "completeness": OperationalPattern(
        id="completeness",
        label="Completeness Verification / Final Sweep",
        tier="T1",
        phase="hardening",
        scope="system",
        regex_signals=_compile(
            r"beautiful\s+bow",
            r"eat\s+off\s+the\s+floor",
            r"perfection",
            r"wrapped\s+with",
            r"final\s+sweep",
            r"nothing\s+left\s+undone",
        ),
        keyword_signals=(
            "beautiful bow", "eat off the floor", "perfection",
            "wrapped with", "final sweep", "completeness",
            "nothing left undone", "polished",
        ),
        category_affinity=(),
        sop_name_hint="completeness-verification",
        description="End-to-end completeness sweep before declaring done.",
    ),
    "agent-seed": OperationalPattern(
        id="agent-seed",
        label="Agent Seeding / Workforce Planning",
        tier="T2",
        phase="foundation",
        scope="system",
        regex_signals=_compile(
            r"agent.*workforce",
            r"parallel.*streams",
            r"deep\s+agent",
            r"department",
            r"workstream\s+decomp",
            r"agent\s+seed",
        ),
        keyword_signals=(
            "agent", "workforce", "parallel streams", "deep agent",
            "department", "workstream", "seed agents",
        ),
        category_affinity=("MCP/Tooling", "ORGANVM System"),
        sop_name_hint="agent-seeding-and-workforce-planning",
        description="Deep agent seeding, parallel workstream decomposition.",
    ),
    "readme-docs": OperationalPattern(
        id="readme-docs",
        label="README / Documentation Generation",
        tier="T2",
        phase="foundation",
        scope="repo",
        regex_signals=_compile(
            r"problem.*approach.*outcome",
            r"hero\s+section",
            r"README",
            r"world.class.*readme",
            r"documentation\s+gen",
        ),
        keyword_signals=(
            "README", "hero section", "documentation",
            "problem approach outcome", "world-class readme",
        ),
        category_affinity=("GitHub/CI/CD",),
        sop_name_hint="readme-and-documentation",
        description="Generating READMEs and project documentation.",
    ),
    "feature-expand": OperationalPattern(
        id="feature-expand",
        label="Feature Expansion / Exhaustive Build",
        tier="T3",
        phase="foundation",
        scope="repo",
        regex_signals=_compile(
            r"expand.*features",
            r"extensively.*exhaustively",
            r"full.breath",
            r"every\s+possible\s+feature",
            r"comprehensive.*implement",
        ),
        keyword_signals=(
            "expand features", "extensively", "exhaustively",
            "full breath", "comprehensive", "every possible",
        ),
        category_affinity=(),
        sop_name_hint="feature-expansion",
        description="Exhaustive feature expansion and implementation.",
    ),
    "session-state": OperationalPattern(
        id="session-state",
        label="Session State Management",
        tier="T1",
        phase="any",
        scope="system",
        regex_signals=_compile(
            r"save.*session",
            r"session\s+state",
            r"session\s+ID",
            r"remember\s+this",
            r"continue\s+from",
        ),
        keyword_signals=(
            "save session", "session state", "session ID",
            "remember this", "continue from", "pick up where",
        ),
        category_affinity=("MCP/Tooling",),
        sop_name_hint="session-state-management",
        description="Saving and restoring AI session state across contexts.",
    ),
    "gh-issues": OperationalPattern(
        id="gh-issues",
        label="GitHub Issue / Blocker Triage",
        tier="T1",
        phase="any",
        scope="repo",
        regex_signals=_compile(
            r"create.*issue",
            r"GH\s+issue",
            r"human\s+intervention",
            r"blocker",
            r"github\s+issue",
        ),
        keyword_signals=(
            "create issue", "GH issue", "human intervention",
            "blocker", "github issue", "triage",
        ),
        category_affinity=("GitHub/CI/CD",),
        sop_name_hint="github-issue-triage",
        description="Creating and triaging GitHub issues and blockers.",
    ),
    "biz-organism": OperationalPattern(
        id="biz-organism",
        label="Business Organism Design",
        tier="T2",
        phase="genesis",
        scope="system",
        regex_signals=_compile(
            r"business\s+organism",
            r"phased\s+activation",
            r"three.scenario",
            r"department",
            r"revenue\s+model",
        ),
        keyword_signals=(
            "business organism", "phased activation", "three-scenario",
            "department", "revenue model", "business design",
        ),
        category_affinity=("ORGANVM System",),
        sop_name_hint="business-organism-design",
        description="Business organism design with phased activation and scenario modeling.",
    ),
}


def get_pattern(pattern_id: str) -> OperationalPattern | None:
    """Retrieve a pattern by ID."""
    return OPERATIONAL_PATTERNS.get(pattern_id)


def all_pattern_ids() -> list[str]:
    """Return all pattern IDs in definition order."""
    return list(OPERATIONAL_PATTERNS.keys())
