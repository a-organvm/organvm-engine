"""Tests for Merkle tree operations in the Testament Protocol."""

from __future__ import annotations

import pytest

from organvm_engine.ledger.merkle import (
    build_merkle_tree,
    compute_merkle_root,
    generate_merkle_proof,
    verify_merkle_proof,
)


class TestMerkleTree:

    def test_single_leaf(self):
        root = compute_merkle_root(["sha256:aaa"])
        assert root == "sha256:aaa"

    def test_two_leaves(self):
        root = compute_merkle_root(["sha256:aaa", "sha256:bbb"])
        assert root.startswith("sha256:")
        assert root != "sha256:aaa"
        assert root != "sha256:bbb"

    def test_deterministic(self):
        leaves = [f"sha256:{chr(97 + i) * 64}" for i in range(4)]
        r1 = compute_merkle_root(leaves)
        r2 = compute_merkle_root(leaves)
        assert r1 == r2

    def test_order_matters(self):
        leaves = ["sha256:aaa", "sha256:bbb"]
        r1 = compute_merkle_root(leaves)
        r2 = compute_merkle_root(["sha256:bbb", "sha256:aaa"])
        assert r1 != r2

    def test_odd_leaf_count(self):
        root = compute_merkle_root(["sha256:a", "sha256:b", "sha256:c"])
        assert root.startswith("sha256:")

    def test_empty_leaves_raises(self):
        with pytest.raises(ValueError):
            compute_merkle_root([])

    def test_build_tree_levels(self):
        leaves = [f"sha256:{i:064x}" for i in range(4)]
        tree = build_merkle_tree(leaves)
        assert len(tree) == 3  # leaves, middle, root
        assert len(tree[0]) == 4
        assert len(tree[1]) == 2
        assert len(tree[2]) == 1

    def test_power_of_two_leaves(self):
        for n in [2, 4, 8, 16]:
            leaves = [f"sha256:{i:064x}" for i in range(n)]
            root = compute_merkle_root(leaves)
            assert root.startswith("sha256:")


class TestMerkleProof:

    def test_proof_for_leaf_in_tree(self):
        leaves = [f"sha256:{i:064x}" for i in range(8)]
        root = compute_merkle_root(leaves)
        proof = generate_merkle_proof(leaves, 3)
        assert verify_merkle_proof(leaves[3], proof, root) is True

    def test_proof_fails_for_wrong_leaf(self):
        leaves = [f"sha256:{i:064x}" for i in range(8)]
        root = compute_merkle_root(leaves)
        proof = generate_merkle_proof(leaves, 3)
        assert verify_merkle_proof("sha256:bogus", proof, root) is False

    def test_proof_for_each_leaf(self):
        leaves = [f"sha256:{i:064x}" for i in range(16)]
        root = compute_merkle_root(leaves)
        for i in range(len(leaves)):
            proof = generate_merkle_proof(leaves, i)
            assert verify_merkle_proof(leaves[i], proof, root) is True

    def test_proof_single_leaf(self):
        leaves = ["sha256:abc"]
        root = compute_merkle_root(leaves)
        proof = generate_merkle_proof(leaves, 0)
        assert verify_merkle_proof(leaves[0], proof, root) is True

    def test_proof_two_leaves(self):
        leaves = ["sha256:aaa", "sha256:bbb"]
        root = compute_merkle_root(leaves)
        for i in range(2):
            proof = generate_merkle_proof(leaves, i)
            assert verify_merkle_proof(leaves[i], proof, root) is True

    def test_proof_odd_count(self):
        leaves = [f"sha256:{i:064x}" for i in range(7)]
        root = compute_merkle_root(leaves)
        for i in range(len(leaves)):
            proof = generate_merkle_proof(leaves, i)
            assert verify_merkle_proof(leaves[i], proof, root) is True
