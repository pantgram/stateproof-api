import uuid
from typing import Literal

from pydantic import BaseModel


class ProofStep(BaseModel):
    hash: str
    direction: Literal["left", "right"]


class EventProofResponse(BaseModel):
    session_id: uuid.UUID
    sequence_no: int
    data_hash: str
    event_hash: str
    proof_path: list[ProofStep]
    session_root: str


class EventProofRequest(BaseModel):
    sequence_no: int
    payload: dict


class StatelessVerifyRequest(BaseModel):
    leaf_hash: str
    proof_path: list[ProofStep]
    hex_root: str


class StatelessVerifyResponse(BaseModel):
    valid: bool
