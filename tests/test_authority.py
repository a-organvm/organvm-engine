"""Tests for governance.authority — agent authority matrix (SPEC-017)."""

from organvm_engine.governance.authority import (
    IMMUTABLE_SPECS,
    AuthorityLevel,
    agent_ceiling,
    can_amend_spec,
    check_authority,
    is_authorized,
)


# ---------- AuthorityLevel enum ----------

def test_authority_levels_are_ordered():
    assert AuthorityLevel.READ < AuthorityLevel.PROPOSE
    assert AuthorityLevel.PROPOSE < AuthorityLevel.MUTATE
    assert AuthorityLevel.MUTATE < AuthorityLevel.APPROVE


def test_authority_level_values():
    assert AuthorityLevel.READ == 1
    assert AuthorityLevel.PROPOSE == 2
    assert AuthorityLevel.MUTATE == 3
    assert AuthorityLevel.APPROVE == 4


def test_authority_level_count():
    assert len(AuthorityLevel) == 4


# ---------- IMMUTABLE_SPECS ----------

def test_immutable_specs_are_correct():
    assert IMMUTABLE_SPECS == {"SPEC-000", "SPEC-001", "SPEC-002"}


def test_immutable_specs_is_a_set():
    assert isinstance(IMMUTABLE_SPECS, set)


# ---------- check_authority ----------

def test_approve_operations():
    for op in ("amend_spec", "era_transition", "topological_mutation",
               "dissolve_organ", "create_organ"):
        assert check_authority("claude", op) == AuthorityLevel.APPROVE, f"Failed for {op}"


def test_mutate_operations():
    for op in ("promote", "demote", "archive", "update_registry",
               "modify_governance", "merge_repo", "split_repo"):
        assert check_authority("claude", op) == AuthorityLevel.MUTATE, f"Failed for {op}"


def test_propose_operations():
    assert check_authority("claude", "propose_promotion") == AuthorityLevel.PROPOSE
    assert check_authority("gemini", "propose_merge") == AuthorityLevel.PROPOSE
    assert check_authority("human", "propose_anything") == AuthorityLevel.PROPOSE


def test_read_operations():
    for op in ("read_registry", "query", "list_repos", "view"):
        assert check_authority("claude", op) == AuthorityLevel.READ, f"Failed for {op}"


def test_unknown_operation_defaults_to_read():
    assert check_authority("claude", "some_unknown_op") == AuthorityLevel.READ


def test_check_authority_ignores_agent_type():
    """check_authority is purely operation-based; agent_type is for documentation."""
    assert check_authority("claude", "promote") == check_authority("human", "promote")
    assert check_authority("gemini", "amend_spec") == check_authority("codex", "amend_spec")


# ---------- can_amend_spec ----------

def test_immutable_spec_blocked_without_era_context():
    assert can_amend_spec("SPEC-000", has_era_context=False) is False
    assert can_amend_spec("SPEC-001", has_era_context=False) is False
    assert can_amend_spec("SPEC-002", has_era_context=False) is False


def test_immutable_spec_allowed_with_era_context():
    assert can_amend_spec("SPEC-000", has_era_context=True) is True
    assert can_amend_spec("SPEC-001", has_era_context=True) is True
    assert can_amend_spec("SPEC-002", has_era_context=True) is True


def test_mutable_spec_always_allowed():
    for spec_id in ("SPEC-003", "SPEC-008", "SPEC-013", "SPEC-017"):
        assert can_amend_spec(spec_id) is True
        assert can_amend_spec(spec_id, has_era_context=False) is True
        assert can_amend_spec(spec_id, has_era_context=True) is True


# ---------- agent_ceiling ----------

def test_human_ceiling_is_approve():
    assert agent_ceiling("human") == AuthorityLevel.APPROVE


def test_ai_agents_capped_at_mutate():
    for agent in ("claude", "gemini", "codex"):
        assert agent_ceiling(agent) == AuthorityLevel.MUTATE, f"Failed for {agent}"


def test_unknown_agent_capped_at_mutate():
    assert agent_ceiling("some_new_agent") == AuthorityLevel.MUTATE


# ---------- is_authorized ----------

def test_human_authorized_for_approve_ops():
    assert is_authorized("human", "amend_spec") is True
    assert is_authorized("human", "era_transition") is True


def test_ai_not_authorized_for_approve_ops():
    assert is_authorized("claude", "amend_spec") is False
    assert is_authorized("gemini", "era_transition") is False
    assert is_authorized("codex", "topological_mutation") is False


def test_ai_authorized_for_mutate_ops():
    assert is_authorized("claude", "promote") is True
    assert is_authorized("gemini", "archive") is True


def test_all_agents_authorized_for_read():
    for agent in ("claude", "gemini", "codex", "human", "unknown"):
        assert is_authorized(agent, "read_registry") is True


def test_all_agents_authorized_for_propose():
    for agent in ("claude", "gemini", "codex", "human"):
        assert is_authorized(agent, "propose_something") is True
