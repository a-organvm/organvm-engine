"""Tests for pulse/variable_bridge — engine→ontologia state sync."""

from __future__ import annotations

import pytest

from organvm_engine.pulse.variable_bridge import (
    GLOBAL_VAR_SPECS,
    ORGAN_METRIC_SPECS,
    SYSTEM_METRIC_SPECS,
    VariableSyncResult,
    _coerce_value,
    sync_all,
    sync_metrics,
    sync_rollups,
    sync_variables,
)


# ---------------------------------------------------------------------------
# Minimal ontologia store stub (avoids importing ontologia in engine tests)
# ---------------------------------------------------------------------------

class _StubVariable:
    """Minimal variable for testing."""

    def __init__(self, key, value, **kw):
        self.key = key
        self.value = value
        self.var_type = kw.get("var_type")
        self.mutability = kw.get("mutability")
        self.scope = kw.get("scope")
        self.entity_id = kw.get("entity_id")
        self.description = kw.get("description", "")
        self.constraint = kw.get("constraint")


class _StubObservation:
    """Minimal observation for testing."""

    def __init__(self, metric_id, entity_id, value, source="system"):
        self.metric_id = metric_id
        self.entity_id = entity_id
        self.value = value
        self.source = source


class StubStore:
    """In-memory stand-in for ontologia.registry.store.RegistryStore.

    Tracks all set_variable, register_metric, and record_observation calls
    without requiring ontologia as a dependency.
    """

    def __init__(self):
        self.variables: dict[str, _StubVariable] = {}
        self.metrics: dict[str, dict] = {}
        self.observations: list[_StubObservation] = []
        self._reject_keys: set[str] = set()  # keys that will fail on set

    def set_variable(self, var) -> tuple[bool, str]:
        if var.key in self._reject_keys:
            return False, f"Rejected: {var.key}"
        compound = f"{var.key}:{getattr(var, 'entity_id', '') or ''}"
        self.variables[compound] = var
        return True, ""

    def register_metric(self, metric):
        self.metrics[metric.metric_id] = metric

    def record_observation(self, metric_id, entity_id, value, source="system"):
        obs = _StubObservation(metric_id, entity_id, value, source)
        self.observations.append(obs)
        return obs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine_vars() -> dict[str, str]:
    """Representative engine variable manifest."""
    return {
        "total_repos": "113",
        "active_repos": "97",
        "archived_repos": "9",
        "total_organs": "8",
        "operational_organs": "8",
        "ci_workflows": "24",
        "dependency_edges": "28",
        "published_essays": "3",
        "sprints_completed": "2",
        "code_files": "640",
        "test_files": "85",
        "repos_with_tests": "42",
        "total_words_numeric": "404000",
        "total_words_formatted": "404,000",
        "total_words_short": "404K+",
        "organ_repos.ORGAN-I": "20",
        "organ_repos.META-ORGANVM": "8",
        "organ_name.ORGAN-I": "Theoria",
        "organ_name.META-ORGANVM": "Meta",
    }


@pytest.fixture
def organ_map() -> dict[str, str]:
    return {
        "ORGAN-I": "ent_organ_001",
        "META-ORGANVM": "ent_organ_meta",
    }


# ---------------------------------------------------------------------------
# Coercion tests
# ---------------------------------------------------------------------------

class TestCoercion:
    def test_integer(self):
        assert _coerce_value("42", "integer") == 42

    def test_integer_with_commas(self):
        assert _coerce_value("1,234", "integer") == 1234

    def test_integer_invalid(self):
        assert _coerce_value("abc", "integer") == 0

    def test_float(self):
        assert _coerce_value("3.14", "float") == 3.14

    def test_float_invalid(self):
        assert _coerce_value("", "float") == 0.0

    def test_boolean_true(self):
        assert _coerce_value("true", "boolean") is True

    def test_boolean_false(self):
        assert _coerce_value("no", "boolean") is False

    def test_string_passthrough(self):
        assert _coerce_value("hello", "string") == "hello"


