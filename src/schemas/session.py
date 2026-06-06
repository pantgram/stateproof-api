import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.verify import ProofStep


class EventInput(BaseModel):
    payload: dict


class SessionCreate(BaseModel):
    events: list[EventInput] = Field(min_length=1)
    status: Literal["pending", "completed", "failed"] = "completed"
    started_at: datetime
    ended_at: datetime | None = None
    meta: dict | None = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    session_root: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    meta: dict | None = None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class SessionSubmitResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    session_root: str | None
    status: str


class SessionStart(BaseModel):
    started_at: datetime | None = None
    meta: dict | None = None


class EventAddRequest(BaseModel):
    events: list[EventInput] = Field(min_length=1)


class EventAddItem(BaseModel):
    sequence_no: int
    event_hash: str


class EventAddResponse(BaseModel):
    events: list[EventAddItem]


class SessionCloseRequest(BaseModel):
    status: Literal["completed", "failed"] = "completed"
    ended_at: datetime | None = None


class EventProofOut(BaseModel):
    sequence_no: int
    event_hash: str
    proof_path: list[ProofStep]


class SessionCloseResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    session_root: str
    status: str
    event_proofs: list[EventProofOut]
