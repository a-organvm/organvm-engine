"""Tests for formation engine (INST-FORMATION)."""

import pytest

from organvm_engine.governance.formations import (
    Formation,
    FormationType,
    SignalClass,
    classify_repo_formation,
    validate_formation,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_formation():
    """A complete, valid formation dict using post-flood signal vocabulary."""
    return {
        "formation_type": "GENERATOR",
        "host_organ": "ORGAN-I",
        "host_repo": "theory-core",
        "signals_in": ["RESEARCH_QUESTION"],
        "signals_out": ["ONT_FRAGMENT", "STATE_MODEL"],
        "maturity": 0.7,
        "exit_modes": ["deprecate", "merge"],
    }


# ---------------------------------------------------------------------------
# FormationType enum
# ---------------------------------------------------------------------------


class TestFormationType:
    def test_all_seven(self):
        assert len(FormationType) == 7
        assert FormationType.GENERATOR.value == "GENERATOR"
        assert FormationType.SYNTHESIZER.value == "SYNTHESIZER"


# ---------------------------------------------------------------------------
# SignalClass enum
# ---------------------------------------------------------------------------


class TestSignalClass:
    def test_canonical_14_post_flood(self):
        """Post-flood Formation Protocol §8.1 defines exactly 14 signal classes."""
        assert len(SignalClass) == 14
        assert SignalClass.ONT_FRAGMENT.value == "ONT_FRAGMENT"
        assert SignalClass.RULE_PROPOSAL.value == "RULE_PROPOSAL"
        assert SignalClass.STATE_MODEL.value == "STATE_MODEL"
        assert SignalClass.ANNOTATED_CORPUS.value == "ANNOTATED_CORPUS"
        assert SignalClass.ARCHIVE_PACKET.value == "ARCHIVE_PACKET"
        assert SignalClass.EXECUTION_TRACE.value == "EXECUTION_TRACE"
        assert SignalClass.RESEARCH_QUESTION.value == "RESEARCH_QUESTION"

    def test_pre_flood_signals_removed(self):
        """Pre-flood signals (CODE_ARTIFACT, etc.) must not exist."""
        names = {s.value for s in SignalClass}
        assert "CODE_ARTIFACT" not in names
        assert "DOC_ARTIFACT" not in names
        assert "USER_INPUT" not in names
        assert "QUERY_RESULT" not in names


# ---------------------------------------------------------------------------
# Formation dataclass
# ---------------------------------------------------------------------------


class TestFormation:
    def test_from_dict(self, valid_formation):
        f = Formation.from_dict(valid_formation)
        assert f.formation_type == "GENERATOR"
        assert f.host_organ == "ORGAN-I"
        assert len(f.signals_out) == 2

    def test_to_dict_roundtrip(self, valid_formation):
        f = Formation.from_dict(valid_formation)
        d = f.to_dict()
        assert d["formation_type"] == "GENERATOR"
        assert d["maturity"] == 0.7

    def test_empty_from_dict(self):
        f = Formation.from_dict({})
        assert f.formation_type == ""
        assert f.maturity == 0.0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidateFormation:
    def test_valid_passes(self, valid_formation):
        valid, errors = validate_formation(valid_formation)
        assert valid is True
        assert errors == []

    def test_invalid_type(self):
        data = {
            "formation_type": "INVALID",
            "host_organ": "ORGAN-I",
            "host_repo": "test",
            "signals_out": ["ONT_FRAGMENT"],
        }
        valid, errors = validate_formation(data)
        assert valid is False
        assert any("formation_type" in e for e in errors)

    def test_missing_host_organ(self, valid_formation):
        del valid_formation["host_organ"]
        valid, errors = validate_formation(valid_formation)
        assert valid is False
        assert any("host_organ" in e for e in errors)

    def test_missing_host_repo(self, valid_formation):
        del valid_formation["host_repo"]
        valid, errors = validate_formation(valid_formation)
        assert valid is False

    def test_empty_signals_out(self, valid_formation):
        valid_formation["signals_out"] = []
        valid, errors = validate_formation(valid_formation)
        assert valid is False
        assert any("signals_out" in e for e in errors)

    def test_prohibited_coupling_router_ont(self):
        data = {
            "formation_type": "ROUTER",
            "host_organ": "ORGAN-IV",
            "host_repo": "router-core",
            "signals_out": ["ONT_FRAGMENT"],
            "maturity": 0.5,
        }
        valid, errors = validate_formation(data)
        assert valid is False
        assert any("prohibited" in e.lower() for e in errors)

    def test_prohibited_coupling_reservoir_ont(self):
        """Reservoir Law §15: RESERVOIR may not emit ONT_FRAGMENT."""
        data = {
            "formation_type": "RESERVOIR",
            "host_organ": "ORGAN-I",
            "host_repo": "memory-corpus",
            "signals_out": ["ONT_FRAGMENT"],
            "maturity": 0.5,
        }
        valid, errors = validate_formation(data)
        assert valid is False
        assert any("prohibited" in e.lower() for e in errors)

    def test_reservoir_allowed_outputs(self):
        """Reservoir Law §15: RESERVOIR may emit ANNOTATED_CORPUS."""
        data = {
            "formation_type": "RESERVOIR",
            "host_organ": "ORGAN-I",
            "host_repo": "memory-corpus",
            "signals_out": ["ANNOTATED_CORPUS", "ARCHIVE_PACKET"],
            "maturity": 0.5,
        }
        valid, errors = validate_formation(data)
        assert valid is True

    def test_maturity_out_of_range(self, valid_formation):
        valid_formation["maturity"] = 1.5
        valid, errors = validate_formation(valid_formation)
        assert valid is False
        assert any("maturity" in e for e in errors)

    def test_negative_maturity(self, valid_formation):
        valid_formation["maturity"] = -0.1
        valid, errors = validate_formation(valid_formation)
        assert valid is False

    def test_unknown_signal_class(self, valid_formation):
        valid_formation["signals_out"] = ["INVENTED_SIGNAL"]
        valid, errors = validate_formation(valid_formation)
        assert valid is False
        assert any("unknown signal" in e.lower() for e in errors)

    def test_unknown_signal_in_inputs(self, valid_formation):
        valid_formation["signals_in"] = ["NOT_A_SIGNAL"]
        valid, errors = validate_formation(valid_formation)
        assert valid is False


# ---------------------------------------------------------------------------
# Heuristic classification
# ---------------------------------------------------------------------------


class TestClassifyRepoFormation:
    def test_engine_is_generator(self):
        repo = {"name": "organvm-engine", "description": "Core engine"}
        assert classify_repo_formation(repo) == FormationType.GENERATOR

    def test_dashboard_is_interface(self):
        repo = {"name": "system-dashboard", "description": "Web dashboard"}
        assert classify_repo_formation(repo) == FormationType.INTERFACE

    def test_corpus_is_reservoir(self):
        repo = {"name": "organvm-corpvs", "description": "Governance corpus"}
        assert classify_repo_formation(repo) == FormationType.RESERVOIR

    def test_infra_is_router(self):
        repo = {"name": "ci-tooling", "tier": "infrastructure"}
        assert classify_repo_formation(repo) == FormationType.ROUTER

    def test_collider_is_synthesizer(self):
        repo = {"name": "materia-collider", "description": "Fusion reactor"}
        assert classify_repo_formation(repo) == FormationType.SYNTHESIZER

    def test_unknown_returns_none(self):
        repo = {"name": "misc-stuff", "description": "Random things"}
        assert classify_repo_formation(repo) is None
