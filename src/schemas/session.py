import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EventPayload(BaseModel):
    event_type: Literal[
        "tool_call", "decision", "approval", "api_call", "error", "trigger"
    ]
    executor_type: Literal[
        "agent", "rpa", "human", "integration", "job", "system"
    ]
    action: str
    timestamp: datetime
    data: dict | None = None


class Event(BaseModel):
    sequence_no: int = Field(ge=0)
    payload: EventPayload


class SessionCreate(BaseModel):
    events: list[Event] = Field(min_length=1)
    status: Literal["pending", "completed", "failed"] = "completed"


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
