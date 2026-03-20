"""Merkle tree construction, proof generation, and checkpoint creation.

Implements Ring 2 of the Testament Protocol: periodic integrity snapshots
over event batches. The Merkle root of a batch is itself recorded as a
checkpoint event in the chain — self-referential integrity verification.
"""

from __future__ import annotations

import hashlib


def _hash_pair(left: str, right: str) -> str:
    """Hash two hex-prefixed hashes together."""
    l_hex = left.removeprefix("sha256:")
    r_hex = right.removeprefix("sha256:")
    combined = (l_hex + r_hex).encode("utf-8")
    return f"sha256:{hashlib.sha256(combined).hexdigest()}"


def build_merkle_tree(leaves: list[str]) -> list[list[str]]:
    """Build a complete Merkle tree from leaf hashes.

    Args:
        leaves: List of hash strings (e.g. ``sha256:abc...``).

    Returns:
        List of levels, from leaves (index 0) to root (last index).

    Raises:
        ValueError: If leaves is empty.
    """
    if not leaves:
        raise ValueError("Cannot build Merkle tree from empty leaf list")

    levels: list[list[str]] = [list(leaves)]
    current = list(leaves)

    while len(current) > 1:
        next_level: list[str] = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else current[i]
            next_level.append(_hash_pair(left, right))
        levels.append(next_level)
        current = next_level

    return levels


def compute_merkle_root(leaves: list[str]) -> str:
    """Compute the Merkle root hash of a list of leaf hashes."""
    tree = build_merkle_tree(leaves)
    return tree[-1][0]


def generate_merkle_proof(
    leaves: list[str], leaf_index: int,
) -> list[tuple[str, str]]:
    """Generate a Merkle proof for a specific leaf.

    Args:
        leaves: All leaf hashes in the tree.
        leaf_index: Index of the leaf to prove.

    Returns:
        List of (sibling_hash, side) tuples where side is "left" or "right".
    """
    tree = build_merkle_tree(leaves)
    proof: list[tuple[str, str]] = []
    idx = leaf_index

    for level in tree[:-1]:  # Skip root level
        if idx % 2 == 0:
            sibling_idx = idx + 1
            side = "right"
        else:
            sibling_idx = idx - 1
            side = "left"

        if sibling_idx < len(level):
            proof.append((level[sibling_idx], side))
        else:
            proof.append((level[idx], "right"))  # Promoted (odd count)

        idx //= 2

    return proof


def verify_merkle_proof(
    leaf_hash: str,
    proof: list[tuple[str, str]],
    expected_root: str,
) -> bool:
    """Verify a Merkle proof against an expected root.

    Args:
        leaf_hash: The hash of the leaf being verified.
        proof: List of (sibling_hash, side) from generate_merkle_proof.
        expected_root: The expected Merkle root to verify against.

    Returns:
        True if the proof reconstructs the expected root.
    """
    current = leaf_hash
    for sibling, side in proof:
        current = (
            _hash_pair(sibling, current) if side == "left"
            else _hash_pair(current, sibling)
        )
    return current == expected_root
