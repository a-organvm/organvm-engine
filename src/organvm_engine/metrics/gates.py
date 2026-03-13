"""Per-repo gate evaluation — 10-gate alpha-to-omega progress model.

Extracted from system-dashboard/routes/progress.py into the engine so
all consumers (dashboard, MCP, CLI, portal) share one computation path.

Gate order: SEED, SCAFFOLD, CI, TESTS, DOCS, PROTO, CAND, DEPLOY, GRAD, OMEGA

Each gate returns a GateResult; a full repo evaluation returns a RepoProgress
with all gates, score, profile detection, and promotion readiness.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.organ_config import ORGANS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GATE_ORDER = ("SEED", "SCAFFOLD", "CI", "TESTS", "DOCS", "PROTO", "CAND", "DEPLOY", "GRAD", "OMEGA")

IMPL_ORDER = {
    "ARCHIVED": 0, "DESIGN_ONLY": 1, "SKELETON": 2,
    "PROTOTYPE": 3, "ACTIVE": 4, "PRODUCTION": 4,
}
PROMO_ORDER = {
    "ARCHIVED": -1, "LOCAL": 0, "CANDIDATE": 1,
    "PUBLIC_PROCESS": 2, "GRADUATED": 3,
}
STALE_WARN = 30
STALE_CRIT = 90
DOCS_THRESHOLD = {
    "flagship": 1000, "standard": 500, "infrastructure": 100,
    "stub": 50, "archive": 0,
}

PROFILES: dict[str, set[str]] = {
    "code-full": set(),
    "documentation": {"TESTS", "DEPLOY"},
    "infrastructure": {"TESTS", "DOCS", "PROTO", "DEPLOY", "GRAD", "OMEGA"},
    "governance": {"TESTS", "PROTO", "DEPLOY"},
    "stub": {"TESTS", "DOCS", "PROTO", "DEPLOY", "GRAD", "OMEGA"},
    "archived": {"OMEGA"},
}

LANG_EXTS = {".py": "Python", ".ts": "TypeScript", ".js": "JavaScript", ".rs": "Rust", ".go": "Go"}

# Derived organ mapping dicts from canonical organ_config
ORG_TO_ORGAN: dict[str, str] = {}
for _info in ORGANS.values():
    ORG_TO_ORGAN[_info["org"]] = _info["registry_key"]
    ORG_TO_ORGAN[_info["dir"]] = _info["registry_key"]

ORGAN_DIRS: dict[str, list[str]] = {
    _info["registry_key"]: [_info["dir"]] for _info in ORGANS.values()
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Result of evaluating a single gate."""

    name: str
    passed: bool
    applicable: bool = True
    detail: str = ""
    next_action: str = ""
    discrepancy: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "passed": self.passed,
            "applicable": self.applicable,
            "detail": self.detail,
            "next_action": self.next_action,
        }
        if self.discrepancy:
            d["discrepancy"] = self.discrepancy
        return d


@dataclass
class ScaffoldInfo:
    """Filesystem scaffold detection results."""

    readme_words: int = 0
    has_readme: bool = False
    has_gitignore: bool = False
    has_license: bool = False
    has_changelog: bool = False
    has_claude_md: bool = False
    has_contributing: bool = False

    def to_dict(self) -> dict:
        return {
            "readme_words": self.readme_words,
            "has_readme": self.has_readme,
            "has_gitignore": self.has_gitignore,
            "has_license": self.has_license,
            "has_changelog": self.has_changelog,
            "has_claude_md": self.has_claude_md,
            "has_contributing": self.has_contributing,
        }


