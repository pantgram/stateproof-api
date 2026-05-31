import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EventInput(BaseModel):
    sequence_no: int = Field(ge=0)
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
    session_hash: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class SessionSubmitResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    session_hash: str
    hex_root: str
    status: str
