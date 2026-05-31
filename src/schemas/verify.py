import uuid
from typing import Literal

from pydantic import BaseModel


class ProofStep(BaseModel):
    hash: str
    direction: Literal["left", "right"]


class SessionProofResponse(BaseModel):
    session_id: uuid.UUID
    leaf_hash: str
    proof_path: list[ProofStep]
    hex_root: str


class EventProofResponse(BaseModel):
    session_id: uuid.UUID
    sequence_no: int
    event_hash: str
    proof_path: list[ProofStep]
    session_hash: str


class VerifyEventRaw(BaseModel):
    sequence_no: int
    payload: dict


class VerifySessionItem(BaseModel):
    session_id: uuid.UUID
    events: list[VerifyEventRaw]


class VerifyWorkflowRequest(BaseModel):
    sessions: list[VerifySessionItem]


class SessionVerifyResult(BaseModel):
    session_id: uuid.UUID
    valid: bool
    reason: str | None = None


class VerifyWorkflowResponse(BaseModel):
    workflow_id: uuid.UUID
    hex_root: str
    results: list[SessionVerifyResult]
    all_valid: bool


class StatelessVerifyRequest(BaseModel):
    leaf_hash: str
    proof_path: list[ProofStep]
    hex_root: str


class StatelessVerifyResponse(BaseModel):
    valid: bool
