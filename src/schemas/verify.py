import uuid

from pydantic import BaseModel



class ProofStep(BaseModel):
    hash: str
    direction: str


class SessionProofResponse(BaseModel):
    session_id: uuid.UUID
    leaf_hash: str
    proof_path: list[ProofStep]
    hex_root: str


class VerifySessionItem(BaseModel):
    session_id: uuid.UUID
    events: list[dict]


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


class EventProofResponse(BaseModel):
    event_id: uuid.UUID
    leaf_hash: str
    proof_path: list[ProofStep]
    hex_root: str


class VerifyEventItem(BaseModel):
    event_id: uuid.UUID
    payload: dict


class VerifySessionRequest(BaseModel):
    events: list[VerifyEventItem]


class EventVerifyResult(BaseModel):
    event_id: uuid.UUID
    valid: bool
    reason: str | None = None


class VerifySessionResponse(BaseModel):
    session_id: uuid.UUID
    hex_root: str
    results: list[EventVerifyResult]
    all_valid: bool
