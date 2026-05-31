from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import Session, SessionStatus, SessionTreeNode, WorkflowTreeNode
from src.schemas.session import SessionCreate
from src.services.merkle import (
    ZERO_HASH,
    MerkleTree,
    build_node_infos,
    build_tree,
    compute_leaf_hash,
    compute_raw_event_hash,
    get_proof,
    verify_proof,
)
from src.services.workflow_service import get_workflow_by_id, get_workflow_by_id_for_update, update_workflow_root


async def create_session(
    db: AsyncSession, workflow_id: uuid.UUID, data: SessionCreate
) -> tuple[Session, str]:
    wf = await get_workflow_by_id_for_update(db, workflow_id)
    if wf is None:
        raise ValueError("Workflow not found")

    sorted_events = sorted(data.events, key=lambda e: e.sequence_no)

    event_hashes = [
        compute_raw_event_hash(e.sequence_no, e.payload) for e in sorted_events
    ]

    session_tree = build_tree(event_hashes)
    session_hash = session_tree.root

    cached_leaves: list[str] = wf.leaf_hashes or []
    prev_hash = cached_leaves[-1] if cached_leaves else ZERO_HASH
    leaf_hash = compute_leaf_hash(session_hash, prev_hash)

    status = SessionStatus(data.status) if data.status else SessionStatus.completed
    sess = Session(
        workflow_id=workflow_id,
        session_hash=session_hash,
        leaf_hash=leaf_hash,
        prev_hash=prev_hash,
        event_count=len(sorted_events),
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

    await _persist_session_tree_nodes(db, sess.id, session_tree, sorted_events)

    new_leaf_hashes = cached_leaves + [leaf_hash]
    new_leaf_session_ids = (wf.leaf_session_ids or []) + [str(sess.id)]

    tree = build_tree(new_leaf_hashes)
    await _persist_workflow_tree_nodes(db, workflow_id, tree, new_leaf_session_ids)

    await update_workflow_root(
        db,
        workflow_id,
        tree.root,
        leaf_hashes=new_leaf_hashes,
        leaf_session_ids=new_leaf_session_ids,
    )
    await db.flush()
    return sess, tree.root


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


async def get_session_proof(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
) -> dict | None:
    sess = await get_session(db, workflow_id, session_id)
    if sess is None:
        return None

    wf = await get_workflow_by_id(db, workflow_id)
    if wf is None:
        return None

    leaf_node = await _get_workflow_leaf_node(db, session_id)
    if leaf_node is None:
        return None

    leaf_hashes: list[str] = wf.leaf_hashes or []
    tree = build_tree(leaf_hashes)
    proof_path = get_proof(tree, leaf_node.position)

    return {
        "session_id": session_id,
        "leaf_hash": sess.leaf_hash,
        "proof_path": proof_path,
        "hex_root": wf.hex_root,
    }


async def get_event_proof(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    sequence_no: int,
) -> dict | None:
    sess = await get_session(db, workflow_id, session_id)
    if sess is None:
        return None

    result = await db.execute(
        select(SessionTreeNode).where(
            SessionTreeNode.session_id == session_id,
            SessionTreeNode.sequence_no == sequence_no,
            SessionTreeNode.is_leaf.is_(True),
        )
    )
    leaf_node = result.scalar_one_or_none()
    if leaf_node is None:
        return None

    proof_path: list[dict] = []
    current = leaf_node
    while current.parent_hash is not None:
        parent_result = await db.execute(
            select(SessionTreeNode).where(
                SessionTreeNode.session_id == session_id,
                SessionTreeNode.hash == current.parent_hash,
                SessionTreeNode.level == current.level + 1,
            )
        )
        parent = parent_result.scalar_one_or_none()
        if parent is None:
            break

        if parent.left_hash == current.hash:
            if parent.right_hash is not None:
                proof_path.append({"hash": parent.right_hash, "direction": "right"})
        elif parent.right_hash == current.hash:
            if parent.left_hash is not None:
                proof_path.append({"hash": parent.left_hash, "direction": "left"})

        current = parent

    return {
        "session_id": session_id,
        "sequence_no": sequence_no,
        "event_hash": leaf_node.hash,
        "proof_path": proof_path,
        "session_hash": sess.session_hash,
    }


async def verify_workflow_sessions(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    session_items: list[dict],
) -> dict:
    wf = await get_workflow_by_id(db, workflow_id)
    if wf is None:
        raise ValueError("Workflow not found")

    leaf_hashes: list[str] = wf.leaf_hashes or []
    tree = build_tree(leaf_hashes)

    leaf_nodes_result = await db.execute(
        select(WorkflowTreeNode).where(
            WorkflowTreeNode.workflow_id == workflow_id,
            WorkflowTreeNode.is_leaf.is_(True),
        ).order_by(WorkflowTreeNode.position.asc())
    )
    workflow_leaf_nodes = list(leaf_nodes_result.scalars().all())
    session_to_leaf: dict[uuid.UUID, WorkflowTreeNode] = {}
    for ln in workflow_leaf_nodes:
        if ln.session_id:
            session_to_leaf[ln.session_id] = ln

    results: list[dict] = []
    for item in session_items:
        session_id = uuid.UUID(item["session_id"]) if isinstance(item["session_id"], str) else item["session_id"]

        sess = await get_session(db, workflow_id, session_id)
        if sess is None:
            results.append(
                {"session_id": session_id, "valid": False, "reason": "Session not found"}
            )
            continue

        raw_events = item["events"]

        hashes: list[tuple[int, str]] = []
        for ev in raw_events:
            seq_no = ev["sequence_no"]
            payload = ev["payload"]
            h = compute_raw_event_hash(seq_no, payload)
            hashes.append((seq_no, h))

        hashes.sort(key=lambda x: x[0])
        hash_values = [h[1] for h in hashes]

        session_tree = build_tree(hash_values)
        computed_root = session_tree.root

        if computed_root != sess.session_hash:
            results.append({
                "session_id": session_id,
                "valid": False,
                "reason": "event log does not match stored session root",
            })
            continue

        leaf_node = session_to_leaf.get(sess.id)
        if leaf_node is None:
            results.append({
                "session_id": session_id,
                "valid": False,
                "reason": "session not in workflow tree",
            })
            continue

        proof_path = get_proof(tree, leaf_node.position)
        valid = verify_proof(sess.leaf_hash, proof_path, wf.hex_root)

        if not valid:
            results.append({
                "session_id": session_id,
                "valid": False,
                "reason": "session not in workflow tree",
            })
        else:
            results.append({"session_id": session_id, "valid": True, "reason": None})

    all_valid = all(r["valid"] for r in results)
    return {
        "workflow_id": workflow_id,
        "hex_root": wf.hex_root,
        "results": results,
        "all_valid": all_valid,
    }


async def list_session_tree_nodes(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    session_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[SessionTreeNode], int] | None:
    sess = await get_session(db, workflow_id, session_id)
    if sess is None:
        return None

    cond = SessionTreeNode.session_id == session_id
    total = (await db.execute(select(func.count()).select_from(SessionTreeNode).where(cond))).scalar_one()

    result = await db.execute(
        select(SessionTreeNode)
        .where(cond)
        .order_by(SessionTreeNode.level.asc(), SessionTreeNode.position.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def list_workflow_tree_nodes(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[WorkflowTreeNode], int] | None:
    wf = await get_workflow_by_id(db, workflow_id)
    if wf is None:
        return None

    cond = WorkflowTreeNode.workflow_id == workflow_id
    total = (await db.execute(select(func.count()).select_from(WorkflowTreeNode).where(cond))).scalar_one()

    result = await db.execute(
        select(WorkflowTreeNode)
        .where(cond)
        .order_by(WorkflowTreeNode.level.asc(), WorkflowTreeNode.position.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def _get_workflow_leaf_node(
    db: AsyncSession, session_id: uuid.UUID
) -> WorkflowTreeNode | None:
    result = await db.execute(
        select(WorkflowTreeNode).where(
            WorkflowTreeNode.session_id == session_id,
            WorkflowTreeNode.is_leaf.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _persist_session_tree_nodes(
    db: AsyncSession,
    session_id: uuid.UUID,
    tree: MerkleTree,
    events: list,
) -> None:
    await db.execute(
        delete(SessionTreeNode).where(SessionTreeNode.session_id == session_id)
    )

    node_infos = build_node_infos(tree)

    seq_map: dict[int, int] = {}
    for i, ev in enumerate(events):
        seq_map[i] = ev.sequence_no

    db.add_all([
        SessionTreeNode(
            session_id=session_id,
            hash=info.hash,
            left_hash=info.left_hash,
            right_hash=info.right_hash,
            parent_hash=info.parent_hash,
            level=info.level,
            position=info.position,
            is_leaf=info.is_leaf,
            sequence_no=seq_map.get(info.position) if info.is_leaf else None,
        )
        for info in node_infos
    ])


async def _persist_workflow_tree_nodes(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    tree: MerkleTree,
    session_ids: list[str],
) -> None:
    await db.execute(
        delete(WorkflowTreeNode).where(WorkflowTreeNode.workflow_id == workflow_id)
    )

    node_infos = build_node_infos(tree, entity_ids=session_ids)
    db.add_all([
        WorkflowTreeNode(
            workflow_id=workflow_id,
            hash=info.hash,
            left_hash=info.left_hash,
            right_hash=info.right_hash,
            parent_hash=info.parent_hash,
            level=info.level,
            position=info.position,
            is_leaf=info.is_leaf,
            session_id=uuid.UUID(info.entity_id) if info.entity_id and info.is_leaf else None,
        )
        for info in node_infos
    ])
