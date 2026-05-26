import uuid

from pydantic import BaseModel, Field

from src.schemas.session import EventPayload


class EventCreate(BaseModel):
    sequence_no: int = Field(ge=0)
    payload: EventPayload


class EventResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    event_hash: str
    sequence_no: int

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int


class EventProofResponse(BaseModel):
    event_id: uuid.UUID
    leaf_hash: str
    proof_path: list[dict]
    hex_root: str