# ---------------------------------------------------------------------------
# Variable sync tests
# ---------------------------------------------------------------------------

class TestSyncVariables:
    def test_global_variables_registered(self, engine_vars):
        store = StubStore()
        result = sync_variables(store, engine_vars)
        assert result.variables_set > 0
        assert result.variables_set == len(GLOBAL_VAR_SPECS)

    def test_integer_typed_correctly(self, engine_vars):
        store = StubStore()
        sync_variables(store, engine_vars)
        var = store.variables.get("total_repos:")
        assert var is not None
        assert var.value == 113

    def test_string_typed_correctly(self, engine_vars):
        store = StubStore()
        sync_variables(store, engine_vars)
        var = store.variables.get("total_words_formatted:")
        assert var is not None
        assert var.value == "404,000"

    def test_missing_key_skipped(self):
        store = StubStore()
        result = sync_variables(store, {})  # empty manifest
        assert result.variables_skipped == len(GLOBAL_VAR_SPECS)
        assert result.variables_set == 0

    def test_rejected_variable_counted(self, engine_vars):
        store = StubStore()
        store._reject_keys = {"total_repos"}
        result = sync_variables(store, engine_vars)
        assert result.variables_skipped >= 1

    def test_per_organ_variables(self, engine_vars, organ_map):
        store = StubStore()
        result = sync_variables(store, engine_vars, organ_entity_map=organ_map)
        # Each organ gets repo_count + organ_name = 2 vars × 2 organs = 4
        organ_vars = [k for k in store.variables if "ent_organ" in k]
        assert len(organ_vars) == 4  # 2 per organ

    def test_organ_repo_count_value(self, engine_vars, organ_map):
        store = StubStore()
        sync_variables(store, engine_vars, organ_entity_map=organ_map)
        var = store.variables.get("repo_count:ent_organ_001")
        assert var is not None
        assert var.value == 20

    def test_no_organ_map_skips_organ_vars(self, engine_vars):
        store = StubStore()
        result = sync_variables(store, engine_vars, organ_entity_map=None)
        organ_vars = [k for k in store.variables if "ent_organ" in k]
        assert len(organ_vars) == 0


# ---------------------------------------------------------------------------
# Metric sync tests
# ---------------------------------------------------------------------------

