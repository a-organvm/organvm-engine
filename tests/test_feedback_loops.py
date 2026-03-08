"""Tests for governance/feedback_loops.py."""

import pytest

from organvm_engine.governance.feedback_loops import (
    FeedbackLoop,
    FeedbackLoopInventory,
    LoopPolarity,
    LoopStatus,
    LoopStratum,
    build_feedback_inventory,
    detect_active_loops,
)


class TestFeedbackLoop:
    def test_to_dict(self):
        loop = FeedbackLoop(
            name="test-loop",
            polarity=LoopPolarity.POSITIVE,
            status=LoopStatus.MAPPED,
            stratum=LoopStratum.ARCHITECTURE,
            description="A test loop",
            nodes=["A", "B"],
            governing_mechanism="test.py",
            risk="could break",
        )
        d = loop.to_dict()
        assert d["name"] == "test-loop"
        assert d["polarity"] == "positive"
        assert d["status"] == "mapped"
        assert d["stratum"] == "architecture"
        assert d["nodes"] == ["A", "B"]
        assert d["governing_mechanism"] == "test.py"
        assert d["risk"] == "could break"

    def test_to_dict_no_optional(self):
        loop = FeedbackLoop(
            name="minimal",
            polarity=LoopPolarity.NEGATIVE,
            status=LoopStatus.UNMAPPED,
            stratum=LoopStratum.SUBSTRATE,
            description="Minimal loop",
            nodes=[],
        )
        d = loop.to_dict()
        assert d["governing_mechanism"] is None
        assert d["risk"] is None


class TestFeedbackLoopInventory:
    def _make_inventory(self):
        return FeedbackLoopInventory(loops=[
            FeedbackLoop(
                name="neg-mapped",
                polarity=LoopPolarity.NEGATIVE,
                status=LoopStatus.MAPPED,
                stratum=LoopStratum.ARCHITECTURE,
                description="Negative mapped",
                nodes=["A"],
                governing_mechanism="test",
            ),
            FeedbackLoop(
                name="pos-observed",
                polarity=LoopPolarity.POSITIVE,
                status=LoopStatus.OBSERVED,
                stratum=LoopStratum.EMERGENT,
                description="Positive observed",
                nodes=["B", "C"],
                risk="could grow",
            ),
            FeedbackLoop(
                name="pos-unmapped",
                polarity=LoopPolarity.POSITIVE,
                status=LoopStatus.UNMAPPED,
                stratum=LoopStratum.ENVIRONMENT,
                description="Positive unmapped",
                nodes=["D"],
                risk="unknown",
            ),
        ])

    def test_counts(self):
        inv = self._make_inventory()
        assert inv.positive_count == 2
        assert inv.negative_count == 1
        assert inv.mapped_count == 1
        assert inv.observed_count == 1
        assert inv.unmapped_count == 1

    def test_by_polarity(self):
        inv = self._make_inventory()
        pos = inv.by_polarity(LoopPolarity.POSITIVE)
        assert len(pos) == 2
        neg = inv.by_polarity(LoopPolarity.NEGATIVE)
        assert len(neg) == 1

    def test_by_status(self):
        inv = self._make_inventory()
        mapped = inv.by_status(LoopStatus.MAPPED)
        assert len(mapped) == 1
        assert mapped[0].name == "neg-mapped"

    def test_by_stratum(self):
        inv = self._make_inventory()
        arch = inv.by_stratum(LoopStratum.ARCHITECTURE)
        assert len(arch) == 1

    def test_ungoverned_positive(self):
        inv = self._make_inventory()
        ungov = inv.ungoverned_positive()
        assert len(ungov) == 2
        names = {l.name for l in ungov}
        assert "pos-observed" in names
        assert "pos-unmapped" in names

    def test_summary_contains_key_info(self):
        inv = self._make_inventory()
        s = inv.summary()
        assert "Total: 3 loops" in s
        assert "Positive: 2" in s
        assert "Negative: 1" in s
        assert "UNGOVERNED POSITIVE LOOPS" in s

    def test_to_dict(self):
        inv = self._make_inventory()
        d = inv.to_dict()
        assert d["total"] == 3
        assert d["ungoverned_positive"] == 2
        assert len(d["loops"]) == 3

    def test_empty_inventory(self):
        inv = FeedbackLoopInventory()
        assert inv.positive_count == 0
        assert inv.negative_count == 0
        assert inv.ungoverned_positive() == []
        assert "Total: 0 loops" in inv.summary()


class TestBuildFeedbackInventory:
    def test_returns_canonical_loops(self):
        inv = build_feedback_inventory()
        assert len(inv.loops) > 0

    def test_has_both_polarities(self):
        inv = build_feedback_inventory()
        assert inv.positive_count > 0
        assert inv.negative_count > 0

    def test_negative_loops_are_mostly_mapped(self):
        inv = build_feedback_inventory()
        neg = inv.by_polarity(LoopPolarity.NEGATIVE)
        mapped = [l for l in neg if l.status == LoopStatus.MAPPED]
        # Most negative loops should be mapped (governance is well-defined)
        assert len(mapped) >= len(neg) - 2

    def test_positive_loops_have_risks(self):
        inv = build_feedback_inventory()
        pos = inv.by_polarity(LoopPolarity.POSITIVE)
        with_risk = [l for l in pos if l.risk]
        assert len(with_risk) == len(pos)

    def test_all_loops_have_nodes(self):
        inv = build_feedback_inventory()
        for loop in inv.loops:
            assert len(loop.nodes) > 0, f"{loop.name} has no nodes"

    def test_all_loops_have_descriptions(self):
        inv = build_feedback_inventory()
        for loop in inv.loops:
            assert len(loop.description) > 10, f"{loop.name} has short description"

    def test_unique_names(self):
        inv = build_feedback_inventory()
        names = [l.name for l in inv.loops]
        assert len(names) == len(set(names)), "Duplicate loop names found"


class TestDetectActiveLoops:
    def test_returns_inventory(self):
        reg = {"organs": {}}
        inv = detect_active_loops(reg)
        assert isinstance(inv, FeedbackLoopInventory)
        assert len(inv.loops) > 0

    def test_with_seed_graph(self):
        """Smoke test with a mock seed graph."""
        class MockGraph:
            edges = [
                ("organvm-iii-ergon/product", "organvm-v-logos/essay", "content"),
                ("organvm-v-logos/essay", "organvm-vi-koinonia/community", "reference"),
            ]

        reg = {"organs": {}}
        inv = detect_active_loops(reg, seed_graph=MockGraph())
        assert isinstance(inv, FeedbackLoopInventory)
