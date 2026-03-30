"""probatio — executable proofs for the palingenesis architecture.

Every structural claim is a test. If the test doesn't pass, the claim is false.
No assertion without measurement. The universe speaks in numbers.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DepthReport:
    """Depth analysis for a single formation."""
    name: str
    language: str
    mandatory_depth: int
    actual_depth: int
    deepest_path: str
    compressible: int  # actual - mandatory
    deepest_dir_siblings: int
    verdict: str  # AT_FLOOR | COMPRESSIBLE | BLOATED


@dataclass
class DepthVerdict:
    """Aggregate verdict across all formations."""
    formations_at_floor: int
    formations_compressible: int
    formations_bloated: int
    max_mandatory: int
    max_actual: int
    total_compressible_levels: int


# ---------------------------------------------------------------------------
# Physics: what each language/framework REQUIRES
# ---------------------------------------------------------------------------

LANGUAGE_PHYSICS = {
    "python_src": {
        "depth": 4,
        "pattern": "repo/src/package/module/file.py",
        "reason": "pip install -e . requires src layout with __init__.py namespace",
    },
    "python_flat": {
        "depth": 2,
        "pattern": "repo/module/file.py",
        "reason": "flat Python package, no src layout",
    },
    "nextjs_app": {
        "depth": 5,
        "pattern": "repo/app/api/resource/[id]/route.ts",
        "reason": "Next.js filesystem routing — directory path IS the URL",
    },
    "nextjs_src": {
        "depth": 3,
        "pattern": "repo/src/component/file.tsx",
        "reason": "Next.js src layout for non-routing files",
    },
    "typescript_flat": {
        "depth": 2,
        "pattern": "repo/src/file.ts",
        "reason": "flat TypeScript/JavaScript project",
    },
    "jvm": {
        "depth": 8,
        "pattern": "repo/src/main/java/com/org/app/File.kt",
        "reason": "JVM requires directory path = package namespace",
    },
    "docs": {
        "depth": 2,
        "pattern": "repo/section/file.md",
        "reason": "documentation corpus, no build system constraints",
    },
}

# Directories that inflate line counts but contain no hand-written code
VENDORED_PATTERNS = [
    "node_modules", ".next", "dist", "build", ".venv", "venv",
    "site-packages", "__pycache__", ".egg-info", ".smart-env",
    "bench", ".specstory", "vendor", "coverage", "_local",
    ".ruff_cache", ".pytest_cache", ".browser-profile",
]

# Directories created by tools, not humans
TOOL_GENERATED_DIRS = [
    ".claude", ".codex", ".gemini", ".conductor", ".github",
]

SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".kt"}


# ---------------------------------------------------------------------------
# Detection: what language/framework does this formation use?
# ---------------------------------------------------------------------------

def detect_language(repo_path: Path) -> str:
    """Detect the language/framework physics of a formation."""
    has_pyproject = (repo_path / "pyproject.toml").exists()
    has_setup = (repo_path / "setup.py").exists()
    has_package_json = (repo_path / "package.json").exists()
    has_cargo = (repo_path / "Cargo.toml").exists()
    has_src = (repo_path / "src").is_dir()
    has_app = (repo_path / "app").is_dir()

    if has_pyproject or has_setup:
        if has_src:
            return "python_src"
        return "python_flat"
    if has_package_json:
        if has_app:
            return "nextjs_app"
        if has_src:
            return "nextjs_src"
        return "typescript_flat"
    if has_cargo:
        return "rust"
    return "docs"


def _is_vendored(path: Path) -> bool:
    """Check if a path is inside a vendored/generated directory."""
    parts = path.parts
    return any(vendor in parts for vendor in VENDORED_PATTERNS)


def _is_source_file(path: Path) -> bool:
    """Check if a file is hand-written source code."""
    return path.suffix in SOURCE_EXTENSIONS and not _is_vendored(path)


# ---------------------------------------------------------------------------
# Measurement: depth analysis per formation
# ---------------------------------------------------------------------------

def measure_depth(repo_path: Path) -> DepthReport:
    """Measure the depth profile of a formation.

    Returns a DepthReport with mandatory depth (physics), actual depth,
    and whether the excess is compressible.
    """
    name = repo_path.name
    language = detect_language(repo_path)
    physics = LANGUAGE_PHYSICS.get(language, LANGUAGE_PHYSICS["docs"])
    mandatory = physics["depth"]

    # Find deepest source file (excluding vendored)
    deepest_depth = 0
    deepest_path = ""
    deepest_dir_siblings = 0

    for root, _dirs, files in os.walk(repo_path):
        root_path = Path(root)

        # Skip vendored and tool-generated
        if _is_vendored(root_path):
            continue
        if any(t in root_path.parts for t in TOOL_GENERATED_DIRS):
            continue
        if ".git" in root_path.parts:
            continue

        for f in files:
            file_path = root_path / f
            if not _is_source_file(file_path):
                continue

            rel = file_path.relative_to(repo_path)
            depth = len(rel.parts)

            if depth > deepest_depth:
                deepest_depth = depth
                deepest_path = str(rel)
                # Count siblings in the deepest directory
                deepest_dir_siblings = sum(
                    1 for ff in root_path.iterdir()
                    if ff.is_file() and _is_source_file(ff)
                )

    compressible = max(0, deepest_depth - mandatory)

    if compressible == 0:
        verdict = "AT_FLOOR"
    elif compressible <= 2:
        verdict = "COMPRESSIBLE"
    else:
        verdict = "BLOATED"

    return DepthReport(
        name=name,
        language=language,
        mandatory_depth=mandatory,
        actual_depth=deepest_depth,
        deepest_path=deepest_path,
        compressible=compressible,
        deepest_dir_siblings=deepest_dir_siblings,
        verdict=verdict,
    )


def stress_test_depth(repo_path: Path) -> dict:
    """Stress test: for each file deeper than mandatory, prove it MUST be there.

    Returns a dict of {relative_path: reason_it_could_relocate} for every
    file that lives deeper than physics demands. Empty dict = formation
    is already at its compression floor.
    """
    report = measure_depth(repo_path)
    language = report.language
    physics = LANGUAGE_PHYSICS.get(language, LANGUAGE_PHYSICS["docs"])
    mandatory = physics["depth"]

    relocatable = {}

    for root, _dirs, files in os.walk(repo_path):
        root_path = Path(root)

        if _is_vendored(root_path):
            continue
        if any(t in root_path.parts for t in TOOL_GENERATED_DIRS):
            continue
        if ".git" in root_path.parts:
            continue

        for f in files:
            file_path = root_path / f
            if not _is_source_file(file_path):
                continue

            rel = file_path.relative_to(repo_path)
            depth = len(rel.parts)

            if depth <= mandatory:
                continue

            # This file is deeper than physics demands. WHY?
            parent = rel.parent
            sibling_count = sum(
                1 for ff in (repo_path / parent).iterdir()
                if ff.is_file() and _is_source_file(ff)
            )

            # Heuristics for whether depth is justified
            reasons = []

            # Framework conventions that force depth
            parts = rel.parts
            if "migrations" in parts or "meta" in parts:
                reasons.append("ORM/migration tool generates this structure")
            if "android" in parts or "java" in parts:
                reasons.append("JVM package namespace requires directory = path")
            if any(p.startswith("[") and p.endswith("]") for p in parts):
                reasons.append("Next.js dynamic route segment — path IS the API")
            if "templates" in parts:
                reasons.append("template directory — framework convention")
            if "__tests__" in parts or "tests" in parts:
                reasons.append("test co-location — framework convention")

            if reasons:
                # Depth is justified by framework physics
                continue

            # Not justified by framework. Check if grouping makes sense.
            if sibling_count >= 4:
                # 4+ siblings = the subdirectory groups a cohesive module
                # Could STILL be flattened, but the grouping is doing work
                relocatable[str(rel)] = (
                    f"MAYBE — {sibling_count} siblings justify grouping, "
                    f"but could flatten with {language} naming prefix"
                )
            elif sibling_count <= 2:
                # 1-2 files in a subdirectory = the directory exists for no reason
                relocatable[str(rel)] = (
                    f"YES — only {sibling_count} file(s) in {parent}/, "
                    f"can move up to {parent.parent}/"
                )
            else:
                relocatable[str(rel)] = (
                    f"MAYBE — {sibling_count} siblings, borderline"
                )

    return relocatable


# ---------------------------------------------------------------------------
# Aggregate: prove the instance depth model
# ---------------------------------------------------------------------------

def prove_instance_depth(instance_path: Path) -> DepthVerdict:
    """Prove: instance → formation = always 2 levels.
    Formation internals governed by their own physics.
    """
    at_floor = 0
    compressible = 0
    bloated = 0
    max_mandatory = 0
    max_actual = 0
    total_compressible = 0

    for entry in instance_path.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        if entry.name in ("lifecycle--preserve", "lifecycle--transform",
                          "aspectus", "reliquiae"):
            continue

        # This is a formation — measure it
        if not (entry / ".git").exists() and not (entry / "pyproject.toml").exists() \
                and not (entry / "package.json").exists():
            continue

        report = measure_depth(entry)
        if report.actual_depth == 0:
            continue

        if report.verdict == "AT_FLOOR":
            at_floor += 1
        elif report.verdict == "COMPRESSIBLE":
            compressible += 1
        else:
            bloated += 1

        max_mandatory = max(max_mandatory, report.mandatory_depth)
        max_actual = max(max_actual, report.actual_depth)
        total_compressible += report.compressible

    return DepthVerdict(
        formations_at_floor=at_floor,
        formations_compressible=compressible,
        formations_bloated=bloated,
        max_mandatory=max_mandatory,
        max_actual=max_actual,
        total_compressible_levels=total_compressible,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def run_depth_stress_test(workspace: Path, *, verbose: bool = False) -> None:
    """Run depth stress test across all formations in a workspace."""
    formations = sorted(
        p for p in workspace.iterdir()
        if p.is_dir()
        and not p.name.startswith(".")
        and (p / ".git").exists()
    )

    print(f"Scanning {len(formations)} formations...\n")
    print(f"{'FORMATION':<45} {'LANG':<14} {'MAND':>4} {'ACT':>4} {'COMP':>4}  VERDICT")
    print("─" * 95)

    for f in formations:
        report = measure_depth(f)
        if report.actual_depth == 0:
            continue
        print(
            f"{report.name:<45} {report.language:<14} "
            f"{report.mandatory_depth:>4} {report.actual_depth:>4} "
            f"{report.compressible:>4}  {report.verdict}"
        )

        if verbose and report.compressible > 0:
            relocatable = stress_test_depth(f)
            for path, reason in sorted(relocatable.items()):
                print(f"  └─ {path}")
                print(f"     {reason}")

    print()


if __name__ == "__main__":
    import sys
    workspace = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    run_depth_stress_test(workspace, verbose="--verbose" in sys.argv)
