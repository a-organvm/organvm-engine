"""Propagate metrics from system-metrics.json into documentation files.

Supports both corpus-only propagation (hardcoded whitelist) and cross-repo
propagation via metrics-targets.yaml manifest.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml


@dataclass
class PropagationResult:
    """Result of a metrics propagation run."""

    replacements: int = 0
    files_changed: int = 0
    json_copies: int = 0
    details: list[str] = field(default_factory=list)


def build_patterns(metrics: dict) -> list[tuple[str, re.Pattern, str]]:
    """Build regex patterns for metric replacement.

    Returns list of (metric_name, compiled_pattern, replacement_string).
    """
    c = metrics.get("computed", {})
    m = metrics.get("manual", {})

    total_repos = c.get("total_repos", 0)
    active_repos = c.get("active_repos", 0)
    archived_repos = c.get("archived_repos", 0)
    essays = c.get("published_essays", 0)
    ci_workflows = c.get("ci_workflows", 0)
    dep_edges = c.get("dependency_edges", 0)
    sprints = c.get("sprints_completed", 0)

    # Try computed first (auto-counted), fall back to manual (legacy)
    total_words_numeric = str(c.get("total_words_numeric") or m.get("total_words_numeric", 404000))
    total_words_formatted = f"{int(total_words_numeric):,}"
    total_words_short = c.get("total_words_short") or m.get("total_words_short", "404K+")
    total_words_k = total_words_short.rstrip("K+")

    patterns = []

    def add(name: str, regex: str, replacement: str) -> None:
        patterns.append((name, re.compile(regex), replacement))

    # Total repos patterns
    add("total_repos", r"(\b)\d+( repositor(?:ies|y) across\b)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(coordinating )\d+( repo)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(Total repositories \| )\d+", rf"\g<1>{total_repos}")
    add("total_repos", r"(Repos-)\d+", rf"\g<1>{total_repos}")
    add("total_repos", r"(\b)\d+(-repo system\b)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(\b)\d+(-repo\b)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(across )\d+( repo)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(organize )\d+( repositor)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(validate )\d+( repositor)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(across all )\d+( repos?\b)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(\b)\d+( documented repositor)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(\b)\d+( repository READMEs)", rf"\g<1>{total_repos}\2")

    # Active repos
    add("active_repos", r"(\b)\d+( ACTIVE\b)", rf"\g<1>{active_repos}\2")
    add("active_repos", r"(Active status \| )\d+", rf"\g<1>{active_repos}")
    add("active_repos", r"(\b)\d+( active repos?,)", rf"\g<1>{active_repos}\2")
    add("active_repos", r"(\b)\d+( production-grade\b)", rf"\g<1>{active_repos}\2")
    add("active_repos", r"(Production status \| )\d+", rf"\g<1>{active_repos}")

    # Archived repos
    add("archived_repos", r"(\b)\d+( ARCHIVED\b)", rf"\g<1>{archived_repos}\2")
    add("archived_repos", r"(Archived \| )\d+", rf"\g<1>{archived_repos}")

    # Essays
    add("published_essays", r"(\b)\d+(\+? published essays?\b)", rf"\g<1>{essays}\2")
    add("published_essays", r"(\b)\d+(\+? meta-system essays?\b)", rf"\g<1>{essays}\2")
    add("published_essays", r"(Published essays? \| )\d+", rf"\g<1>{essays}")
    add("published_essays", r"(\b)\d+( essays explaining\b)", rf"\g<1>{essays}\2")
    add("published_essays", r"(\b)\d+( essays documenting\b)", rf"\g<1>{essays}\2")

    # CI workflows
    add("ci_workflows", r"(\b)\d+(\+ CI/CD workflows?\b)", rf"\g<1>{ci_workflows}\2")
    add("ci_workflows", r"(CI/CD workflows? \| )\d+\+?", rf"\g<1>{ci_workflows}+")
    add("ci_workflows", r"(\b)\d+(\+ CI workflows?\b)", rf"\g<1>{ci_workflows}\2")
    add("ci_workflows", r"(\b)\d+(\+ CI/CD pipelines?\b)", rf"\g<1>{ci_workflows}\2")

    # Dependencies
    add("dependency_edges", r"(\b)\d+( dependency edges?\b)", rf"\g<1>{dep_edges}\2")
    add("dependency_edges", r"(\b)\d+( tracked dependency\b)", rf"\g<1>{dep_edges}\2")
    add("dependency_edges", r"(Dependency edges? \| )\d+", rf"\g<1>{dep_edges}")
    add("dependency_edges", r"(\b)\d+( registry dependency edges?\b)", rf"\g<1>{dep_edges}\2")

    # Sprints
    add("sprints_completed", r"(\b)\d+( sprints completed\b)", rf"\g<1>{sprints}\2")
    add("sprints_completed", r"(Sprints completed \| )\d+", rf"\g<1>{sprints}")

    # Word counts
    add("total_words", r"~\d{3},\d{3}\+?( words)", rf"~{total_words_formatted}+\1")
    add("total_words", r"(?<!~)\b\d{3},\d{3}\+?( words)", rf"{total_words_formatted}+\1")
    add("total_words", r"~?\d{3}K\+?( words)", rf"~{total_words_short}\1")
    add("total_words", r"(Docs-)~?\d{3}K%2B(%20words)", rf"\g<1>~{total_words_k}K%2B\2")
    add(
        "total_words",
        r"(Documentation \| )~?\d{3},?\d{3}\+?( words)",
        rf"\g<1>~{total_words_formatted}+\2",
    )

    return patterns


# Lines containing these markers are historical and should not be updated
SKIP_MARKERS = [
    "Sprint (",
    "Phase 1 (",
    "Phase 2 (",
    "Phase 3 (",
    "Launch (",
    "Silver Sprint:",
    "Bronze Sprint",
    "Gold Sprint",
    "Platinum Sprint",
    "Previous:",
    "Pre-PRAXIS",
    "was pre-existing",
    "**Phase",
    "**Launch",
    "| Total documentation |",
    "| Meta-system essays |",
    "Per-Task TE",
    "README REWRITE",
    "README REVISE",
    "README POPULATE",
    "README EVALUATE",
    "README ARCHIVE",
    "Phase Budgets",
    "5 CI/CD workflow specifications",
    "5 governance",
    "published essays",
    "| COMPLETED |",
]


def load_manifest(manifest_path: Path) -> dict:
    """Load metrics-targets.yaml manifest."""
    with manifest_path.open() as f:
        return yaml.safe_load(f)


def resolve_manifest_files(manifest: dict, corpus_root: Path) -> list[Path]:
    """Resolve all markdown targets from a manifest into concrete file paths."""
    all_files: list[Path] = []
    for target in manifest.get("markdown_targets", []):
        raw_root = target.get("root", ".")
        root = corpus_root if raw_root == "." else Path(raw_root).expanduser().resolve()

        for pattern in target.get("whitelist", []):
            all_files.extend(sorted(root.glob(pattern)))

    # Deduplicate
    seen: set[Path] = set()
    result: list[Path] = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            result.append(f)
    return result


def transform_for_portfolio(canonical: dict, portfolio_path: Path) -> dict:
    """Merge canonical metrics into the portfolio's existing JSON schema.

    The portfolio uses a different structure (registry.*, essays.total) than
    the canonical computed/manual layout. This preserves portfolio-specific
    fields (sprint_history, engagement_baseline, etc.) while updating the
    metrics fields from canonical computed data.
    """
    if portfolio_path.exists():
        with portfolio_path.open() as f:
            portfolio = json.load(f)
    else:
        portfolio = {}

    c = canonical["computed"]

    portfolio["generated"] = canonical["generated"]

    reg = portfolio.get("registry", {})
    reg["total_repos"] = c["total_repos"]
    reg["total_organs"] = c["total_organs"]
    reg["operational_organs"] = c["operational_organs"]
    reg["implementation_status"] = c["implementation_status"]
    reg["ci_coverage"] = c["ci_workflows"]
    reg["dependency_edges"] = c["dependency_edges"]

    organs = reg.get("organs", {})
    for organ_key, info in c.get("per_organ", {}).items():
        if organ_key in organs:
            organs[organ_key]["total_repos"] = info["repos"]
        else:
            organs[organ_key] = {
                "name": info["name"],
                "total_repos": info["repos"],
            }
    reg["organs"] = organs
    portfolio["registry"] = reg

    essays = portfolio.get("essays", {})
    essays["total"] = c.get("published_essays", essays.get("total", 0))
    portfolio["essays"] = essays

    return portfolio


def compute_vitals(metrics: dict) -> dict:
    """Build vitals.json from canonical system-metrics.json.

    Args:
        metrics: Loaded system-metrics.json dict with computed/manual sections.

    Returns:
        Dict matching the vitals.json schema.
    """
    c = metrics["computed"]
    m = metrics.get("manual", {})

    total_repos = c["total_repos"]
    ci_workflows = c["ci_workflows"]
    ci_coverage_pct = round(ci_workflows / total_repos * 100) if total_repos else 0

    return {
        "repos": {
            "total": total_repos,
            "active": c.get("active_repos", 0),
            "orgs": c.get("total_organs", 8),
        },
        "substance": {
            "code_files": c.get("code_files") or m.get("code_files", 0),
            "test_files": c.get("test_files") or m.get("test_files", 0),
            "automated_tests": (
                c.get("repos_with_tests")
                or m.get("automated_tests", m.get("repos_with_tests", 0))
            ),
            "ci_passing": ci_workflows,
            "ci_coverage_pct": ci_coverage_pct,
        },
        "logos": {
            "essays": c.get("published_essays", 0),
            "words": c.get("total_words_numeric") or m.get("total_words_numeric", 0),
            **({"word_breakdown": c["word_counts"]} if "word_counts" in c else {}),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compute_landing(metrics: dict, registry: dict, dest: Path) -> dict:
    """Build landing.json from canonical metrics + registry.

    Preserves sprint_history from existing portfolio system-metrics.json.

    Args:
        metrics: Loaded system-metrics.json dict.
        registry: Loaded registry-v2.json dict.
        dest: Destination path for landing.json (used to find sibling
              system-metrics.json for sprint_history preservation).

    Returns:
        Dict matching the landing.json schema.
    """
    c = metrics["computed"]

    # Build organ list from registry
    organ_meta = {
        "ORGAN-I": ("Theoria", "Theory"),
        "ORGAN-II": ("Poiesis", "Art"),
        "ORGAN-III": ("Ergon", "Commerce"),
        "ORGAN-IV": ("Taxis", "Orchestration"),
        "ORGAN-V": ("Logos", "Public Process"),
        "ORGAN-VI": ("Koinonia", "Community"),
        "ORGAN-VII": ("Kerygma", "Marketing"),
        "META-ORGANVM": ("META-ORGANVM", "META-ORGANVM"),
    }
    organ_orgs = {
        "ORGAN-I": "organvm-i-theoria",
        "ORGAN-II": "organvm-ii-poiesis",
        "ORGAN-III": "organvm-iii-ergon",
        "ORGAN-IV": "organvm-iv-taxis",
        "ORGAN-V": "organvm-v-logos",
        "ORGAN-VI": "organvm-vi-koinonia",
        "ORGAN-VII": "organvm-vii-kerygma",
        "META-ORGANVM": "",
    }

    organs_list = []
    for organ_key, organ_data in registry.get("organs", {}).items():
        greek, nice_name = organ_meta.get(organ_key, (organ_key, organ_key))
        organs_list.append(
            {
                "key": organ_key,
                "name": nice_name,
                "greek": greek,
                "org": organ_orgs.get(organ_key, ""),
                "repo_count": len(organ_data.get("repositories", [])),
                "status": organ_data.get("launch_status", "OPERATIONAL"),
                "description": organ_data.get("description", ""),
            },
        )

    landing_metrics = {
        "total_repos": c["total_repos"],
        "active_repos": c.get("active_repos", 0),
        "archived_repos": c.get("archived_repos", 0),
        "dependency_edges": c.get("dependency_edges", 0),
        "ci_workflows": c.get("ci_workflows", 0),
        "operational_organs": c.get("operational_organs", 8),
        "sprints_completed": c.get("sprints_completed", 0),
    }

    # Preserve sprint_history from existing portfolio system-metrics.json
    sprint_history = []
    sm_path = dest.parent / "system-metrics.json"
    if sm_path.exists():
        with sm_path.open() as f:
            existing = json.load(f)
        sprint_history = existing.get("sprint_history", [])

    return {
        "title": "ORGANVM \u2014 Eight-Organ Creative-Institutional System",
        "tagline": (
            "A living system of 8 organs coordinating theory, art, commerce, "
            "orchestration, public process, community, marketing, and governance."
        ),
        "metrics": landing_metrics,
        "organs": organs_list,
        "sprint_history": sprint_history,
        "generated": datetime.now(timezone.utc).isoformat(),
    }


def copy_json_targets(
    manifest: dict,
    metrics: dict,
    dry_run: bool = False,
    registry: dict | None = None,
) -> int:
    """Process json_copies entries from manifest. Returns count of copies."""
    copies = manifest.get("json_copies", [])
    count = 0
    for entry in copies:
        dest = Path(entry["dest"]).expanduser().resolve()
        transform = entry.get("transform")

        if transform == "portfolio":
            data = transform_for_portfolio(metrics, dest)
        elif transform == "vitals":
            data = compute_vitals(metrics)
        elif transform == "landing":
            if registry is None:
                continue  # skip if no registry provided
            data = compute_landing(metrics, registry, dest)
        else:
            data = metrics

        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")

        count += 1
    return count


def propagate_metrics(
    metrics: dict,
    files: list[Path],
    dry_run: bool = False,
) -> PropagationResult:
    """Apply metric updates to documentation files.

    Args:
        metrics: Loaded system-metrics.json dict.
        files: List of file paths to update.
        dry_run: If True, don't write changes.

    Returns:
        PropagationResult with change details.
    """
    result = PropagationResult()
    patterns = build_patterns(metrics)

    for filepath in files:
        if not filepath.exists():
            continue

        lines = filepath.read_text().splitlines(keepends=True)
        new_lines = []
        file_changed = False

        for line in lines:
            # Skip historical lines
            if any(marker in line for marker in SKIP_MARKERS):
                new_lines.append(line)
                continue

            new_line = line
            for metric_name, pattern, replacement in patterns:
                candidate = pattern.sub(replacement, new_line)
                if candidate != new_line:
                    result.replacements += 1
                    result.details.append(f"{filepath.name}: {metric_name}")
                    new_line = candidate
                    file_changed = True

            new_lines.append(new_line)

        if file_changed:
            result.files_changed += 1
            if not dry_run:
                filepath.write_text("".join(new_lines))

    return result


def propagate_cross_repo(
    metrics: dict,
    manifest_path: Path,
    corpus_root: Path,
    dry_run: bool = False,
    registry: dict | None = None,
) -> PropagationResult:
    """Full cross-repo propagation: JSON copies + markdown updates.

    Args:
        metrics: Loaded system-metrics.json dict.
        manifest_path: Path to metrics-targets.yaml.
        corpus_root: Root of the corpus repo (for relative paths in manifest).
        dry_run: If True, don't write changes.
        registry: Loaded registry-v2.json dict (needed for landing.json transform).

    Returns:
        PropagationResult with combined results.
    """
    manifest = load_manifest(manifest_path)

    # JSON copies
    json_count = copy_json_targets(manifest, metrics, dry_run=dry_run, registry=registry)

    # Markdown propagation
    files = resolve_manifest_files(manifest, corpus_root)
    result = propagate_metrics(metrics, files, dry_run=dry_run)
    result.json_copies = json_count

    return result
