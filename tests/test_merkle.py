import pytest

from src.services.merkle import (
    build_tree,
    compute_raw_event_hash,
    get_proof,
    verify_proof,
)


class TestComputeRawEventHash:
    def test_basic(self):
        h = compute_raw_event_hash(0, {"action": "test"})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        h1 = compute_raw_event_hash(1, {"action": "a"})
        h2 = compute_raw_event_hash(1, {"action": "a"})
        assert h1 == h2

    def test_different_payloads(self):
        h1 = compute_raw_event_hash(0, {"action": "a"})
        h2 = compute_raw_event_hash(0, {"action": "b"})
        assert h1 != h2

    def test_different_sequence_no(self):
        h1 = compute_raw_event_hash(0, {"action": "a"})
        h2 = compute_raw_event_hash(1, {"action": "a"})
        assert h1 != h2


class TestBuildTree:
    def test_single_leaf(self):
        tree = build_tree(["aa"])
        assert tree.size == 1
        assert tree.root != "0" * 64
        assert len(tree.root) == 64

    def test_two_leaves(self):
        tree = build_tree(["aa", "bb"])
        assert tree.size == 2
        root1 = tree.root
        tree = build_tree(["bb", "aa"])
        root2 = tree.root
        assert root1 != root2

    def test_three_leaves(self):
        tree = build_tree(["aa", "bb", "cc"])
        assert tree.size == 3

    def test_seven_leaves(self):
        leaves = [f"leaf_{i}" for i in range(7)]
        tree = build_tree(leaves)
        assert tree.size == 7

    def test_matches_pymerkle(self):
        from pymerkle import InmemoryTree

        leaves = ["aa", "bb", "cc", "dd", "ee"]
        tree = build_tree(leaves)
        pt = InmemoryTree()
        for leaf in leaves:
            pt.append_entry(leaf.encode())
        assert tree.root == pt.get_state().hex()


class TestProofs:
    @pytest.mark.parametrize("n_leaves", [1, 2, 3, 4, 5, 7, 8, 15])
    def test_verify_proof_all_leaves(self, n_leaves):
        leaves = [f"leaf_{i}" for i in range(n_leaves)]
        tree = build_tree(leaves)
        for i in range(n_leaves):
            proof = get_proof(tree, i)
            assert verify_proof(leaves[i], proof, tree.root)

    @pytest.mark.parametrize("n_leaves", [1, 2, 3, 5, 7])
    def test_wrong_leaf_fails(self, n_leaves):
        leaves = [f"leaf_{i}" for i in range(n_leaves)]
        tree = build_tree(leaves)
        proof = get_proof(tree, 0)
        assert not verify_proof("wrong_hash", proof, tree.root)

    def test_wrong_root_fails(self):
        tree = build_tree(["aa", "bb"])
        proof = get_proof(tree, 0)
        assert not verify_proof("aa", proof, "ff" * 32)

    def test_tampered_proof_fails(self):
        tree = build_tree(["aa", "bb", "cc"])
        proof = get_proof(tree, 1)
        tampered = [
            {"hash": "ff" * 32 if i == 0 else p["hash"], "direction": p["direction"]}
            for i, p in enumerate(proof)
        ]
        assert not verify_proof("bb", tampered, tree.root)
