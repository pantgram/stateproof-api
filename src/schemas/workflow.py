import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    meta: dict | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    meta: dict | None = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None = None
    url: str | None = None
    created_at: datetime
    meta: dict | None = None


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse]
    total: int
