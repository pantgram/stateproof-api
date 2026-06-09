import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.middleware.auth import Principal, get_api_key_principal, get_current_principal
from src.models.base import Event, SessionStatus
from src.schemas.session import (
    EventAddRequest,
    EventAddResponse,
    SessionBatchResponse,
    SessionCloseRequest,
    SessionCloseResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionStart,
    SessionSubmitResponse,
)
from src.schemas.verify import EventProofRequest, EventProofResponse
from src.schemas.workflow import (
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
)
from src.services import session_service, workflow_service
from src.services.merkle import build_tree

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


@router.post(
    "/{workflow_id}/sessions", response_model=SessionBatchResponse, status_code=201
)
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
        sess, event_hashes, tree = await session_service.create_session(db, workflow_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    proofs = [
        {
            "sequence_no": seq,
            "event_hash": eh,
            "proof_path": tree.get_proof(i),
        }
        for i, (seq, _, eh) in enumerate(event_hashes)
    ]

    await db.commit()
    await db.refresh(sess)

    return {
        "id": sess.id,
        "workflow_id": sess.workflow_id,
        "session_root": sess.session_root,
        "status": sess.status.value,
        "event_proofs": proofs,
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


@router.post(
    "/{workflow_id}/sessions/{session_id}/events/proof",
    response_model=EventProofResponse,
)
async def get_event_proof(
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    data: EventProofRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    result = await session_service.get_event_proof(
        db, workflow_id, session_id, data.sequence_no, data.payload
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post(
    "/{workflow_id}/sessions/start",
    response_model=SessionSubmitResponse,
    status_code=201,
)
async def start_session(
    workflow_id: uuid.UUID,
    data: SessionStart,
    principal: Principal = Depends(get_api_key_principal),
    db: AsyncSession = Depends(get_db),
):
    try:
        sess = await session_service.start_session(db, workflow_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    await db.refresh(sess)

    return {
        "id": sess.id,
        "workflow_id": sess.workflow_id,
        "session_root": sess.session_root,
        "status": sess.status.value,
    }


@router.post(
    "/{workflow_id}/sessions/{session_id}/events",
    response_model=EventAddResponse,
)
async def add_events(
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    data: EventAddRequest,
    principal: Principal = Depends(get_api_key_principal),
    db: AsyncSession = Depends(get_db),
):
    try:
        new_events = await session_service.add_events(db, workflow_id, session_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    return {
        "events": [
            {
                "sequence_no": e.sequence_no,
                "event_hash": e.event_hash,
            }
            for e in new_events
        ]
    }


@router.post(
    "/{workflow_id}/sessions/{session_id}/close",
    response_model=SessionCloseResponse,
)
async def close_session(
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    data: SessionCloseRequest,
    principal: Principal = Depends(get_api_key_principal),
    db: AsyncSession = Depends(get_db),
):
    try:
        sess = await session_service.close_session(
            db, workflow_id, session_id, SessionStatus(data.status), data.ended_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    all_events_result = await db.execute(
        select(Event)
        .where(Event.session_id == session_id)
        .order_by(Event.sequence_no.asc())
    )
    all_events = list(all_events_result.scalars().all())

    tree = build_tree([e.event_hash for e in all_events])
    proofs = session_service.build_all_proofs(session_id, all_events, tree)

    await db.commit()

    return {
        "id": sess.id,
        "workflow_id": sess.workflow_id,
        "session_root": sess.session_root,
        "status": sess.status.value,
        "event_proofs": proofs,
    }
