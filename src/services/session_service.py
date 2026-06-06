from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import Event, Session, SessionStatus
from src.schemas.session import EventAddRequest, SessionCreate, SessionStart
from src.services.merkle import (
    build_tree,
    compute_raw_event_hash,
)
from src.services.workflow_service import get_workflow_by_id_for_update


async def create_session(
    db: AsyncSession, workflow_id: uuid.UUID, data: SessionCreate
) -> Session:
    wf = await get_workflow_by_id_for_update(db, workflow_id)
    if wf is None:
        raise ValueError("Workflow not found")

    event_hashes = [
        compute_raw_event_hash(i, ev.payload)
        for i, ev in enumerate(data.events)
    ]

    session_tree = build_tree(event_hashes)

    status = SessionStatus(data.status) if data.status else SessionStatus.completed
    sess = Session(
        workflow_id=workflow_id,
        session_root=session_tree.root,
        event_count=len(data.events),
        status=status,
        started_at=data.started_at,
        ended_at=data.ended_at if data.ended_at else (
            datetime.now(timezone.utc) if status == SessionStatus.completed else None
        ),
        meta=data.meta,
    )
    db.add(sess)
    await db.flush()
    await db.refresh(sess)

    db.add_all([
        Event(
            session_id=sess.id,
            sequence_no=i,
            event_hash=event_hashes[i],
        )
        for i in range(len(data.events))
    ])

    await db.flush()
    return sess


async def start_session(
    db: AsyncSession, workflow_id: uuid.UUID, data: SessionStart
) -> Session:
    wf = await get_workflow_by_id_for_update(db, workflow_id)
    if wf is None:
        raise ValueError("Workflow not found")

    sess = Session(
        workflow_id=workflow_id,
        session_root=None,
        event_count=0,
        status=SessionStatus.pending,
        started_at=data.started_at if data.started_at else datetime.now(timezone.utc),
        meta=data.meta,
    )
    db.add(sess)
    await db.flush()
    await db.refresh(sess)
    return sess


async def add_events(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    data: EventAddRequest,
) -> list[Event]:
    sess = await get_session(db, workflow_id, session_id)
    if sess is None:
        raise ValueError("Session not found")
    if sess.status != SessionStatus.pending:
        raise ValueError("Session is not open")

    base_seq = sess.event_count
    new_events: list[Event] = []
    for i, ev in enumerate(data.events):
        seq_no = base_seq + i
        event_hash = compute_raw_event_hash(seq_no, ev.payload)
        event = Event(
            session_id=sess.id,
            sequence_no=seq_no,
            event_hash=event_hash,
        )
        new_events.append(event)

    db.add_all(new_events)
    sess.event_count = base_seq + len(data.events)
    await db.flush()
    for e in new_events:
        await db.refresh(e)
    return new_events


async def close_session(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    status: SessionStatus = SessionStatus.completed,
    ended_at: datetime | None = None,
) -> Session:
    sess = await get_session(db, workflow_id, session_id)
    if sess is None:
        raise ValueError("Session not found")
    if sess.status != SessionStatus.pending:
        raise ValueError("Session is not open")
    if sess.event_count == 0:
        raise ValueError("Cannot close an empty session")

    all_events_result = await db.execute(
        select(Event)
        .where(Event.session_id == session_id)
        .order_by(Event.sequence_no.asc())
    )
    all_events = list(all_events_result.scalars().all())

    tree = build_tree([e.event_hash for e in all_events])

    sess.session_root = tree.root
    sess.status = status
    sess.ended_at = ended_at if ended_at else datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(sess)
    return sess


def build_all_proofs(session_id: uuid.UUID, all_events: list[Event], tree) -> list[dict]:
    proofs = []
    for i, ev in enumerate(all_events):
        proof_path = tree.get_proof(i)
        proofs.append({
            "sequence_no": ev.sequence_no,
            "event_hash": ev.event_hash,
            "proof_path": proof_path,
        })
    return proofs


async def get_session(
    db: AsyncSession, workflow_id: uuid.UUID, session_id: uuid.UUID
) -> Session | None:
    result = await db.execute(
        select(Session).where(
            Session.id == session_id, Session.workflow_id == workflow_id
        )
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Session], int]:
    cond = Session.workflow_id == workflow_id
    total = (await db.execute(select(func.count()).select_from(Session).where(cond))).scalar_one()

    result = await db.execute(
        select(Session).where(cond).order_by(Session.started_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_event_proof(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    sequence_no: int,
    payload: dict,
) -> dict | None:
    sess = await get_session(db, workflow_id, session_id)
    if sess is None:
        return None

    computed_hash = compute_raw_event_hash(sequence_no, payload)

    result = await db.execute(
        select(Event).where(
            Event.session_id == session_id,
            Event.sequence_no == sequence_no,
        )
    )
    event = result.scalar_one_or_none()
    if event is None or event.event_hash != computed_hash:
        return None

    all_events_result = await db.execute(
        select(Event)
        .where(Event.session_id == session_id)
        .order_by(Event.sequence_no.asc())
    )
    all_events = list(all_events_result.scalars().all())

    tree = build_tree([e.event_hash for e in all_events])

    leaf_index = next(i for i, e in enumerate(all_events) if e.sequence_no == sequence_no)
    proof_path = tree.get_proof(leaf_index)

    return {
        "session_id": session_id,
        "sequence_no": sequence_no,
        "event_hash": event.event_hash,
        "proof_path": proof_path,
        "session_root": sess.session_root,
    }