@dataclass
class RepoProgress:
    """Full gate evaluation for a single repository."""

    repo: str
    organ: str
    organ_name: str
    tier: str
    profile: str
    promo: str
    impl: str
    description: str
    deployment_url: str
    platinum: bool
    revenue_model: str
    revenue_status: str
    gates: list[GateResult]
    score: int
    total: int
    pct: int
    languages: dict[str, int]
    primary_lang: str
    stale_days: int
    is_stale: bool
    is_warn_stale: bool
    scaffold: ScaffoldInfo
    promo_ready: bool
    next_promo: str
    blockers: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    discrepancies: list[GateResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "organ": self.organ,
            "organ_name": self.organ_name,
            "tier": self.tier,
            "profile": self.profile,
            "promo": self.promo,
            "impl": self.impl,
            "description": self.description,
            "deployment_url": self.deployment_url,
            "platinum": self.platinum,
            "revenue_model": self.revenue_model,
            "revenue_status": self.revenue_status,
            "gates": [g.to_dict() for g in self.gates],
            "score": self.score,
            "total": self.total,
            "pct": self.pct,
            "languages": self.languages,
            "primary_lang": self.primary_lang,
            "stale_days": self.stale_days,
            "is_stale": self.is_stale,
            "is_warn_stale": self.is_warn_stale,
            "scaffold": self.scaffold.to_dict(),
            "promo_ready": self.promo_ready,
            "next_promo": self.next_promo,
            "blockers": self.blockers,
            "next_actions": self.next_actions,
            "discrepancies": [g.to_dict() for g in self.discrepancies],
        }


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

_CODE_EXTS = {".py", ".ts", ".js", ".rs", ".go", ".java"}
_CODE_DIRS = {"src", "lib", "titan", "agents", "hive", "adapters", "runtime", "pkg", "cmd"}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".build"}


def has_code(path: Path) -> bool:
    """Detect whether a repo directory contains source code."""
    for d in _CODE_DIRS:
        if (path / d).is_dir():
            return True
    try:
        for item in path.iterdir():
            if item.is_file() and item.suffix in _CODE_EXTS:
                return True
            if item.is_dir() and not item.name.startswith("."):
                try:
                    if any(s.suffix in _CODE_EXTS for s in item.iterdir() if s.is_file()):
                        return True
                except PermissionError:
                    continue
    except PermissionError:
        pass
    return False


def detect_profile(entry: dict, local: Path | None) -> str:
    """Determine the evaluation profile for a repo."""
    tier = entry.get("tier", "standard")
    impl = entry.get("implementation_status", "ACTIVE")
    promo = entry.get("promotion_status", "LOCAL")
    doc = entry.get("documentation_status", "")
    name = entry.get("name", "")

    if promo == "ARCHIVED" or tier == "archive":
        return "archived"
    if tier == "stub":
        return "stub"
    if tier == "infrastructure" or doc == "INFRASTRUCTURE":
        return "infrastructure"
    if impl == "DESIGN_ONLY":
        return "documentation"

    gov_kw = {"petasum", "governance", "commandments", "policy", "constitution"}
    if any(kw in name.lower() for kw in gov_kw):
        if local and has_code(local):
            return "code-full"
        return "governance"
    if local and not has_code(local):
        return "documentation"
    return "code-full"


def find_local(entry: dict, organ_id: str, workspace: Path) -> Path | None:
    """Find the local filesystem path for a registry entry."""
    if not workspace.is_dir():
        return None
    org = entry.get("org", "")
    name = entry.get("name", "")
    if not name:
        return None
    for key, dirs in ORGAN_DIRS.items():
        if organ_id == key or org in dirs:
            for d in dirs:
                c = workspace / d / name
                if c.is_dir():
                    return c
    if org:
        c = workspace / org / name
        if c.is_dir():
            return c
    return None


def detect_langs(local: Path | None) -> dict[str, int]:
    """Detect programming languages used in a repo."""
    if not local:
        return {}
    counts: dict[str, int] = defaultdict(int)

    def walk(p: Path, d: int = 0) -> None:
        if d > 3:
            return
        try:
            for item in p.iterdir():
                if item.name in _SKIP_DIRS:
                    continue
                if item.is_file():
                    lang = LANG_EXTS.get(item.suffix)
                    if lang:
                        counts[lang] += 1
                elif item.is_dir() and not item.name.startswith("."):
                    walk(item, d + 1)
        except PermissionError:
            pass

    walk(local)
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def stale_days(entry: dict) -> int:
    """Calculate days since last_validated."""
    lv = entry.get("last_validated", "")
    if not lv:
        return -1
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(str(lv))).days
    except (ValueError, TypeError):
        return -1


