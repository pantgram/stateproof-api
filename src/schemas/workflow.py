import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkflowCreate(BaseModel):
    name: str
    meta: dict | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    meta: dict | None = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    hex_root: str
    created_at: datetime
    meta: dict | None = None


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse]
    total: int