class TestSyncMetrics:
    def test_system_metrics_registered(self, engine_vars):
        store = StubStore()
        result = sync_metrics(store, engine_vars)
        assert result.metrics_registered == len(SYSTEM_METRIC_SPECS)

    def test_observations_recorded(self, engine_vars):
        store = StubStore()
        result = sync_metrics(store, engine_vars)
        # 6 direct mappings + 2 derived (ci_coverage, test_coverage)
        assert result.observations_recorded == 8

    def test_ci_coverage_computed(self, engine_vars):
        store = StubStore()
        sync_metrics(store, engine_vars, system_entity_uid="sys_001")
        ci_obs = [o for o in store.observations if o.metric_id == "met_ci_coverage"]
        assert len(ci_obs) == 1
        # 24/113 * 100 ≈ 21.2
        assert 21.0 <= ci_obs[0].value <= 22.0

    def test_test_coverage_computed(self, engine_vars):
        store = StubStore()
        sync_metrics(store, engine_vars, system_entity_uid="sys_001")
        test_obs = [o for o in store.observations if o.metric_id == "met_test_coverage"]
        assert len(test_obs) == 1
        # 42/113 * 100 ≈ 37.2
        assert 37.0 <= test_obs[0].value <= 38.0

    def test_zero_repos_no_coverage_crash(self):
        """Zero total_repos should not cause division by zero."""
        store = StubStore()
        result = sync_metrics(store, {"total_repos": "0"})
        assert result.observations_recorded >= 0  # no crash

    def test_system_entity_uid_used(self, engine_vars):
        store = StubStore()
        sync_metrics(store, engine_vars, system_entity_uid="sys_test")
        assert all(o.entity_id == "sys_test" for o in store.observations)

    def test_default_entity_id(self, engine_vars):
        store = StubStore()
        sync_metrics(store, engine_vars)
        assert all(o.entity_id == "system" for o in store.observations)

    def test_organ_metrics_registered(self, engine_vars, organ_map):
        store = StubStore()
        result = sync_metrics(store, engine_vars, organ_entity_map=organ_map)
        assert "met_organ_repos" in store.metrics

    def test_organ_observations_recorded(self, engine_vars, organ_map):
        store = StubStore()
        sync_metrics(store, engine_vars, organ_entity_map=organ_map)
        organ_obs = [o for o in store.observations
                     if o.metric_id == "met_organ_repos"]
        assert len(organ_obs) == 2  # one per organ

    def test_organ_observation_values(self, engine_vars, organ_map):
        store = StubStore()
        sync_metrics(store, engine_vars, organ_entity_map=organ_map)
        organ_obs = {o.entity_id: o.value for o in store.observations
                     if o.metric_id == "met_organ_repos"}
        assert organ_obs["ent_organ_001"] == 20.0
        assert organ_obs["ent_organ_meta"] == 8.0

    def test_observation_source_attribution(self, engine_vars):
        store = StubStore()
        sync_metrics(store, engine_vars)
        assert all(o.source == "variable_bridge" for o in store.observations)


# ---------------------------------------------------------------------------
# sync_all tests
# ---------------------------------------------------------------------------

class TestSyncAll:
    def test_combined_result(self, engine_vars, organ_map):
        store = StubStore()
        result = sync_all(
            store, engine_vars,
            system_entity_uid="sys_001",
            organ_entity_map=organ_map,
        )
        assert result.variables_set > 0
        assert result.metrics_registered > 0
        assert result.observations_recorded > 0
        assert isinstance(result.errors, list)

    def test_to_dict(self, engine_vars):
        store = StubStore()
        result = sync_all(store, engine_vars)
        d = result.to_dict()
        assert "variables_set" in d
        assert "metrics_registered" in d
        assert "observations_recorded" in d
        assert "rollups_computed" in d
        assert "errors" in d

    def test_stub_store_no_crash(self, engine_vars, organ_map):
        """StubStore lacks list_metrics/edge_index — sync_all must not raise."""
        store = StubStore()
        result = sync_all(
            store, engine_vars,
            system_entity_uid="sys_001",
            organ_entity_map=organ_map,
        )
        # rollups_computed stays 0 because StubStore has no list_metrics
        assert result.rollups_computed == 0

    def test_rollups_computed_defaults_zero_without_organ_map(self, engine_vars):
        """Without organ_entity_map, rollups are skipped (no uids)."""
        store = StubStore()
        result = sync_all(store, engine_vars)
        assert result.rollups_computed == 0


# ---------------------------------------------------------------------------
# Spec coverage
# ---------------------------------------------------------------------------

class TestSpecCoverage:
    """Verify that all engine var keys have a VarSpec."""

    def test_all_core_keys_covered(self, engine_vars):
        """Every non-organ key from build_vars() should have a VarSpec."""
        spec_keys = {s.key for s in GLOBAL_VAR_SPECS}
        core_keys = {k for k in engine_vars if not k.startswith("organ_")}
        assert core_keys.issubset(spec_keys)

    def test_metric_specs_have_unique_ids(self):
        all_ids = [s.metric_id for s in SYSTEM_METRIC_SPECS + ORGAN_METRIC_SPECS]
        assert len(all_ids) == len(set(all_ids))

    def test_var_specs_have_descriptions(self):
        for spec in GLOBAL_VAR_SPECS:
            assert spec.description, f"{spec.key} missing description"


