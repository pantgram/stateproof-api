import hashlib
import json
from dataclasses import dataclass, field

ZERO_HASH = "0" * 64


def compute_raw_event_hash(sequence_no: int, payload: dict) -> str:
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{sequence_no}{payload_str}".encode()).hexdigest()


def _hash_leaf(entry: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + entry).digest()


def _hash_node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


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

    def extend(self, entries: list[bytes]) -> None:
        self._entries.extend(entries)
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


def build_tree(leaf_hashes: list[str]) -> MerkleTree:
    tree = MerkleTree()
    if leaf_hashes:
        tree.extend([h.encode() for h in leaf_hashes])
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
