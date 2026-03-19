"""Tests for governance.fusion — repo fusion protocol (SPEC-012)."""

from organvm_engine.governance.fusion import (
    FusionClassification,
    FusionComponent,
    FusionPlan,
    classify_fusion_component,
    is_elevation,
    validate_fusion_plan,
)


# ---------- FusionClassification enum ----------

def test_classification_enum_values():
    assert FusionClassification.RETAIN_A.value == "retain_a"
    assert FusionClassification.RETAIN_B.value == "retain_b"
    assert FusionClassification.SYNTHESIZE.value == "synthesize"
    assert FusionClassification.INVENT.value == "invent"


def test_classification_enum_count():
    assert len(FusionClassification) == 4


# ---------- classify_fusion_component ----------

def test_novel_always_invent():
    c = classify_fusion_component("new-thing", novel=True, in_a=True, in_b=True)
    assert c.classification == FusionClassification.INVENT


def test_both_repos_mergeable_synthesize():
    c = classify_fusion_component("shared", in_a=True, in_b=True, mergeable=True)
    assert c.classification == FusionClassification.SYNTHESIZE


def test_only_in_a_retain_a():
    c = classify_fusion_component("a-only", in_a=True, in_b=False)
    assert c.classification == FusionClassification.RETAIN_A


def test_only_in_b_retain_b():
    c = classify_fusion_component("b-only", in_a=False, in_b=True)
    assert c.classification == FusionClassification.RETAIN_B


def test_both_not_mergeable_defaults_to_retain_a():
    c = classify_fusion_component("conflict", in_a=True, in_b=True, mergeable=False)
    assert c.classification == FusionClassification.RETAIN_A


def test_neither_repo_defaults_to_invent():
    c = classify_fusion_component("absent", in_a=False, in_b=False)
    assert c.classification == FusionClassification.INVENT


def test_classify_preserves_metadata():
    c = classify_fusion_component(
        "config",
        in_a=True,
        in_b=False,
        source_a="src/config.py",
        source_b="",
        rationale="Only exists in A",
    )
    assert c.name == "config"
    assert c.source_a == "src/config.py"
    assert c.source_b == ""
    assert c.rationale == "Only exists in A"


# ---------- FusionPlan ----------

def test_plan_classification_counts():
    plan = FusionPlan(
        repo_a="alpha",
        repo_b="beta",
        target_name="gamma",
        components=[
            FusionComponent("a", FusionClassification.RETAIN_A),
            FusionComponent("b", FusionClassification.RETAIN_B),
            FusionComponent("c", FusionClassification.SYNTHESIZE),
            FusionComponent("d", FusionClassification.INVENT),
            FusionComponent("e", FusionClassification.RETAIN_A),
        ],
    )
    counts = plan.classification_counts
    assert counts["retain_a"] == 2
    assert counts["retain_b"] == 1
    assert counts["synthesize"] == 1
    assert counts["invent"] == 1


def test_plan_has_elevation_with_synthesize():
    plan = FusionPlan(
        repo_a="a", repo_b="b", target_name="c",
        components=[FusionComponent("x", FusionClassification.SYNTHESIZE)],
    )
    assert plan.has_elevation is True


def test_plan_has_elevation_with_invent():
    plan = FusionPlan(
        repo_a="a", repo_b="b", target_name="c",
        components=[FusionComponent("x", FusionClassification.INVENT)],
    )
    assert plan.has_elevation is True


def test_plan_no_elevation_retain_only():
    plan = FusionPlan(
        repo_a="a", repo_b="b", target_name="c",
        components=[
            FusionComponent("x", FusionClassification.RETAIN_A),
            FusionComponent("y", FusionClassification.RETAIN_B),
        ],
    )
    assert plan.has_elevation is False


def test_plan_empty_components():
    plan = FusionPlan(repo_a="a", repo_b="b", target_name="c")
    assert plan.classification_counts == {}
    assert plan.has_elevation is False


# ---------- validate_fusion_plan ----------

def test_valid_plan_no_warnings():
    plan = FusionPlan(
        repo_a="alpha",
        repo_b="beta",
        target_name="gamma",
        elevation_rationale="Combines search and indexing into unified query engine",
        components=[
            FusionComponent("search", FusionClassification.RETAIN_A),
            FusionComponent("index", FusionClassification.RETAIN_B),
            FusionComponent("query-engine", FusionClassification.SYNTHESIZE),
        ],
    )
    warnings = validate_fusion_plan(plan)
    assert warnings == []


def test_empty_plan_warns():
    plan = FusionPlan(repo_a="a", repo_b="b", target_name="c")
    warnings = validate_fusion_plan(plan)
    assert any("no components" in w for w in warnings)


def test_no_elevation_warns():
    plan = FusionPlan(
        repo_a="a", repo_b="b", target_name="c",
        components=[FusionComponent("x", FusionClassification.RETAIN_A)],
    )
    warnings = validate_fusion_plan(plan)
    assert any("consolidation" in w for w in warnings)


def test_target_same_as_repo_a_warns():
    plan = FusionPlan(
        repo_a="alpha", repo_b="beta", target_name="alpha",
        components=[FusionComponent("x", FusionClassification.SYNTHESIZE)],
        elevation_rationale="test",
    )
    warnings = validate_fusion_plan(plan)
    assert any("same as repo A" in w for w in warnings)


def test_target_same_as_repo_b_warns():
    plan = FusionPlan(
        repo_a="alpha", repo_b="beta", target_name="beta",
        components=[FusionComponent("x", FusionClassification.SYNTHESIZE)],
        elevation_rationale="test",
    )
    warnings = validate_fusion_plan(plan)
    assert any("same as repo B" in w for w in warnings)


def test_duplicate_component_names_warns():
    plan = FusionPlan(
        repo_a="a", repo_b="b", target_name="c",
        elevation_rationale="test",
        components=[
            FusionComponent("x", FusionClassification.RETAIN_A),
            FusionComponent("x", FusionClassification.RETAIN_B),
            FusionComponent("y", FusionClassification.SYNTHESIZE),
        ],
    )
    warnings = validate_fusion_plan(plan)
    assert any("Duplicate" in w for w in warnings)


def test_elevation_without_rationale_warns():
    plan = FusionPlan(
        repo_a="a", repo_b="b", target_name="c",
        components=[FusionComponent("x", FusionClassification.SYNTHESIZE)],
    )
    warnings = validate_fusion_plan(plan)
    assert any("no rationale" in w for w in warnings)


# ---------- is_elevation ----------

def test_is_elevation_true_when_new_capabilities():
    result = {"capabilities": ["search", "index", "unified-query"]}
    a = {"capabilities": ["search"]}
    b = {"capabilities": ["index"]}
    assert is_elevation(result, a, b) is True


def test_is_elevation_false_when_subset():
    result = {"capabilities": ["search", "index"]}
    a = {"capabilities": ["search"]}
    b = {"capabilities": ["index"]}
    assert is_elevation(result, a, b) is False


def test_is_elevation_empty_capabilities():
    assert is_elevation({}, {}, {}) is False
    assert is_elevation({"capabilities": []}, {"capabilities": ["x"]}, {}) is False