# ---------------------------------------------------------------------------
# VariableSyncResult.rollups_computed field
# ---------------------------------------------------------------------------

class TestRollupsComputedField:
    """Verify rollups_computed field defaults and serialisation."""

    def test_default_is_zero(self):
        r = VariableSyncResult()
        assert r.rollups_computed == 0

    def test_to_dict_includes_rollups_computed(self):
        r = VariableSyncResult(rollups_computed=7)
        d = r.to_dict()
        assert d["rollups_computed"] == 7

    def test_to_dict_zero_by_default(self):
        r = VariableSyncResult()
        assert r.to_dict()["rollups_computed"] == 0


# ---------------------------------------------------------------------------
# sync_rollups with no organ UIDs
# ---------------------------------------------------------------------------

class TestSyncRollupsNoUids:
    """sync_rollups returns empty result when no UIDs are provided."""

    def test_none_uids_returns_zero(self):
        store = StubStore()
        result = sync_rollups(store, organ_uids=None)
        assert result.rollups_computed == 0
        assert result.errors == []

    def test_empty_list_returns_zero(self):
        store = StubStore()
        result = sync_rollups(store, organ_uids=[])
        assert result.rollups_computed == 0
        assert result.errors == []

    def test_stub_store_without_list_metrics_records_error(self):
        """StubStore lacks list_metrics — error is captured, no crash."""
        store = StubStore()
        result = sync_rollups(store, organ_uids=["ent_organ_001"])
        # StubStore has no list_metrics → AttributeError → error recorded
        assert result.rollups_computed == 0
        assert len(result.errors) == 1
        assert "store missing required attribute" in result.errors[0]


# ---------------------------------------------------------------------------
# sync_rollups with real ontologia RegistryStore
# ---------------------------------------------------------------------------

