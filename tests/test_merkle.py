import pytest

from src.services.merkle import (
    ZERO_HASH,
    append_leaf,
    build_node_infos,
    build_tree,
    compute_leaf_hash,
    compute_session_hash,
    get_proof,
    verify_proof,
)


class TestComputeSessionHash:
    def test_basic(self):
        events = [
            {"sequence_no": 2, "payload": {"action": "b"}},
            {"sequence_no": 1, "payload": {"action": "a"}},
            {"sequence_no": 3, "payload": {"action": "c"}},
        ]
        h = compute_session_hash(events)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_ordering_matters(self):
        e1 = [
            {"sequence_no": 1, "payload": {"action": "a"}},
            {"sequence_no": 2, "payload": {"action": "b"}},
        ]
        e2 = [
            {"sequence_no": 2, "payload": {"action": "b"}},
            {"sequence_no": 1, "payload": {"action": "a"}},
        ]
        assert compute_session_hash(e1) == compute_session_hash(e2)

    def test_different_payloads_different_hash(self):
        e1 = [{"sequence_no": 1, "payload": {"action": "a"}}]
        e2 = [{"sequence_no": 1, "payload": {"action": "b"}}]
        assert compute_session_hash(e1) != compute_session_hash(e2)


class TestComputeLeafHash:
    def test_basic(self):
        h = compute_leaf_hash("abc", "def")
        assert len(h) == 64

    def test_prev_hash_affects_result(self):
        h1 = compute_leaf_hash("abc", "000")
        h2 = compute_leaf_hash("abc", "111")
        assert h1 != h2

    def test_first_leaf(self):
        h = compute_leaf_hash("abc", ZERO_HASH)
        assert len(h) == 64


class TestBuildTree:
    def test_single_leaf(self):
        tree = build_tree(["aa"])
        assert tree.size == 1
        assert tree.root != ZERO_HASH
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


class TestAppendLeaf:
    def test_append(self):
        tree = build_tree(["aa"])
        root1 = tree.root
        tree = append_leaf(tree, "bb")
        root2 = tree.root
        assert tree.size == 2
        assert root1 != root2

    def test_append_multiple(self):
        tree = build_tree(["aa"])
        roots = [tree.root]
        for leaf in ["bb", "cc", "dd", "ee"]:
            tree = append_leaf(tree, leaf)
            roots.append(tree.root)
        assert len(set(roots)) == 5  # all different


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


class TestBuildNodeInfos:
    def test_basic(self):
        tree = build_tree(["aa", "bb", "cc"])
        nodes = build_node_infos(tree, entity_ids=["s1", "s2", "s3"])
        assert len(nodes) > 0

        leaf_nodes = [n for n in nodes if n.is_leaf]
        assert len(leaf_nodes) == 3

        for i, n in enumerate(leaf_nodes):
            assert n.entity_id == f"s{i + 1}"
            assert n.level == 0
            assert n.position == i
            assert n.parent_hash is not None
            assert n.entry is not None

        root_nodes = [n for n in nodes if n.parent_hash is None]
        assert len(root_nodes) == 1
        assert root_nodes[0].hash == tree.root

    def test_promoted_nodes_have_no_children(self):
        tree = build_tree(["aa", "bb", "cc"])
        nodes = build_node_infos(tree, entity_ids=["s1", "s2", "s3"])
        internal = [n for n in nodes if not n.is_leaf]
        promoted = [n for n in internal if n.left_hash is None and n.right_hash is None]
        assert len(promoted) >= 1  # cc is promoted at level 1