def scaffold_info(local: Path | None) -> ScaffoldInfo:
    """Detect scaffold files in a local repo."""
    if not local:
        return ScaffoldInfo()
    readme = local / "README.md"
    wc = len(readme.read_text(errors="replace").split()) if readme.is_file() else 0
    return ScaffoldInfo(
        readme_words=wc,
        has_readme=readme.is_file(),
        has_gitignore=(local / ".gitignore").is_file(),
        has_license=any((local / f).is_file() for f in ("LICENSE", "LICENSE.md", "LICENSE.txt")),
        has_changelog=(local / "CHANGELOG.md").is_file(),
        has_claude_md=(local / "CLAUDE.md").is_file(),
        has_contributing=any(
            (local / f).is_file() for f in ("CONTRIBUTING.md", ".github/CONTRIBUTING.md")
        ),
    )


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

def _next_action(gate: str, passed: bool, entry: dict, tier: str) -> str:
    if passed:
        return ""
    actions = {
        "SEED": "Create seed.yaml with schema_version, organ, repo",
        "SCAFFOLD": "Add README.md and .gitignore",
        "CI": "Add .github/workflows/ci.yml",
        "TESTS": "Create tests/ with initial test file"
        if tier != "flagship"
        else "Add >=10 test files (flagship)",
        "DOCS": f"Expand README to >={DOCS_THRESHOLD.get(tier, 500)} words + add CHANGELOG.md",
        "PROTO": (
            f"Advance implementation from "
            f"{entry.get('implementation_status', '?')} to PROTOTYPE+"
        ),
        "CAND": f"Promote from {entry.get('promotion_status', '?')} to CANDIDATE",
        "DEPLOY": "Deploy and set deployment_url in registry",
        "GRAD": f"Promote from {entry.get('promotion_status', '?')} to GRADUATED",
        "OMEGA": "Clear all gates + set platinum_status=true",
    }
    return actions.get(gate, "")


