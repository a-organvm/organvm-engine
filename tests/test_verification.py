"""Tests for the verification module — all four formal logic layers."""

import json
import time

import pytest

from organvm_engine.verification.contracts import (
    CONTRACTS,
    ContractResult,
    DispatchContract,
    verify_contract,
)
from organvm_engine.verification.idempotency import DispatchLedger, LedgerEntry
from organvm_engine.verification.model_check import VerificationReport, verify_system
from organvm_engine.verification.temporal import (
    PrerequisiteResult,
    TemporalResult,
    verify_prerequisite_chain,
    verify_temporal_order,
)


# ── Contract tests ──────────────────────────────────────────────────


class TestDispatchContract:
    def test_check_payload_all_fields_present(self):
        contract = DispatchContract(
            event_pattern="test.event",
            required_payload_fields={"name": str, "count": int},
        )
        errors = contract.check_payload({"name": "foo", "count": 42})
        assert errors == []

    def test_check_payload_missing_field(self):
        contract = DispatchContract(
            event_pattern="test.event",
            required_payload_fields={"name": str, "count": int},
        )
        errors = contract.check_payload({"name": "foo"})
        assert len(errors) == 1
        assert "Missing required field: count" in errors[0]

    def test_check_payload_wrong_type(self):
        contract = DispatchContract(
            event_pattern="test.event",
            required_payload_fields={"name": str, "count": int},
        )
        errors = contract.check_payload({"name": "foo", "count": "not-an-int"})
        assert len(errors) == 1
        assert "expected int" in errors[0]

    def test_check_payload_validator_passes(self):
        contract = DispatchContract(
            event_pattern="test.event",
            required_payload_fields={"name": str},
            required_payload_validators={"name": lambda v: len(v) > 0},
        )
        errors = contract.check_payload({"name": "hello"})
        assert errors == []

    def test_check_payload_validator_fails(self):
        contract = DispatchContract(
            event_pattern="test.event",
            required_payload_fields={"name": str},
            required_payload_validators={"name": lambda v: len(v) > 0},
        )
        errors = contract.check_payload({"name": ""})
        assert len(errors) == 1
        assert "Validator failed" in errors[0]

    def test_check_payload_validator_exception(self):
        def bad_validator(v):
            raise ValueError("boom")

        contract = DispatchContract(
            event_pattern="test.event",
            required_payload_fields={"x": str},
            required_payload_validators={"x": bad_validator},
        )
        errors = contract.check_payload({"x": "hello"})
        assert len(errors) == 1
        assert "Validator error" in errors[0]

    def test_check_payload_validator_on_missing_field_skipped(self):
        """Validators for missing fields are skipped (missing field error takes priority)."""
        contract = DispatchContract(
            event_pattern="test.event",
            required_payload_fields={"name": str},
            required_payload_validators={"name": lambda v: len(v) > 0},
        )
        errors = contract.check_payload({})
        assert len(errors) == 1
        assert "Missing required field" in errors[0]

    def test_empty_contract_has_no_errors(self):
        contract = DispatchContract(event_pattern="test.event")
        errors = contract.check_payload({"anything": "goes"})
        assert errors == []


class TestVerifyContract:
    def test_known_event_passes(self):
        result = verify_contract(
            "theory.published",
            {"artifact_id": "abc123", "title": "My Theory", "source_repo": "styx"},
        )
        assert result.passed
        assert result.contract_found
        assert result.errors == []

    def test_known_event_fails_missing_field(self):
        result = verify_contract(
            "theory.published",
            {"artifact_id": "abc123"},
        )
        assert not result.passed
        assert result.contract_found
        assert len(result.errors) >= 1

    def test_known_event_fails_empty_string(self):
        result = verify_contract(
            "theory.published",
            {"artifact_id": "", "title": "ok", "source_repo": "styx"},
        )
        assert not result.passed
        assert any("Validator failed" in e for e in result.errors)

    def test_unknown_event_passes_no_contract(self):
        result = verify_contract(
            "unknown.event",
            {"whatever": True},
        )
        assert result.passed
        assert not result.contract_found

    def test_result_to_dict(self):
        result = ContractResult(
            event_type="test.event",
            passed=True,
            errors=[],
            contract_found=True,
        )
        d = result.to_dict()
        assert d["event_type"] == "test.event"
        assert d["passed"] is True


