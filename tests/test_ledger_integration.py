"""End-to-end integration test for the Testament Protocol."""

from __future__ import annotations

from organvm_engine.events.spine import EventSpine
from organvm_engine.ledger.chain import GENESIS_PREV_HASH, verify_chain
from organvm_engine.ledger.digest import assemble_digest
from organvm_engine.ledger.merkle import (
    compute_merkle_root,
    generate_merkle_proof,
    verify_merkle_proof,
)
from organvm_engine.ledger.tiers import EventTier, classify_event_tier


class TestFullProtocol:
    """End-to-end: genesis -> emit events -> verify -> checkpoint -> digest."""

    def test_complete_lifecycle(self, tmp_path):
        chain_path = tmp_path / "chain.jsonl"
        spine = EventSpine(chain_path)

        # 1. Genesis
        genesis = spine.emit(
            event_type="testament.genesis",
            entity_uid="",
            source_organ="META-ORGANVM",
            source_repo="organvm-engine",
            actor="human:4jp",
            payload={"message": "Chain begins."},
        )
        assert genesis.sequence == 0
        assert genesis.prev_hash == GENESIS_PREV_HASH

        # 2. Emit a variety of events
        events = [genesis]
        etypes = [
            "governance.promotion",
            "registry.update",
            "seed.update",
            "metrics.update",
            "git.sync",
            "ci.health",
            "content.published",
            "ecosystem.mutation",
            "agent.punch_in",
            "ontologia.variable",
        ]
        for i, etype in enumerate(etypes, start=1):
            r = spine.emit(
                event_type=etype,
                entity_uid=f"ent_{i}",
                source_organ="META-ORGANVM",
                source_repo=f"repo-{i}",
                actor="test",
                payload={"index": i},
                causal_predecessor=events[-1].event_id if i == 1 else "",
            )
            events.append(r)

        assert len(events) == 11

        # 3. Verify chain integrity
        result = verify_chain(chain_path)
        assert result.valid is True
        assert result.event_count == 11

        # 4. Merkle checkpoint
        leaves = [ev.hash for ev in events]
        root = compute_merkle_root(leaves)
        assert root.startswith("sha256:")

        for i in range(len(leaves)):
            proof = generate_merkle_proof(leaves, i)
            assert verify_merkle_proof(leaves[i], proof, root)

        # 5. Tier classification
        tiers = [classify_event_tier(ev.event_type) for ev in events]
        assert EventTier.GOVERNANCE in tiers
        assert EventTier.MILESTONE in tiers
        assert EventTier.OPERATIONAL in tiers
        assert EventTier.INFRASTRUCTURE in tiers

        # 6. Digest
        digest = assemble_digest(events)
        assert digest.event_count == 11
        assert digest.governance_highlights
        text = digest.render_text()
        assert "11 event" in text

        # 7. Re-read from disk and verify
        reloaded = spine.query(limit=100)
        assert len(reloaded) == 11
        for r in reloaded:
            assert r.hash.startswith("sha256:")

    def test_causal_chain(self, tmp_path):
        """Causal predecessor forms a traceable DAG."""
        spine = EventSpine(tmp_path / "chain.jsonl")

        r1 = spine.emit(
            event_type="governance.audit",
            entity_uid="ent_a",
            actor="test",
        )
        r2 = spine.emit(
            event_type="governance.promotion",
            entity_uid="ent_a",
            actor="test",
            causal_predecessor=r1.event_id,
        )
        assert r2.causal_predecessor == r1.event_id
        assert r2.sequence == 1

    def test_chain_survives_reload(self, tmp_path):
        """Chain properties persist across EventSpine instances."""
        path = tmp_path / "chain.jsonl"

        spine1 = EventSpine(path)
        r1 = spine1.emit(event_type="test", entity_uid="e", actor="t")

        spine2 = EventSpine(path)
        r2 = spine2.emit(event_type="test", entity_uid="e", actor="t")

        assert r2.sequence == 1
        assert r2.prev_hash == r1.hash

        result = verify_chain(path)
        assert result.valid is True
        assert result.event_count == 2
