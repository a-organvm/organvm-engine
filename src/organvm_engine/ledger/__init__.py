"""Ledger — the Testament Protocol's native hash-linked event chain.

Extends the constitutional EventSpine (events/spine.py) with cryptographic
hash-linking, Merkle checkpoints, tier classification, and digest assembly.
The EventSpine records events; the ledger makes them tamper-evident.
"""

from organvm_engine.ledger.chain import (
    GENESIS_PREV_HASH,
    ChainVerificationResult,
    compute_event_hash,
    verify_chain,
    verify_chain_link,
    verify_hash,
)
from organvm_engine.ledger.digest import DigestSummary, assemble_digest
from organvm_engine.ledger.merkle import (
    compute_merkle_root,
    generate_merkle_proof,
    verify_merkle_proof,
)
from organvm_engine.ledger.tiers import EventTier, classify_event_tier

__all__ = [
    "GENESIS_PREV_HASH",
    "ChainVerificationResult",
    "DigestSummary",
    "EventTier",
    "assemble_digest",
    "classify_event_tier",
    "compute_event_hash",
    "compute_merkle_root",
    "generate_merkle_proof",
    "verify_chain",
    "verify_chain_link",
    "verify_hash",
    "verify_merkle_proof",
]
