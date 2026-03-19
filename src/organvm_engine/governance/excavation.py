"""Excavation engine — multi-scale scanner for buried entities within repos.

Surfaces sub-packages, cross-organ families, extractable modules, and
misplaced governance artifacts. Produces structured reports with
remediation recommendations.
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BuriedEntity:
    """A single buried entity finding."""

    repo: str
    organ: str
    entity_path: str
    entity_type: str  # sub_package | cross_organ_family | extractable_module | misplaced_governance
    evidence: list[str] = field(default_factory=list)
    scale: dict[str, int] = field(default_factory=dict)
    severity: str = "info"
    recommendation: str = ""
    pattern: str = ""  # workspace | embedded_app | misplacement | unknown

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "organ": self.organ,
            "entity_path": self.entity_path,
            "entity_type": self.entity_type,
            "evidence": self.evidence,
            "scale": self.scale,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "pattern": self.pattern,
        }


@dataclass
class ExcavationReport:
    """Full excavation report across the workspace."""

    scanned_repos: int = 0
    total_findings: int = 0
    findings: list[BuriedEntity] = field(default_factory=list)
    by_type: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)
    cross_organ_families: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scanned_repos": self.scanned_repos,
            "total_findings": self.total_findings,
            "findings": [f.to_dict() for f in self.findings],
            "by_type": self.by_type,
            "by_severity": self.by_severity,
            "cross_organ_families": self.cross_organ_families,
        }


# ── Build manifest filenames that indicate a sub-package ────────

_BUILD_MANIFESTS = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
}


# ── Sub-package pattern classification ──────────────────────────
# Directories whose presence as an ancestor indicates a monorepo workspace
_WORKSPACE_PARENTS = {"packages", "apps", "services", "modules", "libs", "crates", "tools"}

# Known misplacements: (repo_name, sub_dir_str) tuples where the sub-package
# is a standalone project that clearly doesn't belong inside the parent
_KNOWN_MISPLACEMENTS: set[tuple[str, str]] = {
    ("organvm-corpvs-testamentvm", "portfolio-site"),
}


def _classify_sub_package(
    repo_name: str,
    sub_dir: Path,
    has_ci: bool,
) -> str:
    """Classify a sub-package into a structural pattern.

    Returns one of: workspace, embedded_app, misplacement.
    """
    sub_str = str(sub_dir)

    # Explicit misplacement overrides
    if (repo_name, sub_str) in _KNOWN_MISPLACEMENTS:
        return "misplacement"

    # Workspace pattern: sub-package sits under a conventional monorepo dir
    parts = sub_dir.parts
    if any(p in _WORKSPACE_PARENTS for p in parts):
        return "workspace"

    # Embedded app: has its own CI (strong independence signal) OR is a
    # top-level directory with its own build manifest (depth 1 nesting)
    if has_ci or len(parts) == 1:
        return "embedded_app"

    # Default: deeply nested build manifest, treat as embedded_app
    return "embedded_app"


_PATTERN_RECOMMENDATIONS = {
    "workspace": (
        "Monorepo workspace pattern — legitimate if using a workspace manager "
        "(npm/pnpm workspaces, Cargo workspace, Go modules). "
        "Verify workspace root config references this package."
    ),
    "embedded_app": (
        "Standalone application embedded inside a parent repo. "
        "Consider extracting to its own repo if it has an independent "
        "release cycle, team, or deployment target."
    ),
    "misplacement": (
        "This sub-package does not belong in its parent repo. "
        "Extract to an independent repo in the appropriate organ."
    ),
}


def scan_sub_packages(
    workspace: Path,
    registry: dict,
) -> list[BuriedEntity]:
    """Detect nested build manifests indicating embedded sub-packages."""
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.registry.query import all_repos

    findings: list[BuriedEntity] = []
    r2d = registry_key_to_dir()

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        name = repo.get("name", "")
        organ_dir = r2d.get(organ_key, "")
        if not organ_dir:
            continue

        repo_path = workspace / organ_dir / name
        if not repo_path.is_dir():
            continue

        # Walk looking for build manifests at depth > 0
        for manifest_name in _BUILD_MANIFESTS:
            for manifest_path in repo_path.rglob(manifest_name):
                rel = manifest_path.relative_to(repo_path)
                # Skip root-level manifests (that's the repo itself)
                if len(rel.parts) <= 1:
                    continue
                # Skip dependency/build/staging directories
                _SKIP_DIRS = {
                    "node_modules", ".venv", "new_venv", "__pycache__",
                    "dist", "build", "bench", "site-packages",
                    "vendor", "third_party", "egg-info",
                }
                if any(
                    p.startswith(".") or p in _SKIP_DIRS or p.endswith(".egg-info")
                    for p in rel.parts[:-1]
                ):
                    continue

                sub_dir = rel.parent
                evidence = [f"Found {manifest_name} at {rel}"]

                # Check for CI workflow in the sub-package
                has_ci = (repo_path / sub_dir / ".github" / "workflows").is_dir()
                if has_ci:
                    evidence.append("Has its own CI workflow")

                # Check for test directory
                has_tests = (repo_path / sub_dir / "tests").is_dir() or (
                    repo_path / sub_dir / "test"
                ).is_dir()
                if has_tests:
                    evidence.append("Has its own test suite")

                # Classify the pattern
                pattern = _classify_sub_package(name, sub_dir, has_ci)
                evidence.append(f"Pattern: {pattern}")

                # Severity depends on pattern + independence signals
                if pattern == "misplacement" or has_ci:
                    severity = "critical"
                elif pattern == "embedded_app":
                    severity = "warning"
                else:
                    # workspace pattern — legitimate, just informational
                    severity = "info"

                # Pattern-specific recommendation
                base_rec = _PATTERN_RECOMMENDATIONS[pattern]
                recommendation = (
                    f"'{sub_dir}' ({manifest_name}): {base_rec}"
                )

                findings.append(BuriedEntity(
                    repo=name,
                    organ=organ_key,
                    entity_path=str(sub_dir),
                    entity_type="sub_package",
                    evidence=evidence,
                    pattern=pattern,
                    severity=severity,
                    recommendation=recommendation,
                ))

    return findings


def scan_cross_organ_families(
    registry: dict,
) -> tuple[list[BuriedEntity], list[dict]]:
    """Detect repo name prefixes that span multiple organs."""
    from organvm_engine.registry.query import all_repos

    # Extract name stems: normalize double-hyphens, strip common suffixes
    stem_to_repos: dict[str, list[dict]] = {}

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        name = repo.get("name", "")
        if not name:
            continue

        # Extract stem: split on double-hyphen, take first part
        stem = name.split("--")[0] if "--" in name else name
        # Also try prefix before last hyphen for multi-word stems
        # e.g., "styx-behavioral-analysis" → "styx-behavioral"
        parts = stem.split("-")
        prefix = "-".join(parts[:2]) if len(parts) >= 2 else stem

        # Skip very short stems that would match too broadly
        if len(prefix) < 4:
            continue

        stem_to_repos.setdefault(prefix, []).append({
            "repo": name,
            "organ": organ_key,
        })

    findings: list[BuriedEntity] = []
    families: list[dict] = []

    for stem, members in stem_to_repos.items():
        organs = {m["organ"] for m in members}
        if len(organs) < 2:
            continue

        family = {
            "stem": stem,
            "members": members,
            "organ_count": len(organs),
        }
        families.append(family)

        for member in members:
            findings.append(BuriedEntity(
                repo=member["repo"],
                organ=member["organ"],
                entity_path="(repo-level)",
                entity_type="cross_organ_family",
                evidence=[
                    f"Name stem '{stem}' appears in {len(organs)} organs",
                    f"Family members: {', '.join(m['repo'] for m in members)}",
                ],
                severity="info",
                recommendation=(
                    f"Cross-organ family '{stem}' may need a unifying governance "
                    "entity (registry tag or cross-organ project definition)"
                ),
            ))

    return findings, families


def scan_extractable_modules(
    workspace: Path,
    registry: dict,
    file_threshold: int = 10,
    line_threshold: int = 2000,
) -> list[BuriedEntity]:
    """For Python packages, detect modules at extractable scale."""
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.registry.query import all_repos

    findings: list[BuriedEntity] = []
    r2d = registry_key_to_dir()

    # Directories to skip (dispatch packages, caches, etc.)
    skip_dirs = {"cli", "__pycache__", ".git", "node_modules", ".venv", "tests"}

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        name = repo.get("name", "")
        organ_dir = r2d.get(organ_key, "")
        if not organ_dir:
            continue

        repo_path = workspace / organ_dir / name
        if not repo_path.is_dir():
            continue

        # Look for src/ layout Python packages
        src_dirs = list(repo_path.glob("src/*/"))
        for pkg_dir in src_dirs:
            if not pkg_dir.is_dir() or pkg_dir.name.startswith("."):
                continue

            # Check each subdirectory (depth-1 module)
            for mod_dir in sorted(pkg_dir.iterdir()):
                if not mod_dir.is_dir():
                    continue
                if mod_dir.name in skip_dirs or mod_dir.name.startswith("_"):
                    continue

                py_files = list(mod_dir.glob("*.py"))
                file_count = len(py_files)
                if file_count < file_threshold:
                    continue

                # Count lines
                total_lines = 0
                for py_file in py_files:
                    with contextlib.suppress(OSError, UnicodeDecodeError):
                        total_lines += sum(1 for _ in py_file.open())

                evidence = [f"{file_count} Python files, {total_lines} lines"]

                if file_count >= file_threshold and total_lines >= line_threshold:
                    severity = "warning"
                else:
                    severity = "info"

                findings.append(BuriedEntity(
                    repo=name,
                    organ=organ_key,
                    entity_path=str(mod_dir.relative_to(repo_path)),
                    entity_type="extractable_module",
                    evidence=evidence,
                    scale={"files": file_count, "lines": total_lines},
                    severity=severity,
                    recommendation=(
                        f"Module '{mod_dir.name}' has {file_count} files / "
                        f"{total_lines} lines — consider extraction if it has "
                        "an independent release cycle"
                    ),
                ))

    return findings


# Governance artifact patterns
_GOVERNANCE_PATTERNS = [
    re.compile(r"^SOP[-_]", re.IGNORECASE),
    re.compile(r"^METADOC[-_]", re.IGNORECASE),
]
_GOVERNANCE_DIRS = {"governance", "policies", "standards"}
_GOVERNANCE_REPOS = {
    "organvm-corpvs-testamentvm",
    "praxis-perpetua",
    ".github",
}
_STANDARD_ROOT_FILES = {
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "LICENSE",
    "LICENSE.md",
    "SECURITY.md",
}


def scan_misplaced_governance(
    workspace: Path,
    registry: dict,
) -> list[BuriedEntity]:
    """Find governance artifacts in non-governance repos."""
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.registry.query import all_repos

    findings: list[BuriedEntity] = []
    r2d = registry_key_to_dir()

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        name = repo.get("name", "")
        if name in _GOVERNANCE_REPOS:
            continue

        organ_dir = r2d.get(organ_key, "")
        if not organ_dir:
            continue

        repo_path = workspace / organ_dir / name
        if not repo_path.is_dir():
            continue

        # Check for governance directories
        for gov_dir_name in _GOVERNANCE_DIRS:
            gov_path = repo_path / gov_dir_name
            if gov_path.is_dir():
                file_count = sum(1 for _ in gov_path.rglob("*") if _.is_file())
                if file_count > 0:
                    findings.append(BuriedEntity(
                        repo=name,
                        organ=organ_key,
                        entity_path=gov_dir_name,
                        entity_type="misplaced_governance",
                        evidence=[f"Directory '{gov_dir_name}/' with {file_count} files"],
                        scale={"files": file_count},
                        severity="warning",
                        recommendation=(
                            f"Governance artifacts in '{gov_dir_name}/' should be "
                            "in praxis-perpetua or organvm-corpvs-testamentvm"
                        ),
                    ))

        # Check for SOP/METADOC files at root
        for child in repo_path.iterdir():
            if not child.is_file():
                continue
            if child.name in _STANDARD_ROOT_FILES:
                continue
            for pattern in _GOVERNANCE_PATTERNS:
                if pattern.search(child.name):
                    findings.append(BuriedEntity(
                        repo=name,
                        organ=organ_key,
                        entity_path=child.name,
                        entity_type="misplaced_governance",
                        evidence=[f"File '{child.name}' matches governance naming pattern"],
                        severity="warning",
                        recommendation=(
                            f"'{child.name}' should be in praxis-perpetua/standards/ "
                            "or cross-referenced from there"
                        ),
                    ))
                    break

    return findings


# ── .gitmodules parsing ──────────────────────────────────────────

_GITHUB_URL_RE = re.compile(r"github\.com[:/]([^/]+)/([^/.]+)")


def _parse_gitmodules(gitmodules_path: Path) -> list[dict]:
    """Parse a .gitmodules file into submodule entry dicts.

    Each entry: {name, path, url, github_org, github_repo}.
    """
    entries: list[dict] = []
    if not gitmodules_path.is_file():
        return entries
    with contextlib.suppress(OSError, UnicodeDecodeError):
        current: dict | None = None
        for line in gitmodules_path.read_text().splitlines():
            line = line.strip()
            m = re.match(r'\[submodule "(.+)"\]', line)
            if m:
                current = {
                    "name": m.group(1), "path": "", "url": "",
                    "github_org": "", "github_repo": "",
                }
                entries.append(current)
                continue
            if current is None or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key == "path":
                current["path"] = value
            elif key == "url":
                current["url"] = value
                gm = _GITHUB_URL_RE.search(value)
                if gm:
                    current["github_org"] = gm.group(1)
                    current["github_repo"] = gm.group(2)
    return entries


def scan_submodule_topology(
    workspace: Path,
    registry: dict,
) -> list[BuriedEntity]:
    """Detect mismatches between git submodule infrastructure and registry.

    Surfaces:
    - superproject_mismatch: repo registered in organ X but submodule of organ Y
    - org_mismatch: .gitmodules URL org differs from registry org field
    - dual_homed: repo appears in multiple organ superprojects
    - submodule_orphan: in a .gitmodules but absent from registry
    """
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.registry.query import all_repos

    findings: list[BuriedEntity] = []
    r2d = registry_key_to_dir()
    d2r = {v: k for k, v in r2d.items()}

    # Build registry lookup: repo_name → (organ_key, org_field)
    registry_map: dict[str, tuple[str, str]] = {}
    for organ_key, repo in all_repos(registry):
        name = repo.get("name", "")
        if name:
            registry_map[name] = (organ_key, repo.get("org", ""))

    # Parse all organ superproject .gitmodules
    submod_by_repo: dict[str, list[tuple[str, dict]]] = {}
    for organ_dir in sorted(set(r2d.values())):
        sp_path = workspace / organ_dir / ".gitmodules"
        entries = _parse_gitmodules(sp_path)
        sp_organ = d2r.get(organ_dir, organ_dir)
        for entry in entries:
            repo_name = entry.get("github_repo") or entry.get("name", "")
            if repo_name:
                submod_by_repo.setdefault(repo_name, []).append(
                    (sp_organ, entry),
                )

    for repo_name, locations in submod_by_repo.items():
        # Skip org-level infrastructure repos (.github) — each org has its own
        if repo_name.startswith("."):
            continue

        reg_info = registry_map.get(repo_name)

        for sp_organ, entry in locations:
            github_org = entry.get("github_org", "")

            if reg_info is None:
                findings.append(BuriedEntity(
                    repo=repo_name,
                    organ=sp_organ,
                    entity_path=entry.get("path", repo_name),
                    entity_type="submodule_orphan",
                    evidence=[e for e in [
                        f"Submodule of {sp_organ} superproject",
                        f"GitHub org: {github_org}" if github_org else "",
                        "Not in registry-v2.json",
                    ] if e],
                    severity="warning",
                    recommendation=(
                        f"'{repo_name}' is a git submodule in {sp_organ} "
                        "but has no registry entry."
                    ),
                ))
                continue

            reg_organ, reg_org = reg_info

            # Superproject organ doesn't match registry organ
            if sp_organ != reg_organ:
                findings.append(BuriedEntity(
                    repo=repo_name,
                    organ=reg_organ,
                    entity_path=entry.get("path", repo_name),
                    entity_type="submodule_mismatch",
                    evidence=[e for e in [
                        f"Registered in {reg_organ} (registry)",
                        f"Submodule of {sp_organ} (git infrastructure)",
                        f"URL org: {github_org}" if github_org else "",
                    ] if e],
                    severity="critical",
                    pattern="superproject_mismatch",
                    recommendation=(
                        f"'{repo_name}' registered in {reg_organ} but "
                        f"tracked as submodule of {sp_organ}."
                    ),
                ))

            # GitHub URL org doesn't match registry org
            if github_org and reg_org and github_org != reg_org:
                findings.append(BuriedEntity(
                    repo=repo_name,
                    organ=reg_organ,
                    entity_path=entry.get("path", repo_name),
                    entity_type="submodule_mismatch",
                    evidence=[
                        f"Registry org: {reg_org}",
                        f"URL org: {github_org}",
                    ],
                    severity="warning",
                    pattern="org_mismatch",
                    recommendation=(
                        f"'{repo_name}' registry org '{reg_org}' differs "
                        f"from GitHub URL org '{github_org}'."
                    ),
                ))

        # Dual-homed: in multiple distinct superprojects
        sp_organs = {sp for sp, _ in locations}
        if len(sp_organs) > 1:
            findings.append(BuriedEntity(
                repo=repo_name,
                organ=reg_info[0] if reg_info else locations[0][0],
                entity_path="(repo-level)",
                entity_type="submodule_mismatch",
                evidence=[
                    f"In {len(sp_organs)} superprojects: "
                    + ", ".join(sorted(sp_organs)),
                ],
                severity="warning",
                pattern="dual_homed",
                recommendation=(
                    f"'{repo_name}' in multiple superprojects. "
                    "Consolidate to its registry organ's superproject."
                ),
            ))

    return findings


# ── Lineage / derivation patterns ────────────────────────────────

_DERIVATION_PREFIXES = [
    ("art-from--", "artistic_derivative"),
]


def scan_lineage(
    registry: dict,
) -> list[BuriedEntity]:
    """Detect spawn and derivative relationships between repos.

    Traces name-based derivation patterns (e.g., art-from--X derives from X)
    and flags repos whose lineage should be tracked for realignment.
    """
    from organvm_engine.registry.query import all_repos

    findings: list[BuriedEntity] = []
    name_map: dict[str, tuple[str, dict]] = {}
    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        name = repo.get("name", "")
        if name:
            name_map[name] = (organ_key, repo)

    for name, (organ_key, _repo) in name_map.items():
        for prefix, lineage_type in _DERIVATION_PREFIXES:
            if not name.startswith(prefix):
                continue

            source_stem = name[len(prefix):]
            source_match = name_map.get(source_stem)

            if source_match:
                src_organ = source_match[0]
                cross_organ = src_organ != organ_key
                findings.append(BuriedEntity(
                    repo=name,
                    organ=organ_key,
                    entity_path="(repo-level)",
                    entity_type="lineage",
                    evidence=[
                        f"'{prefix}' → derives from '{source_stem}'",
                        f"Source: {source_stem} ({src_organ})",
                        f"Derivative: {name} ({organ_key})",
                        "Cross-organ" if cross_organ else "Same-organ",
                    ],
                    pattern=lineage_type,
                    severity="warning" if cross_organ else "info",
                    recommendation=(
                        f"'{name}' derives from '{source_stem}'"
                        + (
                            f" ({src_organ}→{organ_key})"
                            if cross_organ
                            else f" (within {organ_key})"
                        )
                        + ". Track lineage for propagation."
                    ),
                ))
            else:
                findings.append(BuriedEntity(
                    repo=name,
                    organ=organ_key,
                    entity_path="(repo-level)",
                    entity_type="lineage",
                    evidence=[
                        f"'{prefix}' suggests derivation from '{source_stem}'",
                        f"No source '{source_stem}' in registry",
                    ],
                    pattern="orphan_derivative",
                    severity="warning",
                    recommendation=(
                        f"'{name}' appears to derive from '{source_stem}' "
                        "but no source repo found."
                    ),
                ))

    return findings


def run_full_excavation(
    workspace: Path,
    registry: dict,
    thresholds: dict | None = None,
) -> ExcavationReport:
    """Run all four scanners and merge results."""
    file_threshold = (thresholds or {}).get("file_threshold", 10)
    line_threshold = (thresholds or {}).get("line_threshold", 2000)

    from organvm_engine.registry.query import all_repos

    # Count non-archived repos
    repo_count = sum(
        1 for _, r in all_repos(registry)
        if r.get("implementation_status") != "ARCHIVED"
    )

    # Run scanners
    sub_pkg = scan_sub_packages(workspace, registry)
    family_findings, families = scan_cross_organ_families(registry)
    extractable = scan_extractable_modules(
        workspace, registry, file_threshold, line_threshold,
    )
    gov_misplaced = scan_misplaced_governance(workspace, registry)
    topology = scan_submodule_topology(workspace, registry)
    lineage = scan_lineage(registry)

    all_findings = (
        sub_pkg + family_findings + extractable
        + gov_misplaced + topology + lineage
    )

    # Sort by severity (critical first), then repo name
    sev_order = {"critical": 0, "warning": 1, "info": 2}
    all_findings.sort(key=lambda f: (sev_order.get(f.severity, 9), f.repo))

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for f in all_findings:
        by_type[f.entity_type] = by_type.get(f.entity_type, 0) + 1
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    return ExcavationReport(
        scanned_repos=repo_count,
        total_findings=len(all_findings),
        findings=all_findings,
        by_type=by_type,
        by_severity=by_severity,
        cross_organ_families=families,
    )