def eval_gate(
    gate: str, entry: dict, local: Path | None, tier: str, scaf: ScaffoldInfo,
) -> GateResult:
    """Evaluate a single gate for a repo entry."""
    if gate == "SEED":
        if local:
            sp = local / "seed.yaml"
            if sp.is_file():
                return GateResult(name="SEED", passed=True, detail="seed.yaml present")
            return GateResult(name="SEED", passed=False, detail="seed.yaml missing")
        return GateResult(name="SEED", passed=True, detail="in registry")

    if gate == "SCAFFOLD":
        if local:
            ok = scaf.has_readme and scaf.has_gitignore
            parts = []
            if scaf.has_readme:
                parts.append(f"README({scaf.readme_words}w)")
            if scaf.has_gitignore:
                parts.append(".gitignore")
            if scaf.has_license:
                parts.append("LICENSE")
            if scaf.has_claude_md:
                parts.append("CLAUDE.md")
            return GateResult(name="SCAFFOLD", passed=ok, detail=", ".join(parts) or "missing")
        doc = entry.get("documentation_status", "")
        return GateResult(
            name="SCAFFOLD", passed=bool(doc) and doc not in ("", "NONE"), detail=f"doc={doc}",
        )

    if gate == "CI":
        reg_ci = entry.get("ci_workflow")
        if local:
            wf = local / ".github" / "workflows"
            local_ok = wf.is_dir() and any(wf.glob("*.yml"))
            passed = bool(reg_ci) and local_ok
            disc = "registry/local mismatch" if bool(reg_ci) != local_ok else ""
            return GateResult(name="CI", passed=passed, detail=reg_ci or "none", discrepancy=disc)
        return GateResult(name="CI", passed=bool(reg_ci), detail=reg_ci or "none")

    if gate == "TESTS":
        min_t = 10 if tier == "flagship" else 1
        if local:
            count = 0
            for td in ("tests", "__tests__", "test", "spec"):
                d = local / td
                if d.is_dir():
                    count += sum(1 for _ in d.rglob("*.py"))
                    count += sum(1 for _ in d.rglob("*.ts"))
                    count += sum(1 for _ in d.rglob("*.js"))
            detail = f"{count} files" + (f" (need {min_t})" if count < min_t else "")
            return GateResult(name="TESTS", passed=count >= min_t, detail=detail)
        return GateResult(name="TESTS", passed=False, detail="no local")

    if gate == "DOCS":
        doc = entry.get("documentation_status", "")
        reg_ok = doc in ("DEPLOYED", "FLAGSHIP README DEPLOYED")
        thresh = DOCS_THRESHOLD.get(tier, 500)
        if local:
            wc = scaf.readme_words
            cl = scaf.has_changelog
            local_ok = wc >= thresh and cl
            return GateResult(
                name="DOCS",
                passed=reg_ok or local_ok,
                detail=f"{wc}w/{thresh} {'+ CL' if cl else ''}",
            )
        return GateResult(name="DOCS", passed=reg_ok, detail=doc)

    if gate == "PROTO":
        impl = entry.get("implementation_status", "SKELETON")
        return GateResult(
            name="PROTO", passed=IMPL_ORDER.get(impl, 0) >= IMPL_ORDER["PROTOTYPE"], detail=impl,
        )

    if gate == "CAND":
        promo = entry.get("promotion_status", "LOCAL")
        return GateResult(name="CAND", passed=PROMO_ORDER.get(promo, 0) >= 1, detail=promo)

    if gate == "DEPLOY":
        url = entry.get("deployment_url", "")
        platform = entry.get("deployment_platform", "")
        detail = url or "none"
        if platform:
            detail += f" ({platform})"
        return GateResult(name="DEPLOY", passed=bool(url), detail=detail)

    if gate == "GRAD":
        promo = entry.get("promotion_status", "LOCAL")
        return GateResult(name="GRAD", passed=PROMO_ORDER.get(promo, 0) >= 3, detail=promo)

    if gate == "OMEGA":
        plat = entry.get("platinum_status", False)
        return GateResult(name="OMEGA", passed=plat, detail="platinum" if plat else "not platinum")

    return GateResult(name=gate, passed=False, detail="unknown")


def promo_ready(gates: list[GateResult], promo: str) -> bool:
    """Check if a repo is ready for the next promotion."""
    current = PROMO_ORDER.get(promo, 0)
    app = {g.name: g for g in gates if g.applicable}

    if current == 0:
        return all(
            app.get(g, GateResult(name=g, passed=False)).passed
            for g in ("SEED", "SCAFFOLD", "CI") if g in app
        )
    if current == 1:
        return all(
            app.get(g, GateResult(name=g, passed=False)).passed
            for g in ("SEED", "SCAFFOLD", "CI", "TESTS", "DOCS", "PROTO")
            if g in app
        )
    if current == 2:
        return all(g.passed for g in gates if g.applicable and g.name != "OMEGA")
    return False


def next_promo(promo: str) -> str:
    """Determine the next promotion target."""
    _rev = {v: k for k, v in PROMO_ORDER.items() if v >= 0}
    return _rev.get(PROMO_ORDER.get(promo, 0) + 1, "GRADUATED")


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------

