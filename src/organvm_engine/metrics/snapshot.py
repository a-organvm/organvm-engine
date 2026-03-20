"""System snapshot export — structured narrative JSON for external consumers."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_system_snapshot(
    registry: dict,
    computed_metrics: dict,
    workspace: Path | None = None,
    metrics_full: dict | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    all_repos: list[dict] = []
    organs_list: list[dict] = []

    for organ_key, organ_data in registry.get("organs", {}).items():
        repos = organ_data.get("repositories", [])
        all_repos.extend(repos)
        flagship = sum(1 for r in repos if r.get("tier") == "flagship")
        standard = sum(1 for r in repos if r.get("tier") == "standard")
        infra = sum(1 for r in repos if r.get("tier") == "infrastructure")
        organs_list.append({
            "key": organ_key,
            "name": organ_data.get("name", organ_key),
            "repo_count": len(repos),
            "flagship_count": flagship,
            "standard_count": standard,
            "infrastructure_count": infra,
            "repositories": [
                {"name": r.get("name", ""), "status": r.get("promotion_status", ""),
                 "tier": r.get("tier", ""), "ci": bool(r.get("ci_workflow"))}
                for r in repos
            ],
        })

    pipeline = Counter(r.get("promotion_status", "UNKNOWN") for r in all_repos)

    # AMMOI (best-effort)
    ammoi_text = ""
    density = 0.0
    entities = 0
    edges = 0
    try:
        from organvm_engine.pulse.ammoi import compute_ammoi
        ammoi = compute_ammoi(registry=registry, workspace=workspace)
        ammoi_text = ammoi.compressed_text
        density = ammoi.system_density
        entities = ammoi.total_entities
        edges = ammoi.active_edges
    except Exception:
        pass

    # Variables
    variables: dict[str, str] = {}
    try:
        from organvm_engine.metrics.vars import build_vars
        full = metrics_full if metrics_full else {"computed": computed_metrics, "manual": {}}
        variables = build_vars(full, registry)
    except Exception:
        pass

    # Omega
    omega: dict[str, Any] = {"met": 0, "total": 17}
    try:
        from organvm_engine.omega.scorecard import evaluate_omega
        result = evaluate_omega(registry, workspace=workspace)
        omega = {"met": result.met_count, "total": result.total}
    except Exception:
        pass

    # Code profile (best-effort, requires workspace)
    code_profile: dict[str, Any] = {}
    if workspace and workspace.is_dir():
        import contextlib

        with contextlib.suppress(Exception):
            code_profile = _scan_code_profile(workspace)

    # Word counts from computed metrics
    word_counts = computed_metrics.get("word_counts", {})

    return {
        "generated_at": now,
        "system": {
            "total_repos": computed_metrics.get("total_repos", len(all_repos)),
            "active_repos": computed_metrics.get("active_repos", 0),
            "density": round(density, 4),
            "entities": entities,
            "edges": edges,
            "ci_workflows": computed_metrics.get("ci_workflows", 0),
            "code_files": computed_metrics.get("code_files", 0),
            "test_files": computed_metrics.get("test_files", 0),
            "repos_with_tests": computed_metrics.get("repos_with_tests", 0),
            "total_words": computed_metrics.get("total_words_short", ""),
            "total_words_numeric": computed_metrics.get("total_words_numeric", 0),
            "published_essays": computed_metrics.get("published_essays")
                or (metrics_full or {}).get("computed", {}).get("published_essays", 0),
            "sprints_completed": computed_metrics.get("sprints_completed")
                or (metrics_full or {}).get("computed", {}).get("sprints_completed", 0),
            "ammoi": ammoi_text,
        },
        "code_profile": code_profile,
        "word_counts": word_counts,
        "organs": sorted(organs_list, key=lambda o: o["key"]),
        "variables": variables,
        "omega": omega,
        "promotion_pipeline": dict(sorted(pipeline.items())),
    }


_LANG_MAP: dict[str, str] = {
    # Primary languages
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript/React",
    ".js": "JavaScript", ".jsx": "JavaScript/React", ".go": "Go",
    ".rs": "Rust", ".sh": "Shell", ".bash": "Shell",
    # Other compiled/scripting
    ".rb": "Ruby", ".java": "Java", ".kt": "Kotlin",
    ".swift": "Swift", ".c": "C", ".cpp": "C++",
    ".cs": "C#", ".php": "PHP", ".lua": "Lua",
    ".sol": "Solidity",
    # Data/query
    ".sql": "SQL", ".graphql": "GraphQL", ".gql": "GraphQL",
    ".prisma": "Prisma", ".proto": "Protocol Buffers",
    # Web/UI
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".svelte": "Svelte", ".vue": "Vue", ".astro": "Astro", ".mdx": "MDX",
    # Config/data
    ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML",
    ".json": "JSON", ".jsonc": "JSON",
    # Documentation
    ".md": "Markdown",
}

# Subset that counts as "code" (not config/data/docs)
_CODE_EXTS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".sh", ".bash",
    ".rb", ".java", ".kt", ".swift", ".c", ".cpp", ".cs", ".php", ".lua",
    ".sol", ".sql", ".graphql", ".gql", ".prisma", ".proto",
    ".html", ".css", ".scss", ".svelte", ".vue", ".astro", ".mdx",
})

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist",
    "build", ".next", ".astro", "intake", ".claude", "materia-collider",
    ".eggs", "egg-info", "site-packages", "new_venv", "env",
})

_SKIP_IN_PATH = ("site-packages", "new_venv", "/venv/", "/.venv/", "/env/", "/dist/", "/build/")

_TEST_PATTERNS = ("test_", "_test.", ".test.", ".spec.", "/tests/", "/__tests__/")


def _scan_code_profile(workspace: Path) -> dict[str, Any]:
    """Scan workspace for code/test files by language and framework.

    Returns a structured breakdown: languages, test_frameworks, and
    verified_test_counts for packages with known passing test suites.
    """
    all_lang_counts: dict[str, int] = {}  # every file type
    lang_counts: dict[str, int] = {}      # code files only
    test_lang_counts: dict[str, int] = {}
    frameworks: dict[str, int] = {}

    import re

    py_test_fns = 0
    ts_test_fns = 0

    for org_dir in workspace.iterdir():
        if not org_dir.is_dir() or org_dir.name.startswith(".") or org_dir.name in _SKIP_DIRS:
            continue
        for f in org_dir.rglob("*"):
            path_str = str(f)
            if any(s in path_str for s in _SKIP_IN_PATH):
                continue
            if any(s in f.parts for s in _SKIP_DIRS):
                continue
            if not f.is_file():
                continue

            name = f.name.lower()
            ext = f.suffix.lower()

            # Framework detection
            if name == "conftest.py":
                frameworks["pytest"] = frameworks.get("pytest", 0) + 1
            elif name.startswith("vitest.config"):
                frameworks["vitest"] = frameworks.get("vitest", 0) + 1
            elif name.startswith("jest.config"):
                frameworks["jest"] = frameworks.get("jest", 0) + 1

            # Language counting (all recognized files)
            if ext not in _LANG_MAP:
                continue
            lang = _LANG_MAP[ext]
            all_lang_counts[lang] = all_lang_counts.get(lang, 0) + 1

            # Code files only (not config/data/docs)
            if ext in _CODE_EXTS:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

            # Test file + function counting
            if name.startswith("test_") and ext == ".py":
                test_lang_counts["Python"] = test_lang_counts.get("Python", 0) + 1
                try:
                    content = f.read_text(errors="ignore")
                    py_test_fns += len(re.findall(r"^\s*def test_", content, re.MULTILINE))
                except Exception:
                    pass
            elif name.endswith((".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx")):
                tl = _LANG_MAP.get(ext, "TypeScript")
                test_lang_counts[tl] = test_lang_counts.get(tl, 0) + 1
                try:
                    content = f.read_text(errors="ignore")
                    ts_test_fns += len(re.findall(r"(?:^|\s)(?:it|test)\s*\(", content, re.MULTILINE))
                except Exception:
                    pass

    total_test_fns = py_test_fns + ts_test_fns

    return {
        "all_files": dict(sorted(all_lang_counts.items(), key=lambda x: -x[1])),
        "code_files_by_language": dict(sorted(lang_counts.items(), key=lambda x: -x[1])),
        "test_languages": dict(sorted(test_lang_counts.items(), key=lambda x: -x[1])),
        "test_frameworks": dict(sorted(frameworks.items(), key=lambda x: -x[1])),
        "total_files": sum(all_lang_counts.values()),
        "total_code_files": sum(lang_counts.values()),
        "total_test_files": sum(test_lang_counts.values()),
        "primary_language": max(lang_counts, key=lang_counts.get) if lang_counts else "",
        "test_functions": {
            "python": py_test_fns,
            "typescript": ts_test_fns,
            "total": total_test_fns,
        },
    }


def write_system_snapshot(snapshot: dict, output: Path) -> None:
    import json
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=False)
        f.write("\n")
