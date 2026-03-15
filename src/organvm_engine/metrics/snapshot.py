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
        variables = build_vars({"computed": computed_metrics, "manual": {}}, registry)
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

    return {
        "generated_at": now,
        "system": {
            "total_repos": computed_metrics.get("total_repos", len(all_repos)),
            "active_repos": computed_metrics.get("active_repos", 0),
            "density": round(density, 4),
            "entities": entities,
            "edges": edges,
            "ci_workflows": computed_metrics.get("ci_workflows", 0),
            "ammoi": ammoi_text,
        },
        "organs": sorted(organs_list, key=lambda o: o["key"]),
        "variables": variables,
        "omega": omega,
        "promotion_pipeline": dict(sorted(pipeline.items())),
    }


def write_system_snapshot(snapshot: dict, output: Path) -> None:
    import json
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=False)
        f.write("\n")
