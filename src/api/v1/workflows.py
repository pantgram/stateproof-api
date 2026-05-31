import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.middleware.auth import Principal, get_api_key_principal, get_current_principal
from src.schemas.session import (
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionSubmitResponse,
)
from src.schemas.tree_node import (
    SessionTreeNodeListResponse,
    WorkflowTreeNodeListResponse,
)
from src.schemas.verify import (
    EventProofResponse,
    SessionProofResponse,
    VerifyWorkflowRequest,
    VerifyWorkflowResponse,
)
from src.schemas.workflow import WorkflowCreate, WorkflowListResponse, WorkflowResponse, WorkflowUpdate
from src.services import session_service, workflow_service

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.create_workflow(db, principal.organization_id, data)
    await db.commit()
    return wf


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    workflows, total = await workflow_service.list_workflows(
        db, principal.organization_id, offset, limit
    )
    return {"workflows": workflows, "total": total}


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.get_workflow(db, principal.organization_id, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.update_workflow(
        db, principal.organization_id, workflow_id, data
    )
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.commit()
    return wf


@router.post("/{workflow_id}/sessions", response_model=SessionSubmitResponse, status_code=201)
async def create_session(
    workflow_id: uuid.UUID,
    data: SessionCreate,
    principal: Principal = Depends(get_api_key_principal),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.get_workflow(db, principal.organization_id, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        sess, hex_root = await session_service.create_session(db, workflow_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    await db.refresh(sess)

    return {
        "id": sess.id,
        "workflow_id": sess.workflow_id,
        "session_hash": sess.session_hash,
        "hex_root": hex_root,
        "status": sess.status.value,
    }


@router.get("/{workflow_id}/sessions", response_model=SessionListResponse)
async def list_sessions(
    workflow_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.get_workflow(db, principal.organization_id, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    sessions, total = await session_service.list_sessions(
        db, workflow_id, offset, limit
    )
    return {"sessions": sessions, "total": total}


@router.get("/{workflow_id}/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    sess = await session_service.get_session(db, workflow_id, session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


@router.get("/{workflow_id}/sessions/{session_id}/proof", response_model=SessionProofResponse)
async def get_session_proof(
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    result = await session_service.get_session_proof(db, workflow_id, session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get(
    "/{workflow_id}/sessions/{session_id}/events/{sequence_no}/proof",
    response_model=EventProofResponse,
)
async def get_event_proof(
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    sequence_no: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    result = await session_service.get_event_proof(db, workflow_id, session_id, sequence_no)
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post("/{workflow_id}/verify", response_model=VerifyWorkflowResponse)
async def verify_workflow(
    workflow_id: uuid.UUID,
    data: VerifyWorkflowRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await session_service.verify_workflow_sessions(
            db, workflow_id, [s.model_dump() for s in data.sessions]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.get("/{workflow_id}/tree-nodes", response_model=WorkflowTreeNodeListResponse)
async def list_workflow_tree_nodes(
    workflow_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.get_workflow(db, principal.organization_id, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await session_service.list_workflow_tree_nodes(db, workflow_id, offset, limit)
    return {"workflow_tree_nodes": result[0], "total": result[1]}


@router.get(
    "/{workflow_id}/sessions/{session_id}/tree-nodes",
    response_model=SessionTreeNodeListResponse,
)
async def list_session_tree_nodes(
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.get_workflow(db, principal.organization_id, workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await session_service.list_session_tree_nodes(
        db, workflow_id, session_id, offset, limit
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_tree_nodes": result[0], "total": result[1]}
