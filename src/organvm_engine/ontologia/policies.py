"""Governance policy bridge — defines and evaluates production EvolutionPolicy instances.

Bridges ontologia's policy/revision framework with real system data:
- Defines 6 core policies for promotion, CI, staleness, naming, dependencies
- Loads/saves policies from ~/.organvm/ontologia/policies.json
- Evaluates policies against entity states from the registry
- Creates Revision objects for triggered policies
- Appends to ~/.organvm/ontologia/revisions.jsonl
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

try:
    from ontologia.governance.policies import (
        EvolutionPolicy,
        evaluate_policies,
    )
    from ontologia.governance.revision import Evidence, create_revision
    from ontologia.registry.store import open_store

    HAS_ONTOLOGIA = True
except ImportError:
    HAS_ONTOLOGIA = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_DEFAULT_STORE_DIR = Path.home() / ".organvm" / "ontologia"


# ---------------------------------------------------------------------------
# Core policy definitions
# ---------------------------------------------------------------------------

CORE_POLICIES: list[dict[str, Any]] = [
    {
        "policy_id": "pol-promote-ready",
        "name": "Promotion Readiness",
        "description": (
            "CANDIDATE repos with CI, platinum status, and ACTIVE implementation "
            "are ready for promotion to PUBLIC_PROCESS."
        ),
        "conditions": [
            {"field": "promotion_status", "operator": "eq", "value": "CANDIDATE"},
            {"field": "ci_workflow", "operator": "ne", "value": ""},
            {"field": "platinum_status", "operator": "eq", "value": True},
            {"field": "implementation_status", "operator": "eq", "value": "ACTIVE"},
        ],
        "action": "promote",
        "scope_entity_type": "repo",
        "priority": 10,
        "enabled": True,
    },
    {
        "policy_id": "pol-stale-candidate",
        "name": "Stale Candidate",
        "description": (
            "CANDIDATE repos with no validation in 90+ days need attention."
        ),
        "conditions": [
            {"field": "promotion_status", "operator": "eq", "value": "CANDIDATE"},
            {"field": "days_since_validation", "operator": "gt", "value": 90},
        ],
        "action": "flag",
        "scope_entity_type": "repo",
        "priority": 5,
        "enabled": True,
    },
    {
        "policy_id": "pol-missing-ci",
        "name": "Missing CI",
        "description": (
            "Non-infrastructure, non-archived repos without CI workflow need one."
        ),
        "conditions": [
            {"field": "ci_workflow", "operator": "eq", "value": ""},
            {"field": "tier", "operator": "not_in", "value": ["infrastructure", "archive"]},
            {"field": "promotion_status", "operator": "ne", "value": "ARCHIVED"},
        ],
        "action": "flag",
        "scope_entity_type": "repo",
        "priority": 7,
        "enabled": True,
    },
    {
        "policy_id": "pol-archive-idle",
        "name": "Idle Archive Candidate",
        "description": (
            "Repos idle for 180+ days that aren't GRADUATED may need archiving."
        ),
        "conditions": [
            {"field": "days_since_validation", "operator": "gt", "value": 180},
            {"field": "promotion_status", "operator": "ne", "value": "GRADUATED"},
            {"field": "promotion_status", "operator": "ne", "value": "ARCHIVED"},
        ],
        "action": "flag",
        "scope_entity_type": "repo",
        "priority": 3,
        "enabled": True,
    },
    {
        "policy_id": "pol-naming-drift",
        "name": "Naming Drift",
        "description": (
            "Entity primary name doesn't match the repo name in the registry."
        ),
        "conditions": [
            {"field": "name_matches_repo", "operator": "eq", "value": False},
        ],
        "action": "notify",
        "scope_entity_type": "repo",
        "priority": 2,
        "enabled": True,
    },
    {
        "policy_id": "pol-dep-violation",
        "name": "Dependency Violation",
        "description": (
            "Repo depends on an organ that creates a back-edge "
            "(violates I->II->III unidirectional flow)."
        ),
        "conditions": [
            {"field": "has_dependency_violation", "operator": "eq", "value": True},
        ],
        "action": "flag",
        "scope_entity_type": "repo",
        "priority": 8,
        "enabled": True,
    },
]


# ---------------------------------------------------------------------------
# Policy I/O
# ---------------------------------------------------------------------------

def policies_path(store_dir: Path | None = None) -> Path:
    d = store_dir or _DEFAULT_STORE_DIR
    return d / "policies.json"


def revisions_path(store_dir: Path | None = None) -> Path:
    d = store_dir or _DEFAULT_STORE_DIR
    return d / "revisions.jsonl"


def load_policies(store_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load policies from JSON file, bootstrapping if needed."""
    path = policies_path(store_dir)
    if not path.is_file():
        bootstrap_policies(store_dir)
    try:
        data = json.loads(path.read_text())
        return data.get("policies", []) if isinstance(data, dict) else data
    except (OSError, json.JSONDecodeError):
        return CORE_POLICIES


