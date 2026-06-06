import uuid

import pytest

from src.services.merkle import (
    build_tree,
    compute_data_hash,
    compute_raw_event_hash,
    get_proof,
    verify_proof,
)


class TestComputeDataHash:
    def test_basic(self):
        h = compute_data_hash({"action": "test"})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        h1 = compute_data_hash({"action": "a"})
        h2 = compute_data_hash({"action": "a"})
        assert h1 == h2

    def test_different_payloads(self):
        h1 = compute_data_hash({"action": "a"})
        h2 = compute_data_hash({"action": "b"})
        assert h1 != h2

    def test_same_payload_across_sequence_nos(self):
        payload = {"action": "same"}
        h1 = compute_data_hash(payload)
        h2 = compute_data_hash(payload)
        assert h1 == h2


class TestComputeRawEventHash:
    def test_basic(self):
        sid = uuid.uuid4()
        data_hash, event_hash = compute_raw_event_hash(sid, 0, {"action": "test"})
        assert len(data_hash) == 64
        assert len(event_hash) == 64
        assert all(c in "0123456789abcdef" for c in event_hash)

    def test_deterministic(self):
        sid = uuid.uuid4()
        dh1, eh1 = compute_raw_event_hash(sid, 1, {"action": "a"})
        dh2, eh2 = compute_raw_event_hash(sid, 1, {"action": "a"})
        assert dh1 == dh2
        assert eh1 == eh2

    def test_different_payloads(self):
        sid = uuid.uuid4()
        _, eh1 = compute_raw_event_hash(sid, 0, {"action": "a"})
        _, eh2 = compute_raw_event_hash(sid, 0, {"action": "b"})
        assert eh1 != eh2

    def test_different_sequence_no(self):
        sid = uuid.uuid4()
        dh1, eh1 = compute_raw_event_hash(sid, 0, {"action": "a"})
        dh2, eh2 = compute_raw_event_hash(sid, 1, {"action": "a"})
        assert dh1 == dh2
        assert eh1 != eh2

    def test_different_session_id(self):
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        _, eh1 = compute_raw_event_hash(sid1, 0, {"action": "a"})
        _, eh2 = compute_raw_event_hash(sid2, 0, {"action": "a"})
        assert eh1 != eh2

    def test_data_hash_matches_compute_data_hash(self):
        sid = uuid.uuid4()
        data_hash, _ = compute_raw_event_hash(sid, 0, {"action": "test"})
        assert data_hash == compute_data_hash({"action": "test"})


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