class TestContractRegistry:
    def test_all_registered_contracts_have_fields(self):
        """Every registered contract should have at least one required field."""
        for event_type, contract in CONTRACTS.items():
            assert contract.required_payload_fields, (
                f"Contract '{event_type}' has no required payload fields"
            )

    def test_all_validators_reference_existing_fields(self):
        """Validators should reference fields that exist in required_payload_fields."""
        for event_type, contract in CONTRACTS.items():
            for vfield in contract.required_payload_validators:
                assert vfield in contract.required_payload_fields, (
                    f"Contract '{event_type}': validator for '{vfield}' "
                    f"not in required_payload_fields"
                )

    def test_eight_contracts_registered(self):
        assert len(CONTRACTS) == 10

    def test_theory_published_contract(self):
        c = CONTRACTS["theory.published"]
        assert "artifact_id" in c.required_payload_fields
        assert "title" in c.required_payload_fields
        assert "source_repo" in c.required_payload_fields
        assert c.consumes_trigger is True

    def test_essay_published_contract(self):
        c = CONTRACTS["essay.published"]
        assert "word_count" in c.required_payload_fields
        assert c.required_payload_fields["word_count"] is int
        assert c.consumes_trigger is True


# ── Temporal tests ──────────────────────────────────────────────────


class TestTemporalOrder:
    def test_forward_flow_allowed(self):
        result = verify_temporal_order(
            "theory.published",
            "organvm-i-theoria",
            "organvm-ii-poiesis",
        )
        assert result.valid

    def test_same_level_allowed(self):
        result = verify_temporal_order(
            "internal.event",
            "organvm-i-theoria",
            "organvm-i-theoria",
        )
        assert result.valid

    def test_back_edge_rejected(self):
        result = verify_temporal_order(
            "bad.event",
            "organvm-iii-ergon",
            "organvm-i-theoria",
        )
        assert not result.valid
        assert "Back-edge" in result.reason

    def test_non_restricted_always_allowed(self):
        """Organs IV-VIII can send to any organ."""
        result = verify_temporal_order(
            "governance.updated",
            "meta-organvm",
            "organvm-i-theoria",
        )
        assert result.valid

    def test_restricted_to_non_restricted_allowed(self):
        result = verify_temporal_order(
            "product.release",
            "organvm-iii-ergon",
            "organvm-vii-kerygma",
        )
        assert result.valid

    def test_unknown_organ_passes(self):
        result = verify_temporal_order(
            "test.event",
            "unknown-organ",
            "organvm-i-theoria",
        )
        assert result.valid
        assert "Unrecognized" in result.reason

    def test_result_to_dict(self):
        result = TemporalResult(
            source_organ="a",
            target_organ="b",
            valid=True,
            reason="ok",
        )
        d = result.to_dict()
        assert d["valid"] is True


class TestPrerequisiteChain:
    def test_empty_seed_graph(self):
        result = verify_prerequisite_chain("theory.published", {})
        assert result.passed
        assert result.chain == []

    def test_valid_forward_chain(self):
        seeds = {
            "ivviiviivvi/styx": {
                "organ": "ORGAN-I",
                "org": "ivviiviivvi",
                "repo": "styx",
                "produces": [{"type": "theory.published", "targets": ["ORGAN-II"]}],
            },
            "omni/consumer": {
                "organ": "ORGAN-II",
                "org": "omni",
                "repo": "consumer",
                "consumes": [{"type": "theory.published", "source": "ORGAN-I"}],
            },
        }
        result = verify_prerequisite_chain("theory.published", seeds)
        assert result.passed
        assert len(result.chain) == 2

    def test_result_to_dict(self):
        result = PrerequisiteResult(event_type="test", chain=["a"], violations=[])
        d = result.to_dict()
        assert d["passed"] is True


# ── Idempotency tests ──────────────────────────────────────────────


