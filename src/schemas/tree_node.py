import uuid

from pydantic import BaseModel


class SessionTreeNodeResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    hash: str
    left_hash: str | None = None
    right_hash: str | None = None
    parent_hash: str | None = None
    level: int
    position: int
    is_leaf: bool
    sequence_no: int | None = None

    model_config = {"from_attributes": True}


class WorkflowTreeNodeResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    hash: str
    left_hash: str | None = None
    right_hash: str | None = None
    parent_hash: str | None = None
    level: int
    position: int
    is_leaf: bool
    session_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class SessionTreeNodeListResponse(BaseModel):
    session_tree_nodes: list[SessionTreeNodeResponse]
    total: int


class WorkflowTreeNodeListResponse(BaseModel):
    workflow_tree_nodes: list[WorkflowTreeNodeResponse]
    total: int