def evaluate_repo(
    entry: dict,
    organ_id: str,
    organ_name: str,
    workspace: Path | None = None,
) -> RepoProgress:
    """Evaluate all gates for a single repo entry.

    Args:
        entry: Repo dict from registry.
        organ_id: Registry organ key (e.g. "ORGAN-I").
        organ_name: Human organ name (e.g. "Theory").
        workspace: Workspace root for filesystem checks. None = registry-only.

    Returns:
        RepoProgress with full gate evaluation.
    """
    local = find_local(entry, organ_id, workspace) if workspace else None
    profile = detect_profile(entry, local)
    skip = PROFILES[profile]
    tier = entry.get("tier", "standard")
    promo = entry.get("promotion_status", "LOCAL")
    scaf = scaffold_info(local)
    langs = detect_langs(local)
    stale = stale_days(entry)

    gates: list[GateResult] = []
    for g in GATE_ORDER:
        if g in skip:
            gates.append(GateResult(name=g, passed=False, applicable=False, detail="N/A"))
        else:
            ev = eval_gate(g, entry, local, tier, scaf)
            ev.next_action = _next_action(g, ev.passed, entry, tier)
            gates.append(ev)

    # OMEGA: require all prior applicable gates
    applicable_prior = [x for x in gates[:-1] if x.applicable]
    if gates[-1].applicable:
        all_ok = all(x.passed for x in applicable_prior) and gates[-1].passed
        gates[-1].passed = all_ok
        if not all_ok:
            failed = [x.name for x in applicable_prior if not x.passed]
            gates[-1].next_action = (
                f"Clear: {', '.join(failed)}" if failed
                else "Set platinum_status"
            )

    score = sum(1 for x in gates if x.applicable and x.passed)
    total = sum(1 for x in gates if x.applicable)
    ready = promo_ready(gates, promo)

    discs = [g for g in gates if g.discrepancy]
    blockers = [f"{g.name}: {g.detail}" for g in gates if g.applicable and not g.passed]
    actions = [g.next_action for g in gates if g.applicable and not g.passed and g.next_action]

    primary = "none"
    if langs:
        non_meta = [k for k in langs if k not in ("Markdown", "YAML", "JSON")]
        if non_meta:
            primary = max(non_meta, key=lambda k: langs[k])

    return RepoProgress(
        repo=entry.get("name", "?"),
        organ=organ_id,
        organ_name=organ_name,
        tier=tier,
        profile=profile,
        promo=promo,
        impl=entry.get("implementation_status", "?"),
        description=entry.get("description", ""),
        deployment_url=entry.get("deployment_url", ""),
        platinum=entry.get("platinum_status", False),
        revenue_model=entry.get("revenue_model", ""),
        revenue_status=entry.get("revenue_status", ""),
        gates=gates,
        score=score,
        total=total,
        pct=int(score / total * 100) if total else 0,
        languages=langs,
        primary_lang=primary,
        stale_days=stale,
        is_stale=stale > STALE_CRIT or stale == -1,
        is_warn_stale=STALE_WARN < stale <= STALE_CRIT,
        scaffold=scaf,
        promo_ready=ready,
        next_promo=next_promo(promo),
        blockers=blockers,
        next_actions=actions,
        discrepancies=discs,
    )


def evaluate_all(
    registry: dict,
    workspace: Path | None = None,
) -> list[RepoProgress]:
    """Evaluate all repos in the registry.

    Args:
        registry: Loaded registry dict.
        workspace: Workspace root for filesystem checks.

    Returns:
        List of RepoProgress for every repo.
    """
    results = []
    for organ_id, organ_data in registry.get("organs", {}).items():
        organ_name = organ_data.get("name", organ_id)
        for entry in organ_data.get("repositories", []):
            results.append(evaluate_repo(entry, organ_id, organ_name, workspace))

    # Emit batch gate evaluation event
    try:
        from organvm_engine.pulse.emitter import emit_engine_event
        from organvm_engine.pulse.types import GATE_EVALUATED

        total = len(results)
        avg_pct = int(sum(r.pct for r in results) / total) if total else 0
        emit_engine_event(
            event_type=GATE_EVALUATED,
            source="metrics",
            payload={"total_repos": total, "avg_pct": avg_pct},
        )
    except Exception:
        pass

    return results


def evaluate_all_for_dashboard(
    registry: dict,
    workspace: Path | None = None,
) -> list[dict]:
    """Evaluate all repos and return dict format for dashboard backward compat.

    If workspace is None, uses ~/Workspace as default (matching old behavior).
    """
    if workspace is None:
        workspace = Path.home() / "Workspace"
    return [rp.to_dict() for rp in evaluate_all(registry, workspace)]