class TestDispatchLedger:
    def test_record_new_dispatch(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        result = ledger.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II")
        assert result is True

    def test_record_duplicate_rejected(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        assert ledger.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II")
        assert ledger.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II") is False

    def test_consume_dispatch(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        ledger.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II")
        assert ledger.consume("abc-123") is True
        assert ledger.is_consumed("abc-123")

    def test_consume_unknown_returns_false(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        assert ledger.consume("nonexistent") is False

    def test_consume_already_consumed_returns_false(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        ledger.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II")
        ledger.consume("abc-123")
        assert ledger.consume("abc-123") is False

    def test_reject_dispatch(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        ledger.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II")
        assert ledger.reject("abc-123") is True
        assert ledger.get_status("abc-123") == "rejected"

    def test_reject_unknown_returns_false(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        assert ledger.reject("nonexistent") is False

    def test_get_status_unknown(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        assert ledger.get_status("nonexistent") == "unknown"

    def test_get_status_pending(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        ledger.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II")
        assert ledger.get_status("abc-123") == "pending"

    def test_is_known(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        assert not ledger.is_known("abc-123")
        ledger.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II")
        assert ledger.is_known("abc-123")

    def test_status_summary(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        ledger.record("a", "e1", "s1", "t1")
        ledger.record("b", "e2", "s2", "t2")
        ledger.consume("a")
        status = ledger.status()
        assert status.total == 2
        assert status.consumed == 1
        assert status.pending == 1

    def test_find_duplicates(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        ledger.record("a", "theory.published", "ORGAN-I", "ORGAN-II")
        ledger.record("b", "theory.published", "ORGAN-I", "ORGAN-II")
        dupes = ledger.find_duplicates("theory.published", "ORGAN-I", "ORGAN-II")
        assert len(dupes) == 2

    def test_recent_entries(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        ledger.record("a", "e1", "s1", "t1")
        recent = ledger.recent(hours=1)
        assert len(recent) == 1

    def test_persistence_across_instances(self, tmp_path):
        path = tmp_path / "ledger.jsonl"
        ledger1 = DispatchLedger(path)
        ledger1.record("abc-123", "theory.published", "ORGAN-I", "ORGAN-II")

        ledger2 = DispatchLedger(path)
        assert ledger2.is_known("abc-123")
        assert ledger2.get_status("abc-123") == "pending"

    def test_empty_ledger_file(self, tmp_path):
        path = tmp_path / "ledger.jsonl"
        path.write_text("")
        ledger = DispatchLedger(path)
        status = ledger.status()
        assert status.total == 0

    def test_malformed_jsonl_lines_skipped(self, tmp_path):
        path = tmp_path / "ledger.jsonl"
        path.write_text("not json\n{bad\n")
        ledger = DispatchLedger(path)
        status = ledger.status()
        assert status.total == 0

    def test_ledger_entry_to_dict(self):
        entry = LedgerEntry(
            dispatch_id="abc",
            event="theory.published",
            source="ORGAN-I",
            target="ORGAN-II",
            timestamp=1000.0,
        )
        d = entry.to_dict()
        assert d["dispatch_id"] == "abc"
        assert d["status"] == "pending"

    def test_ledger_entry_from_dict(self):
        d = {
            "dispatch_id": "abc",
            "event": "theory.published",
            "source": "ORGAN-I",
            "target": "ORGAN-II",
            "timestamp": 1000.0,
            "status": "consumed",
        }
        entry = LedgerEntry.from_dict(d)
        assert entry.dispatch_id == "abc"
        assert entry.status == "consumed"


# ── Model check tests ──────────────────────────────────────────────


class TestVerifySystem:
    def test_empty_system_passes(self):
        report = verify_system({}, {})
        assert report.passed
        assert report.contract_coverage == 100.0

    def test_system_with_seed_graph(self):
        seeds = {
            "ivviiviivvi/styx": {
                "organ": "ORGAN-I",
                "org": "ivviiviivvi",
                "repo": "styx",
                "produces": [{"type": "theory.published"}],
            },
        }
        report = verify_system({"organs": {}}, seeds)
        # theory.published has a contract, so coverage should be 100%
        assert report.contract_coverage == 100.0
        assert report.contracts_checked > 0

    def test_uncovered_events_detected(self):
        seeds = {
            "org/repo": {
                "organ": "ORGAN-I",
                "org": "org",
                "repo": "repo",
                "produces": [{"type": "custom.unusual_event"}],
            },
        }
        report = verify_system({"organs": {}}, seeds)
        assert "custom.unusual_event" in report.uncovered_events

    def test_system_with_ledger(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        ledger.record("a", "theory.published", "ORGAN-I", "ORGAN-II")
        ledger.record("b", "theory.published", "ORGAN-I", "ORGAN-II")

        report = verify_system({"organs": {}}, {}, ledger)
        assert report.ledger_total == 2
        assert report.ledger_duplicates == 1
        assert len(report.idempotency_risks) >= 1

    def test_report_to_dict(self):
        report = VerificationReport(
            vacuous_truths=["a"],
            temporal_violations=["b"],
        )
        d = report.to_dict()
        assert d["passed"] is False
        assert "a" in d["vacuous_truths"]

    def test_report_passed_property(self):
        assert VerificationReport().passed
        assert not VerificationReport(vacuous_truths=["x"]).passed
        assert not VerificationReport(temporal_violations=["x"]).passed
        assert not VerificationReport(idempotency_risks=["x"]).passed

    def test_stale_pending_detected(self, tmp_path):
        ledger = DispatchLedger(tmp_path / "ledger.jsonl")
        # Manually create an old entry
        entry_data = {
            "dispatch_id": "old-one",
            "event": "theory.published",
            "source": "ORGAN-I",
            "target": "ORGAN-II",
            "timestamp": time.time() - 100000,  # ~28 hours ago
            "status": "pending",
        }
        (tmp_path / "ledger.jsonl").write_text(json.dumps(entry_data) + "\n")

        ledger2 = DispatchLedger(tmp_path / "ledger.jsonl")
        report = verify_system({"organs": {}}, {}, ledger2)
        assert any("Stale pending" in r for r in report.idempotency_risks)
