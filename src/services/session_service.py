from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import Session, SessionStatus, WorkflowTreeNode
from src.schemas.session import SessionCreate
from src.services.merkle import (
    ZERO_HASH,
    MerkleTree,
    build_node_infos,
    build_tree,
    compute_event_hash,
    compute_leaf_hash,
    get_proof,
    verify_proof,
)
from src.services.workflow_service import get_workflow_by_id, update_workflow_root


async def create_session(
    db: AsyncSession, workflow_id: uuid.UUID, data: SessionCreate
) -> tuple[Session, str]:
    wf = await get_workflow_by_id(db, workflow_id)
    if wf is None:
        raise ValueError("Workflow not found")

    status = SessionStatus(data.status) if data.status else SessionStatus.completed
    sess = Session(
        workflow_id=workflow_id,
        session_hash=ZERO_HASH,
        status=status,
        ended_at=datetime.now(timezone.utc) if status == SessionStatus.completed else None,
    )
    db.add(sess)
    await db.flush()
    await db.refresh(sess)

    from src.services.event_service import create_events_batch
    event_rows, event_tree_root = await create_events_batch(db, sess.id, data.events)
    await db.flush()
    await db.refresh(sess)

    cached_leaves: list[str] = wf.leaf_hashes or []
    prev_hash = cached_leaves[-1] if cached_leaves else ZERO_HASH
    leaf_hash = compute_leaf_hash(sess.session_hash, prev_hash)

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


async def _get_session_leaf_node(
    db: AsyncSession, session_id: uuid.UUID
) -> WorkflowTreeNode | None:
    result = await db.execute(
        select(WorkflowTreeNode).where(
            WorkflowTreeNode.session_id == session_id,
            WorkflowTreeNode.is_leaf.is_(True),
        )
    )
    return result.scalar_one_or_none()


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

    leaf_node = await _get_session_leaf_node(db, session_id)
    if leaf_node is None:
        return None

    leaf_hashes: list[str] = wf.leaf_hashes or []
    tree = build_tree(leaf_hashes)
    proof_path = get_proof(tree, leaf_node.position)

    return {
        "session_id": session_id,
        "leaf_hash": leaf_node.entry,
        "proof_path": proof_path,
        "hex_root": wf.hex_root,
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
    session_to_leaf = {ln.session_id: ln for ln in workflow_leaf_nodes}

    results = []
    for item in session_items:
        session_id = item["session_id"]
        raw_events = item.get("events", [])

        sess = await get_session(db, workflow_id, session_id)
        if sess is None:
            results.append(
                {"session_id": session_id, "valid": False, "reason": "Session not found"}
            )
            continue

        sorted_events = sorted(raw_events, key=lambda e: e.get("sequence_no", 0))
        evt_leaves: list[str] = []
        prev = ZERO_HASH
        for ev in sorted_events:
            p = ev.get("payload", {})
            event_hash = compute_event_hash(
                p.get("event_type", ""),
                p.get("executor_type", ""),
                p.get("action", ""),
                p.get("timestamp", ""),
                p.get("data"),
            )
            leaf = compute_leaf_hash(event_hash, prev)
            evt_leaves.append(leaf)
            prev = leaf

        evt_tree = build_tree(evt_leaves)
        if evt_tree.root != sess.session_hash:
            results.append(
                {
                    "session_id": session_id,
                    "valid": False,
                    "reason": "Session hash mismatch",
                }
            )
            continue

        leaf_node = session_to_leaf.get(sess.id)
        if leaf_node is None:
            results.append(
                {
                    "session_id": session_id,
                    "valid": False,
                    "reason": "Leaf not found in tree",
                }
            )
            continue

        if leaf_node.position == 0:
            expected_prev = ZERO_HASH
        else:
            prev_leaf_node = workflow_leaf_nodes[leaf_node.position - 1]
            expected_prev = prev_leaf_node.entry

        recomputed_leaf = compute_leaf_hash(sess.session_hash, expected_prev)
        if recomputed_leaf != leaf_node.entry:
            results.append(
                {
                    "session_id": session_id,
                    "valid": False,
                    "reason": "Leaf hash mismatch",
                }
            )
            continue

        proof_path = get_proof(tree, leaf_node.position)
        valid = verify_proof(leaf_node.entry, proof_path, wf.hex_root)

        results.append(
            {"session_id": session_id, "valid": valid, "reason": None}
        )

    all_valid = all(r["valid"] for r in results)
    return {
        "workflow_id": workflow_id,
        "hex_root": wf.hex_root,
        "results": results,
        "all_valid": all_valid,
    }


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
            entry=info.entry,
            left_hash=info.left_hash,
            right_hash=info.right_hash,
            parent_hash=info.parent_hash,
            level=info.level,
            position=info.position,
            is_leaf=info.is_leaf,
            session_id=uuid.UUID(info.entity_id) if info.entity_id else None,
        )
        for info in node_infos
    ])