class TestSyncRollupsRealStore:
    """Integration tests using a real RegistryStore in tmp_path.

    Requires ontologia to be installed in the same venv (it is).
    Uses tmp_path to avoid touching ~/.organvm/.
    """

    @pytest.fixture(autouse=True)
    def _isolate_events(self, tmp_path):
        """Redirect event bus to tmp_path."""
        from ontologia.events import bus as ont_bus
        ont_bus.set_events_path(tmp_path / "events.jsonl")
        ont_bus.clear_subscribers()
        yield
        ont_bus.set_events_path(None)
        ont_bus.clear_subscribers()

    @pytest.fixture
    def real_store(self, tmp_path):
        """A fresh RegistryStore loaded from tmp_path with organ+repo hierarchy."""
        from ontologia.entity.identity import EntityType
        from ontologia.metrics.metric import AggregationPolicy, MetricDefinition, MetricType
        from ontologia.registry.store import RegistryStore

        store_dir = tmp_path / "ontologia"
        store_dir.mkdir()
        store = RegistryStore(store_dir=store_dir)
        store.load()

        # Create organ entity and two repo children
        organ = store.create_entity(EntityType.ORGAN, "ORGAN-I", created_by="test")
        repo_a = store.create_entity(EntityType.REPO, "repo-alpha", created_by="test")
        repo_b = store.create_entity(EntityType.REPO, "repo-beta", created_by="test")

        # Wire hierarchy edges: organ → repo_a, organ → repo_b
        store.add_hierarchy_edge(organ.uid, repo_a.uid)
        store.add_hierarchy_edge(organ.uid, repo_b.uid)

        # Register a metric
        metric = MetricDefinition(
            metric_id="met_organ_repos",
            name="Organ Repo Count",
            metric_type=MetricType.GAUGE,
            unit="count",
            aggregation=AggregationPolicy.SUM,
        )
        store.register_metric(metric)

        # Record observations on the repo children
        store.record_observation("met_organ_repos", repo_a.uid, 10.0, source="test")
        store.record_observation("met_organ_repos", repo_b.uid, 5.0, source="test")

        store.save()
        return store, organ.uid

    def test_rollup_aggregates_children(self, real_store):
        store, organ_uid = real_store
        result = sync_rollups(store, organ_uids=[organ_uid])
        assert result.rollups_computed == 1
        assert result.errors == []

    def test_rollup_records_sum_observation(self, real_store):
        """The rolled-up observation should equal child sum (10 + 5 = 15)."""
        store, organ_uid = real_store
        sync_rollups(store, organ_uids=[organ_uid])
        # Latest observation for the organ should be the rollup
        latest = store.observation_store.latest("met_organ_repos", organ_uid)
        assert latest is not None
        assert latest.value == 15.0
        assert latest.source == "rollup"

    def test_rollup_source_is_rollup(self, real_store):
        store, organ_uid = real_store
        sync_rollups(store, organ_uids=[organ_uid])
        latest = store.observation_store.latest("met_organ_repos", organ_uid)
        assert latest.source == "rollup"

    def test_no_children_no_rollup_recorded(self, tmp_path):
        """An organ with no child observations produces child_count=0 → not recorded."""
        from ontologia.entity.identity import EntityType
        from ontologia.metrics.metric import AggregationPolicy, MetricDefinition, MetricType
        from ontologia.registry.store import RegistryStore

        store_dir = tmp_path / "store2"
        store_dir.mkdir()
        store = RegistryStore(store_dir=store_dir)
        store.load()

        organ = store.create_entity(EntityType.ORGAN, "lonely-organ", created_by="test")
        metric = MetricDefinition(
            metric_id="met_organ_repos",
            name="Organ Repo Count",
            metric_type=MetricType.GAUGE,
            aggregation=AggregationPolicy.SUM,
        )
        store.register_metric(metric)
        # No child observations recorded
        result = sync_rollups(store, organ_uids=[organ.uid])
        assert result.rollups_computed == 0

    def test_multiple_organs_multiple_rollups(self, tmp_path):
        """Two organs each with one child → two rollups."""
        from ontologia.entity.identity import EntityType
        from ontologia.metrics.metric import AggregationPolicy, MetricDefinition, MetricType
        from ontologia.registry.store import RegistryStore

        store_dir = tmp_path / "multi"
        store_dir.mkdir()
        store = RegistryStore(store_dir=store_dir)
        store.load()

        metric = MetricDefinition(
            metric_id="met_organ_repos",
            name="Count",
            metric_type=MetricType.GAUGE,
            aggregation=AggregationPolicy.SUM,
        )
        store.register_metric(metric)

        organ1 = store.create_entity(EntityType.ORGAN, "organ-1", created_by="test")
        repo1 = store.create_entity(EntityType.REPO, "repo-1", created_by="test")
        store.add_hierarchy_edge(organ1.uid, repo1.uid)
        store.record_observation("met_organ_repos", repo1.uid, 7.0, source="test")

        organ2 = store.create_entity(EntityType.ORGAN, "organ-2", created_by="test")
        repo2 = store.create_entity(EntityType.REPO, "repo-2", created_by="test")
        store.add_hierarchy_edge(organ2.uid, repo2.uid)
        store.record_observation("met_organ_repos", repo2.uid, 3.0, source="test")

        result = sync_rollups(store, organ_uids=[organ1.uid, organ2.uid])
        assert result.rollups_computed == 2

    def test_sync_all_with_real_store_populates_rollups_computed(self, real_store, engine_vars):
        """sync_all with a real store and organ_entity_map triggers rollups."""
        store, organ_uid = real_store
        organ_map = {"ORGAN-I": organ_uid}
        result = sync_all(
            store, engine_vars,
            system_entity_uid="sys_test",
            organ_entity_map=organ_map,
        )
        # Should have at least 1 rollup (met_organ_repos on the organ)
        assert result.rollups_computed >= 1
        assert "rollups_computed" in result.to_dict()