def save_policies(
    policy_dicts: list[dict[str, Any]],
    store_dir: Path | None = None,
) -> None:
    """Save policies to JSON file."""
    path = policies_path(store_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"policies": policy_dicts, "updated_at": _now_iso()},
        indent=2,
    ))


def bootstrap_policies(store_dir: Path | None = None) -> None:
    """Write the core policies to disk if not present."""
    path = policies_path(store_dir)
    if not path.is_file():
        save_policies(CORE_POLICIES, store_dir)


def append_revision(
    revision_dict: dict[str, Any],
    store_dir: Path | None = None,
) -> None:
    """Append a revision to the JSONL log."""
    path = revisions_path(store_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(revision_dict, separators=(",", ":"), default=str)
    with path.open("a") as f:
        f.write(line + "\n")


def load_revisions(
    store_dir: Path | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Load revisions from JSONL, optionally filtered by status."""
    path = revisions_path(store_dir)
    if not path.is_file():
        return []
    revisions: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rev = json.loads(line)
            if status and rev.get("status") != status:
                continue
            revisions.append(rev)
        except json.JSONDecodeError:
            continue
    return revisions[-limit:]


# ---------------------------------------------------------------------------
# Policy evaluation against real data
# ---------------------------------------------------------------------------

def _build_entity_state(
    repo: dict[str, Any],
    entity_name: str | None = None,
    store=None,
) -> dict[str, Any]:
    """Build the state dict that policies evaluate against.

    Enriches raw registry fields with computed properties like
    days_since_validation and name_matches_repo.
    """
    state = {
        "promotion_status": repo.get("promotion_status", ""),
        "ci_workflow": repo.get("ci_workflow", ""),
        "platinum_status": repo.get("platinum_status", False),
        "implementation_status": repo.get("implementation_status", ""),
        "tier": repo.get("tier", ""),
        "public": repo.get("public", False),
    }

    # Compute days since validation
    last_v = repo.get("last_validated", "")
    if last_v:
        try:
            dt = datetime.fromisoformat(last_v.replace("Z", "+00:00"))
            state["days_since_validation"] = (
                datetime.now(timezone.utc) - dt
            ).days
        except (ValueError, TypeError):
            state["days_since_validation"] = 999
    else:
        state["days_since_validation"] = 999

    # Check name match
    repo_name = repo.get("name", "")
    state["name_matches_repo"] = True
    if store and entity_name:
        state["name_matches_repo"] = entity_name == repo_name

    # Dependency violations: computed by governance module
    state["has_dependency_violation"] = False
    deps = repo.get("dependencies", [])
    if isinstance(deps, list) and deps:
        # Placeholder — real violation checking uses governance/dependency_graph
        state["has_dependency_violation"] = False

    return state


def evaluate_all_policies(
    registry_path: Path | None = None,
    store_dir: Path | None = None,
    write_revisions: bool = False,
) -> dict[str, Any]:
    """Evaluate all policies against all repo entities.

    Returns:
        {
            "evaluated": int,
            "triggered": [
                {"policy_id": ..., "policy_name": ..., "entity": ..., "action": ...},
                ...
            ],
            "revisions_created": int,
        }
    """
    policy_dicts = load_policies(store_dir)

    # Load registry
    reg_path = registry_path
    if reg_path is None:
        try:
            from organvm_engine.paths import registry_path as _rp
            reg_path = _rp()
        except Exception:
            return {"error": "Cannot resolve registry path"}

    try:
        registry = json.loads(reg_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"error": f"Cannot read registry: {reg_path}"}

    # Optionally use ontologia types
    if HAS_ONTOLOGIA:
        policies = [EvolutionPolicy.from_dict(p) for p in policy_dicts]
        import contextlib

        store = None
        with contextlib.suppress(Exception):
            store = open_store(Path(store_dir) if store_dir else None)
    else:
        policies = policy_dicts
        store = None

    triggered: list[dict[str, Any]] = []
    evaluated = 0
    revisions_created = 0

    for _organ_key, organ_data in registry.get("organs", {}).items():
        for repo in organ_data.get("repositories", []):
            name = repo.get("name", "")
            entity_state = _build_entity_state(repo, name, store)
            evaluated += 1

            if HAS_ONTOLOGIA:
                matched = evaluate_policies(cast(list, policies), entity_state, "repo")
                for policy in matched:
                    entry = {
                        "policy_id": policy.policy_id,
                        "policy_name": policy.name,
                        "action": policy.action.value,
                        "entity": name,
                        "organ": organ_data.get("name", ""),
                    }
                    triggered.append(entry)

                    if write_revisions:
                        rev = create_revision(
                            title=f"{policy.name}: {name}",
                            action=policy.action.value,
                            affected_entities=[name],
                            triggered_by=policy.policy_id,
                        )
                        rev.add_evidence(Evidence(
                            evidence_type="policy_trigger",
                            description=f"Policy {policy.policy_id} triggered",
                            data=entity_state,
                        ))
                        append_revision(rev.to_dict(), store_dir)
                        revisions_created += 1
            else:
                # Fallback: manual condition evaluation
                for pol_dict in policy_dicts:
                    if not pol_dict.get("enabled", True):
                        continue
                    scope = pol_dict.get("scope_entity_type")
                    if scope and scope != "repo":
                        continue
                    conditions = pol_dict.get("conditions", [])
                    all_met = all(
                        _eval_condition(c, entity_state) for c in conditions
                    )
                    if all_met:
                        triggered.append({
                            "policy_id": pol_dict["policy_id"],
                            "policy_name": pol_dict["name"],
                            "action": pol_dict.get("action", "flag"),
                            "entity": name,
                            "organ": organ_data.get("name", ""),
                        })

    return {
        "evaluated": evaluated,
        "triggered": triggered,
        "revisions_created": revisions_created,
    }


def _eval_condition(cond: dict[str, Any], state: dict[str, Any]) -> bool:
    """Evaluate a single policy condition without ontologia."""
    field_val = state.get(cond.get("field", ""))
    op = cond.get("operator", "eq")
    expected = cond.get("value")

    if op == "eq":
        return field_val == expected
    if op == "ne":
        return field_val != expected
    if op == "gt":
        return field_val is not None and field_val > expected
    if op == "lt":
        return field_val is not None and field_val < expected
    if op == "gte":
        return field_val is not None and field_val >= expected
    if op == "lte":
        return field_val is not None and field_val <= expected
    if op == "in":
        return field_val in expected if expected is not None else False
    if op == "not_in":
        return field_val not in expected if expected is not None else True
    if op == "contains":
        return expected in field_val if field_val else False
    return False
