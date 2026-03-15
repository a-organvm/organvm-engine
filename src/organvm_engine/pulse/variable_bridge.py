"""Bridge engine system state into ontologia's formal variable and metric stores.

Translates the engine's flat string manifest (build_vars) into ontologia's
typed Variable model with scope, mutability, and constraints. Also registers
MetricDefinitions for key system gauges and records initial observations.

Called during pulse_once() to keep ontologia's variable/metric state in sync
with the engine's computed metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Variable definitions — what engine keys map to in ontologia
# ---------------------------------------------------------------------------

@dataclass
class VarSpec:
    """Blueprint for registering an engine variable in ontologia."""

    key: str
    description: str
    var_type: str = "integer"       # string | integer | float | boolean
    mutability: str = "computed"    # computed = derived from engine state
    scope: str = "global"          # global | organ
    min_value: float | None = None
    max_value: float | None = None


# Global system variables — one value for the whole system
GLOBAL_VAR_SPECS: list[VarSpec] = [
    VarSpec("total_repos", "Total number of repositories in the registry",
            min_value=0),
    VarSpec("active_repos", "Number of non-archived repositories",
            min_value=0),
    VarSpec("archived_repos", "Number of archived repositories",
            min_value=0),
    VarSpec("total_organs", "Number of organs in the system",
            min_value=1, max_value=20),
    VarSpec("operational_organs", "Number of organs with active repositories",
            min_value=0),
    VarSpec("ci_workflows", "Number of repositories with CI workflows",
            min_value=0),
    VarSpec("dependency_edges", "Number of seed graph dependency edges",
            min_value=0),
    VarSpec("published_essays", "Number of published essays",
            min_value=0),
    VarSpec("sprints_completed", "Number of completed sprints",
            min_value=0),
    VarSpec("code_files", "Total number of source code files",
            min_value=0),
    VarSpec("test_files", "Total number of test files",
            min_value=0),
    VarSpec("repos_with_tests", "Number of repositories with test suites",
            min_value=0),
    VarSpec("total_words_numeric", "Total word count across all documents",
            min_value=0),
    VarSpec("total_words_formatted", "Formatted word count (comma-separated)",
            var_type="string"),
    VarSpec("total_words_short", "Abbreviated word count (e.g., '404K+')",
            var_type="string"),
]


# ---------------------------------------------------------------------------
# Metric definitions — gauges recorded as observations
# ---------------------------------------------------------------------------

@dataclass
class MetricSpec:
    """Blueprint for registering a metric in ontologia."""

    metric_id: str
    name: str
    unit: str = "count"
    description: str = ""
    metric_type: str = "gauge"
    aggregation: str = "sum"
    entity_type_scope: str | None = None  # "organ" or "repo" or None (system)


SYSTEM_METRIC_SPECS: list[MetricSpec] = [
    MetricSpec("met_total_repos", "Total Repositories",
               description="System-wide repository count"),
    MetricSpec("met_active_repos", "Active Repositories",
               description="Non-archived repository count"),
    MetricSpec("met_ci_coverage", "CI Coverage",
               unit="percent", aggregation="avg",
               description="Percentage of repos with CI workflows"),
    MetricSpec("met_test_coverage", "Test Coverage",
               unit="percent", aggregation="avg",
               description="Percentage of repos with test suites"),
    MetricSpec("met_dependency_edges", "Dependency Edges",
               description="Seed graph inter-repo edges"),
    MetricSpec("met_code_files", "Source Files",
               description="Total source code files across all repos"),
    MetricSpec("met_test_files", "Test Files",
               description="Total test files across all repos"),
    MetricSpec("met_total_words", "Total Words",
               unit="words",
               description="Word count across all documentation"),
]

# Per-organ metrics — registered per organ entity
ORGAN_METRIC_SPECS: list[MetricSpec] = [
    MetricSpec("met_organ_repos", "Organ Repository Count",
               description="Number of repositories in this organ",
               entity_type_scope="organ"),
]


# ---------------------------------------------------------------------------
# Sync result
# ---------------------------------------------------------------------------

@dataclass
class VariableSyncResult:
    """Summary of a variable+metric bridge sync run."""

    variables_set: int = 0
    variables_skipped: int = 0
    metrics_registered: int = 0
    observations_recorded: int = 0
    rollups_computed: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variables_set": self.variables_set,
            "variables_skipped": self.variables_skipped,
            "metrics_registered": self.metrics_registered,
            "observations_recorded": self.observations_recorded,
            "rollups_computed": self.rollups_computed,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Core sync functions
# ---------------------------------------------------------------------------

def _coerce_value(raw: str, var_type: str) -> Any:
    """Coerce an engine string value to the appropriate Python type."""
    if var_type == "integer":
        try:
            return int(raw.replace(",", ""))
        except (ValueError, AttributeError):
            return 0
    if var_type == "float":
        try:
            return float(raw)
        except (ValueError, AttributeError):
            return 0.0
    if var_type == "boolean":
        return raw.lower() in ("true", "1", "yes")
    return raw  # string


def sync_variables(
    store: Any,
    engine_vars: dict[str, str],
    organ_entity_map: dict[str, str] | None = None,
) -> VariableSyncResult:
    """Sync engine system variables into ontologia's VariableStore.

    Args:
        store: An ontologia RegistryStore instance.
        engine_vars: Flat key→string manifest from build_vars().
        organ_entity_map: Optional {organ_registry_key: ontologia_entity_uid}
            for per-organ variable scoping. If None, only global vars are set.

    Returns:
        VariableSyncResult with counts.
    """
    from ontologia.variables.variable import (
        Constraint,
        Mutability,
        Scope,
        Variable,
        VariableType,
    )

    result = VariableSyncResult()
    type_map = {
        "string": VariableType.STRING,
        "integer": VariableType.INTEGER,
        "float": VariableType.FLOAT,
        "boolean": VariableType.BOOLEAN,
    }
    mut_map = {
        "constant": Mutability.CONSTANT,
        "runtime": Mutability.RUNTIME,
        "computed": Mutability.COMPUTED,
    }

    # --- Global variables ---
    for spec in GLOBAL_VAR_SPECS:
        raw = engine_vars.get(spec.key)
        if raw is None:
            result.variables_skipped += 1
            continue

        value = _coerce_value(raw, spec.var_type)

        constraint = None
        if spec.min_value is not None or spec.max_value is not None:
            constraint = Constraint(
                min_value=spec.min_value,
                max_value=spec.max_value,
            )

        var = Variable(
            key=spec.key,
            value=value,
            var_type=type_map.get(spec.var_type, VariableType.STRING),
            mutability=mut_map.get(spec.mutability, Mutability.COMPUTED),
            scope=Scope.GLOBAL,
            description=spec.description,
            constraint=constraint,
        )

        ok, msg = store.set_variable(var)
        if ok:
            result.variables_set += 1
        else:
            # Computed vars may already exist — update by clearing and re-setting
            result.variables_skipped += 1
            logger.debug("Variable %s skipped: %s", spec.key, msg)

    # --- Per-organ variables ---
    if organ_entity_map:
        for organ_key, entity_uid in organ_entity_map.items():
            repo_count_key = f"organ_repos.{organ_key}"
            raw = engine_vars.get(repo_count_key)
            if raw is None:
                continue

            var = Variable(
                key="repo_count",
                value=_coerce_value(raw, "integer"),
                var_type=VariableType.INTEGER,
                mutability=Mutability.COMPUTED,
                scope=Scope.ORGAN,
                entity_id=entity_uid,
                description=f"Repository count for {organ_key}",
            )
            ok, msg = store.set_variable(var)
            if ok:
                result.variables_set += 1
            else:
                result.variables_skipped += 1

            # Organ name
            name_key = f"organ_name.{organ_key}"
            name_raw = engine_vars.get(name_key, "")
            if name_raw:
                var = Variable(
                    key="organ_name",
                    value=name_raw,
                    var_type=VariableType.STRING,
                    mutability=Mutability.CONSTANT,
                    scope=Scope.ORGAN,
                    entity_id=entity_uid,
                    description=f"Display name for {organ_key}",
                )
                ok, _ = store.set_variable(var)
                if ok:
                    result.variables_set += 1

    return result


def sync_metrics(
    store: Any,
    engine_vars: dict[str, str],
    system_entity_uid: str = "",
    organ_entity_map: dict[str, str] | None = None,
) -> VariableSyncResult:
    """Register metric definitions and record current observations.

    Args:
        store: An ontologia RegistryStore instance.
        engine_vars: Flat key→string manifest from build_vars().
        system_entity_uid: Entity UID representing the whole system.
            If empty, uses "system" as the entity_id.
        organ_entity_map: Optional {organ_key: entity_uid} for per-organ metrics.

    Returns:
        VariableSyncResult with metrics_registered and observations_recorded counts.
    """
    from ontologia.metrics.metric import (
        AggregationPolicy,
        MetricDefinition,
        MetricType,
    )

    result = VariableSyncResult()
    sys_id = system_entity_uid or "system"
    type_map = {
        "gauge": MetricType.GAUGE,
        "counter": MetricType.COUNTER,
        "delta": MetricType.DELTA,
    }
    agg_map = {
        "sum": AggregationPolicy.SUM,
        "avg": AggregationPolicy.AVG,
        "max": AggregationPolicy.MAX,
        "latest": AggregationPolicy.LATEST,
    }

    # Mapping from metric_id to engine_vars key for observation values
    metric_to_var = {
        "met_total_repos": "total_repos",
        "met_active_repos": "active_repos",
        "met_dependency_edges": "dependency_edges",
        "met_code_files": "code_files",
        "met_test_files": "test_files",
        "met_total_words": "total_words_numeric",
    }

    # --- Register system metrics + record observations ---
    for spec in SYSTEM_METRIC_SPECS:
        metric = MetricDefinition(
            metric_id=spec.metric_id,
            name=spec.name,
            metric_type=type_map.get(spec.metric_type, MetricType.GAUGE),
            unit=spec.unit,
            description=spec.description,
            aggregation=agg_map.get(spec.aggregation, AggregationPolicy.SUM),
            entity_type_scope=spec.entity_type_scope,
        )
        store.register_metric(metric)
        result.metrics_registered += 1

        # Record observation if we have a value
        var_key = metric_to_var.get(spec.metric_id)
        if var_key and var_key in engine_vars:
            try:
                value = float(engine_vars[var_key].replace(",", ""))
                store.record_observation(
                    spec.metric_id, sys_id, value, source="variable_bridge",
                )
                result.observations_recorded += 1
            except (ValueError, TypeError) as e:
                result.errors.append(f"Observation {spec.metric_id}: {e}")

    # Derived metrics: CI coverage and test coverage
    total = int(engine_vars.get("total_repos", "0").replace(",", "") or "0")
    if total > 0:
        ci = int(engine_vars.get("ci_workflows", "0").replace(",", "") or "0")
        store.record_observation(
            "met_ci_coverage", sys_id,
            round(ci / total * 100, 1),
            source="variable_bridge",
        )
        result.observations_recorded += 1

        tests = int(engine_vars.get("repos_with_tests", "0").replace(",", "") or "0")
        store.record_observation(
            "met_test_coverage", sys_id,
            round(tests / total * 100, 1),
            source="variable_bridge",
        )
        result.observations_recorded += 1

    # --- Per-organ metrics ---
    if organ_entity_map:
        for spec in ORGAN_METRIC_SPECS:
            metric = MetricDefinition(
                metric_id=spec.metric_id,
                name=spec.name,
                metric_type=type_map.get(spec.metric_type, MetricType.GAUGE),
                unit=spec.unit,
                description=spec.description,
                aggregation=agg_map.get(spec.aggregation, AggregationPolicy.SUM),
                entity_type_scope="organ",
            )
            store.register_metric(metric)
            result.metrics_registered += 1

        for organ_key, entity_uid in organ_entity_map.items():
            raw = engine_vars.get(f"organ_repos.{organ_key}", "0")
            try:
                value = float(raw)
                store.record_observation(
                    "met_organ_repos", entity_uid, value,
                    source="variable_bridge",
                )
                result.observations_recorded += 1
            except (ValueError, TypeError):
                pass

    return result


def sync_rollups(
    store: Any,
    organ_uids: list[str] | None = None,
) -> VariableSyncResult:
    """Aggregate child repo observations up to each organ entity.

    Iterates over all registered metrics × organ UIDs, calls
    ``rollup_for_entity()`` from ontologia, and records the rolled-up
    values as new observations with ``source="rollup"``.

    Args:
        store: A real ontologia RegistryStore instance.  The store must
            expose ``list_metrics()``, ``edge_index``, and
            ``observation_store`` — i.e. it must be a proper RegistryStore,
            not a stub.
        organ_uids: Explicit list of organ entity UIDs to roll up.  If
            None, the function skips rollup silently (no UIDs to process).

    Returns:
        VariableSyncResult with ``rollups_computed`` set to the number of
        successful rollup observations recorded.
    """
    from ontologia.metrics.rollups import rollup_for_entity

    result = VariableSyncResult()

    if not organ_uids:
        return result

    try:
        metrics = store.list_metrics()
        edge_index = store.edge_index
        obs_store = store.observation_store
    except AttributeError as exc:
        result.errors.append(f"sync_rollups: store missing required attribute: {exc}")
        return result

    for metric in metrics:
        for uid in organ_uids:
            try:
                rollup = rollup_for_entity(uid, metric, edge_index, obs_store)
                if rollup.child_count > 0:
                    store.record_observation(
                        metric.metric_id,
                        uid,
                        rollup.value,
                        source="rollup",
                    )
                    result.rollups_computed += 1
            except Exception as exc:  # noqa: BLE001
                result.errors.append(
                    f"sync_rollups: {metric.metric_id}@{uid}: {exc}",
                )

    return result


def sync_all(
    store: Any,
    engine_vars: dict[str, str],
    system_entity_uid: str = "",
    organ_entity_map: dict[str, str] | None = None,
) -> VariableSyncResult:
    """Run variable sync, metric sync, and rollup aggregation in one call.

    This is the main entry point called from pulse_once().
    """
    r1 = sync_variables(store, engine_vars, organ_entity_map)
    r2 = sync_metrics(store, engine_vars, system_entity_uid, organ_entity_map)

    organ_uids = list(organ_entity_map.values()) if organ_entity_map else None
    try:
        r3 = sync_rollups(store, organ_uids)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_rollups failed: %s", exc)
        r3 = VariableSyncResult(errors=[f"sync_rollups: {exc}"])

    return VariableSyncResult(
        variables_set=r1.variables_set + r2.variables_set,
        variables_skipped=r1.variables_skipped + r2.variables_skipped,
        metrics_registered=r2.metrics_registered,
        observations_recorded=r2.observations_recorded,
        rollups_computed=r3.rollups_computed,
        errors=r1.errors + r2.errors + r3.errors,
    )
