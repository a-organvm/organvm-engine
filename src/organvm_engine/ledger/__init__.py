"""Ledger — the Testament Protocol's native hash-linked event chain.

Extends the constitutional EventSpine (events/spine.py) with cryptographic
hash-linking, Merkle checkpoints, tier classification, and digest assembly.
The EventSpine records events; the ledger makes them tamper-evident.
"""

from organvm_engine.ledger.chain import (
    GENESIS_PREV_HASH,
    ChainVerificationResult,
    compute_event_hash,
    repair_chain,
    verify_chain,
    verify_chain_link,
    verify_hash,
)
from organvm_engine.ledger.digest import DigestSummary, assemble_digest
from organvm_engine.ledger.emit import testament_emit
from organvm_engine.ledger.merkle import (
    compute_merkle_root,
    generate_merkle_proof,
    verify_merkle_proof,
)
from organvm_engine.ledger.rotation import (
    ChainIndex,
    RotatedSegment,
    all_chain_files,
    load_index,
    rebuild_index,
    rotate_chain,
    save_index,
)
from organvm_engine.ledger.tiers import EventTier, classify_event_tier

__all__ = [
    "GENESIS_PREV_HASH",
    "ChainIndex",
    "ChainVerificationResult",
    "DigestSummary",
    "EventTier",
    "RotatedSegment",
    "all_chain_files",
    "assemble_digest",
    "classify_event_tier",
    "compute_event_hash",
    "compute_merkle_root",
    "generate_merkle_proof",
    "load_index",
    "rebuild_index",
    "repair_chain",
    "rotate_chain",
    "save_index",
    "testament_emit",
    "verify_chain",
    "verify_chain_link",
    "verify_hash",
    "verify_merkle_proof",
]
