import hashlib
from dataclasses import dataclass, field

ZERO_HASH = "0" * 64


def compute_event_hash(event_type: str, executor_type: str, action: str, timestamp, data: dict | None) -> str:
    import json

    if hasattr(timestamp, "isoformat"):
        ts_str = timestamp.isoformat()
    else:
        ts_str = timestamp
        if isinstance(ts_str, str) and ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"

    payload = json.dumps(
        {
            "event_type": event_type,
            "executor_type": executor_type,
            "action": action,
            "timestamp": ts_str,
            "data": data,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_session_hash(events: list[dict]) -> str:
    import json

    sorted_events = sorted(events, key=lambda e: e["sequence_no"])
    concat = "".join(
        json.dumps(e["payload"], sort_keys=True) for e in sorted_events
    )
    return hashlib.sha256(concat.encode()).hexdigest()


def compute_leaf_hash(session_hash: str, prev_hash: str) -> str:
    return hashlib.sha256(f"{session_hash}{prev_hash}".encode()).hexdigest()


def _hash_leaf(entry: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + entry).digest()


def _hash_node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


@dataclass
class TreeNodeInfo:
    hash: str
    level: int
    position: int
    is_leaf: bool
    entry: str | None = None
    left_hash: str | None = None
    right_hash: str | None = None
    parent_hash: str | None = None
    entity_id: str | None = None


@dataclass
class MerkleTree:
    _entries: list[bytes] = field(default_factory=list)
    _levels: list[list[bytes]] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def root(self) -> str:
        if not self._levels:
            return ZERO_HASH
        return self._levels[-1][0].hex()

    def append(self, entry: bytes) -> None:
        self._entries.append(entry)
        self._build()

    def _build(self) -> None:
        if not self._entries:
            self._levels = []
            return

        current = [_hash_leaf(e) for e in self._entries]
        self._levels = [list(current)]

        while len(current) > 1:
            next_level: list[bytes] = []
            i = 0
            while i < len(current):
                if i + 1 < len(current):
                    next_level.append(_hash_node(current[i], current[i + 1]))
                    i += 2
                else:
                    next_level.append(current[i])
                    i += 1
            self._levels.append(next_level)
            current = next_level

    def get_proof(self, leaf_index: int) -> list[dict]:
        if leaf_index < 0 or leaf_index >= self.size:
            raise ValueError(f"Index {leaf_index} out of range [0, {self.size})")

        proof: list[dict] = []
        idx = leaf_index

        for level in range(len(self._levels) - 1):
            nodes = self._levels[level]
            if idx % 2 == 0:
                if idx + 1 < len(nodes):
                    proof.append(
                        {"hash": nodes[idx + 1].hex(), "direction": "right"}
                    )
            else:
                proof.append({"hash": nodes[idx - 1].hex(), "direction": "left"})
            idx //= 2

        return proof

    def get_node_infos(
        self, entity_ids: list[str] | None = None
    ) -> list[TreeNodeInfo]:
        nodes: list[TreeNodeInfo] = []

        for level_idx, level in enumerate(self._levels):
            for pos, node_hash_bytes in enumerate(level):
                is_leaf = level_idx == 0

                left_hash: str | None = None
                right_hash: str | None = None
                if level_idx > 0:
                    prev_level = self._levels[level_idx - 1]
                    left_idx = pos * 2
                    right_idx = pos * 2 + 1
                    if right_idx < len(prev_level):
                        left_hash = prev_level[left_idx].hex()
                        right_hash = prev_level[right_idx].hex()

                parent_hash: str | None = None
                if level_idx < len(self._levels) - 1:
                    next_level = self._levels[level_idx + 1]
                    parent_pos = pos // 2
                    if parent_pos < len(next_level):
                        parent_hash = next_level[parent_pos].hex()

                entry: str | None = None
                entity_id: str | None = None
                if is_leaf:
                    if pos < len(self._entries):
                        entry = self._entries[pos].decode()
                    if entity_ids and pos < len(entity_ids):
                        entity_id = entity_ids[pos]

                nodes.append(
                    TreeNodeInfo(
                        hash=node_hash_bytes.hex(),
                        level=level_idx,
                        position=pos,
                        is_leaf=is_leaf,
                        entry=entry,
                        left_hash=left_hash,
                        right_hash=right_hash,
                        parent_hash=parent_hash,
                        entity_id=entity_id,
                    )
                )

        return nodes


def build_tree(leaf_hashes: list[str]) -> MerkleTree:
    tree = MerkleTree()
    for h in leaf_hashes:
        tree.append(h.encode())
    return tree


def append_leaf(tree: MerkleTree, leaf_hash: str) -> MerkleTree:
    tree.append(leaf_hash.encode())
    return tree


def get_proof(tree: MerkleTree, leaf_index: int) -> list[dict]:
    return tree.get_proof(leaf_index)


def verify_proof(leaf_hash: str, proof_path: list[dict], hex_root: str) -> bool:
    current = _hash_leaf(leaf_hash.encode())
    for step in proof_path:
        sibling = bytes.fromhex(step["hash"])
        if step["direction"] == "left":
            current = _hash_node(sibling, current)
        else:
            current = _hash_node(current, sibling)
    return current.hex() == hex_root


def build_node_infos(
    tree: MerkleTree,
    entity_ids: list[str] | None = None,
) -> list[TreeNodeInfo]:
    return tree.get_node_infos(entity_ids)
