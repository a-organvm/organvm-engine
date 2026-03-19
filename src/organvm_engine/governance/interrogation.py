"""Structural interrogation engine — 7-dimension diagnostic framework.

Implements: SPEC-009, DIAG-001 through DIAG-007

Seven diagnostic dimensions derived from the constitutional corpus:
  DIAG-001  Existence  — does the entity exist as a discrete, addressable unit?
  DIAG-002  Identity   — does it have a stable, unique identity?
  DIAG-003  Structure  — is it internally organized with named parts?
  DIAG-004  Law        — is it governed by explicit rules?
  DIAG-005  Process    — does it participate in defined workflows?
  DIAG-006  Relation   — are its connections to other entities explicit?
  DIAG-007  Teleology  — does it have a declared purpose?

fast_tension_scan() compresses all seven dimensions into a single
registry-wide sweep returning a score per dimension.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from organvm_engine.registry.query import all_repos

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

DiagResult = tuple[float, list[str]]


@dataclass
class InterrogationReport:
    """Consolidated interrogation result across all 7 dimensions."""

    dimensions: dict[str, DiagResult] = field(default_factory=dict)

    @property
    def overall_score(self) -> float:
        if not self.dimensions:
            return 0.0
        return sum(s for s, _ in self.dimensions.values()) / len(self.dimensions)

    @property
    def all_findings(self) -> list[str]:
        out: list[str] = []
        for dim, (_, findings) in self.dimensions.items():
            for f in findings:
                out.append(f"[{dim}] {f}")
        return out

    def summary(self) -> str:
        lines = ["Structural Interrogation", "=" * 40]
        for dim, (score, findings) in self.dimensions.items():
            lines.append(f"  {dim}: {score:.2%}")
            for f in findings:
                lines.append(f"    - {f}")
        lines.append(f"\nOverall: {self.overall_score:.2%}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# DIAG-001: Existence
# ---------------------------------------------------------------------------

def check_existence(repo: dict[str, Any]) -> DiagResult:
    """Does the entity exist as a discrete, addressable unit?

    Checks: name present, org present, not empty strings.
    """
    findings: list[str] = []
    checks_passed = 0
    total_checks = 3

    name = repo.get("name", "")
    org = repo.get("org", "")
    impl = repo.get("implementation_status", "")

    if name:
        checks_passed += 1
    else:
        findings.append("Missing name")

    if org:
        checks_passed += 1
    else:
        findings.append("Missing org")

    if impl:
        checks_passed += 1
    else:
        findings.append("Missing implementation_status")

    return checks_passed / total_checks, findings


# ---------------------------------------------------------------------------
# DIAG-002: Identity
# ---------------------------------------------------------------------------

def check_identity(repo: dict[str, Any]) -> DiagResult:
    """Does the entity have a stable, unique identity?

    Checks: name is non-empty, promotion_status exists, has description.
    """
    findings: list[str] = []
    checks_passed = 0
    total_checks = 3

    if repo.get("name"):
        checks_passed += 1
    else:
        findings.append("No name (identity anchor)")

    if repo.get("promotion_status"):
        checks_passed += 1
    else:
        findings.append("No promotion_status (lifecycle identity)")

    if repo.get("description"):
        checks_passed += 1
    else:
        findings.append("No description (semantic identity)")

    return checks_passed / total_checks, findings


# ---------------------------------------------------------------------------
# DIAG-003: Structure
# ---------------------------------------------------------------------------

def check_structure(repo: dict[str, Any]) -> DiagResult:
    """Is the entity internally organized with named parts?

    Checks: has code_files > 0, has tier, has dependencies list.
    """
    findings: list[str] = []
    checks_passed = 0
    total_checks = 3

    code_files = repo.get("code_files", 0) or 0
    if code_files > 0:
        checks_passed += 1
    else:
        findings.append("No code_files (no internal structure evidence)")

    if repo.get("tier"):
        checks_passed += 1
    else:
        findings.append("No tier classification")

    if isinstance(repo.get("dependencies"), list):
        checks_passed += 1
    else:
        findings.append("No dependencies list (structural isolation)")

    return checks_passed / total_checks, findings


# ---------------------------------------------------------------------------
# DIAG-004: Law
# ---------------------------------------------------------------------------

def check_law(repo: dict[str, Any]) -> DiagResult:
    """Is the entity governed by explicit rules?

    Checks: promotion_status is set, ci_workflow exists, platinum_status set.
    """
    findings: list[str] = []
    checks_passed = 0
    total_checks = 3

    if repo.get("promotion_status"):
        checks_passed += 1
    else:
        findings.append("No promotion_status (ungoverned lifecycle)")

    if repo.get("ci_workflow"):
        checks_passed += 1
    else:
        findings.append("No ci_workflow (no automated enforcement)")

    if repo.get("platinum_status") is not None:
        checks_passed += 1
    else:
        findings.append("No platinum_status (no quality bar)")

    return checks_passed / total_checks, findings


# ---------------------------------------------------------------------------
# DIAG-005: Process
# ---------------------------------------------------------------------------

def check_process(repo: dict[str, Any]) -> DiagResult:
    """Does the entity participate in defined workflows?

    Checks: last_validated exists, implementation_status is not DESIGN_ONLY,
    has test_files.
    """
    findings: list[str] = []
    checks_passed = 0
    total_checks = 3

    if repo.get("last_validated"):
        checks_passed += 1
    else:
        findings.append("Never validated (no process engagement)")

    impl = repo.get("implementation_status", "")
    if impl and impl != "DESIGN_ONLY":
        checks_passed += 1
    else:
        findings.append("DESIGN_ONLY or missing (no active process)")

    test_files = repo.get("test_files", 0) or 0
    if test_files > 0:
        checks_passed += 1
    else:
        findings.append("No test_files (no verification process)")

    return checks_passed / total_checks, findings


# ---------------------------------------------------------------------------
# DIAG-006: Relation
# ---------------------------------------------------------------------------

def check_relation(repo: dict[str, Any]) -> DiagResult:
    """Are connections to other entities explicit?

    Checks: dependencies is a list, org maps to a known prefix,
    has at least one explicit dependency or is declared independent.
    """
    findings: list[str] = []
    checks_passed = 0
    total_checks = 3

    deps = repo.get("dependencies")
    if isinstance(deps, list):
        checks_passed += 1
    else:
        findings.append("No dependencies field (relational void)")

    if repo.get("org"):
        checks_passed += 1
    else:
        findings.append("No org (no organ membership relation)")

    # Having explicit deps or a tier that implies independence is fine
    if isinstance(deps, list) and len(deps) > 0:
        checks_passed += 1
    elif repo.get("tier") in ("flagship", "infrastructure"):
        checks_passed += 1  # expected to have few deps
    else:
        findings.append("No declared dependencies and not flagship/infrastructure")

    return checks_passed / total_checks, findings


# ---------------------------------------------------------------------------
# DIAG-007: Teleology
# ---------------------------------------------------------------------------

def check_teleology(repo: dict[str, Any]) -> DiagResult:
    """Does the entity have a declared purpose?

    Checks: description exists and is substantial, tier is assigned,
    note field provides rationale.
    """
    findings: list[str] = []
    checks_passed = 0
    total_checks = 3

    desc = repo.get("description", "")
    if desc and len(desc) > 10:
        checks_passed += 1
    else:
        findings.append("No substantial description (no stated purpose)")

    if repo.get("tier"):
        checks_passed += 1
    else:
        findings.append("No tier (no role in system)")

    note = repo.get("note", "")
    if note and len(note) > 5:
        checks_passed += 1
    else:
        findings.append("No note (no rationale)")

    return checks_passed / total_checks, findings


# ---------------------------------------------------------------------------
# Full interrogation
# ---------------------------------------------------------------------------

_DIMENSION_CHECKS = {
    "existence": check_existence,
    "identity": check_identity,
    "structure": check_structure,
    "law": check_law,
    "process": check_process,
    "relation": check_relation,
    "teleology": check_teleology,
}


def interrogate_repo(repo: dict[str, Any]) -> InterrogationReport:
    """Run all 7 diagnostic dimensions on a single repo.

    Args:
        repo: A repository dict from the registry.

    Returns:
        InterrogationReport with per-dimension scores and findings.
    """
    report = InterrogationReport()
    for dim_name, check_fn in _DIMENSION_CHECKS.items():
        report.dimensions[dim_name] = check_fn(repo)
    return report


# ---------------------------------------------------------------------------
# Fast tension scan (compressed registry-wide)
# ---------------------------------------------------------------------------

def fast_tension_scan(registry: dict) -> dict[str, float]:
    """Compressed 7-dimension scan across the entire registry.

    Averages each dimension's score across all active repos.
    This is the "10-question compressed scan" — one aggregate score
    per dimension for the whole system.

    Args:
        registry: Loaded registry dict.

    Returns:
        Dict of dimension_name -> average score (0.0 to 1.0).
    """
    dim_totals: dict[str, float] = {d: 0.0 for d in _DIMENSION_CHECKS}
    count = 0

    for _organ_key, repo in all_repos(registry):
        impl = repo.get("implementation_status", "")
        if impl == "ARCHIVED":
            continue

        count += 1
        for dim_name, check_fn in _DIMENSION_CHECKS.items():
            score, _ = check_fn(repo)
            dim_totals[dim_name] += score

    if count == 0:
        return {d: 1.0 for d in _DIMENSION_CHECKS}

    return {d: round(t / count, 4) for d, t in dim_totals.items()}
