"""Tests for testament digest assembly."""

from organvm_engine.events.spine import EventRecord
from organvm_engine.ledger.digest import DigestSummary, assemble_digest


class TestDigestAssembly:

    def test_empty_events(self):
        digest = assemble_digest([])
        assert digest.event_count == 0
        assert digest.by_type == {}

    def test_counts_by_type(self):
        events = [
            EventRecord(event_type="registry.update", sequence=0),
            EventRecord(event_type="registry.update", sequence=1),
            EventRecord(event_type="seed.update", sequence=2),
        ]
        digest = assemble_digest(events)
        assert digest.event_count == 3
        assert digest.by_type["registry.update"] == 2
        assert digest.by_type["seed.update"] == 1

    def test_counts_by_tier(self):
        events = [
            EventRecord(event_type="governance.promotion", sequence=0),
            EventRecord(event_type="registry.update", sequence=1),
            EventRecord(event_type="git.sync", sequence=2),
        ]
        digest = assemble_digest(events)
        assert digest.by_tier["governance"] == 1
        assert digest.by_tier["operational"] == 1
        assert digest.by_tier["infrastructure"] == 1

    def test_counts_by_organ(self):
        events = [
            EventRecord(
                event_type="test", sequence=0,
                source_organ="META-ORGANVM",
            ),
            EventRecord(
                event_type="test", sequence=1,
                source_organ="META-ORGANVM",
            ),
            EventRecord(
                event_type="test", sequence=2,
                source_organ="ORGAN-I",
            ),
        ]
        digest = assemble_digest(events)
        assert digest.by_organ["META-ORGANVM"] == 2
        assert digest.by_organ["ORGAN-I"] == 1

    def test_governance_highlights(self):
        events = [
            EventRecord(
                event_type="governance.promotion", sequence=0,
                source_repo="test-repo",
            ),
        ]
        digest = assemble_digest(events)
        assert len(digest.governance_highlights) == 1
        assert "test-repo" in digest.governance_highlights[0]

    def test_sequence_range(self):
        events = [
            EventRecord(event_type="test", sequence=5),
            EventRecord(event_type="test", sequence=6),
            EventRecord(event_type="test", sequence=7),
        ]
        digest = assemble_digest(events)
        assert digest.sequence_range == (5, 7)

    def test_render_text(self):
        events = [
            EventRecord(
                event_type="governance.promotion", sequence=0,
                source_repo="test-repo",
            ),
        ]
        digest = assemble_digest(events)
        text = digest.render_text()
        assert "1 event" in text
        assert "governance" in text.lower()
