from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.base import Event, SessionTreeNode, Session
from src.schemas.session import Event as EventSchema
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


async def _rebuild_event_leaf_entries(db: AsyncSession, session_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(SessionTreeNode.entry)
        .where(
            SessionTreeNode.session_id == session_id,
            SessionTreeNode.is_leaf.is_(True),
        )
        .order_by(SessionTreeNode.position.asc())
    )
    return list(result.scalars().all())


async def _get_event_leaf_node(
    db: AsyncSession, event_id: uuid.UUID
) -> SessionTreeNode | None:
    result = await db.execute(
        select(SessionTreeNode).where(
            SessionTreeNode.event_id == event_id,
            SessionTreeNode.is_leaf.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _persist_event_tree_nodes(
    db: AsyncSession,
    session_id: uuid.UUID,
    tree: MerkleTree,
    event_ids: list[str],
) -> None:
    await db.execute(
        delete(SessionTreeNode).where(SessionTreeNode.session_id == session_id)
    )

    node_infos = build_node_infos(tree, entity_ids=event_ids)
    db.add_all([
        SessionTreeNode(
            session_id=session_id,
            hash=info.hash,
            entry=info.entry,
            left_hash=info.left_hash,
            right_hash=info.right_hash,
            parent_hash=info.parent_hash,
            level=info.level,
            position=info.position,
            is_leaf=info.is_leaf,
            event_id=uuid.UUID(info.entity_id) if info.entity_id else None,
        )
        for info in node_infos
    ])


async def create_events_batch(
    db: AsyncSession, session_id: uuid.UUID, events: list[EventSchema]
) -> tuple[list[Event], str]:
    sorted_events = sorted(events, key=lambda e: e.sequence_no)

    event_rows: list[Event] = []
    leaf_hashes: list[str] = []
    prev_hash = ZERO_HASH

    for ev in sorted_events:
        ts_str = ev.payload.timestamp.isoformat()
        event_hash = compute_event_hash(
            ev.payload.event_type,
            ev.payload.executor_type,
            ev.payload.action,
            ts_str,
            ev.payload.data,
        )
        leaf_hash = compute_leaf_hash(event_hash, prev_hash)

        row = Event(
            session_id=session_id,
            event_hash=event_hash,
            sequence_no=ev.sequence_no,
        )
        event_rows.append(row)
        leaf_hashes.append(leaf_hash)
        prev_hash = leaf_hash

    db.add_all(event_rows)
    await db.flush()

    for row in event_rows:
        await db.refresh(row)

    tree = build_tree(leaf_hashes)

    await _persist_event_tree_nodes(
        db, session_id, tree, [str(e.id) for e in event_rows]
    )

    await _update_session_hash(db, session_id, tree.root)

    return event_rows, tree.root


async def get_event(
    db: AsyncSession, session_id: uuid.UUID, event_id: uuid.UUID
) -> Event | None:
    result = await db.execute(
        select(Event).where(
            Event.id == event_id, Event.session_id == session_id
        )
    )
    return result.scalar_one_or_none()


async def list_events(
    db: AsyncSession,
    session_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Event], int]:
    cond = Event.session_id == session_id
    total = (await db.execute(select(func.count()).select_from(Event).where(cond))).scalar_one()

    result = await db.execute(
        select(Event).where(cond).order_by(Event.sequence_no.asc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def get_event_proof(
    db: AsyncSession,
    session_id: uuid.UUID,
    event_id: uuid.UUID,
) -> dict | None:
    evt = await get_event(db, session_id, event_id)
    if evt is None:
        return None

    sess_result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    sess = sess_result.scalar_one_or_none()
    if sess is None:
        return None

    leaf_node = await _get_event_leaf_node(db, event_id)
    if leaf_node is None:
        return None

    leaf_entries = await _rebuild_event_leaf_entries(db, session_id)
    tree = build_tree(leaf_entries)
    proof_path = get_proof(tree, leaf_node.position)

    return {
        "event_id": event_id,
        "leaf_hash": leaf_node.entry,
        "proof_path": proof_path,
        "hex_root": sess.session_hash,
    }


async def verify_session_events(
    db: AsyncSession,
    session_id: uuid.UUID,
    event_items: list[dict],
) -> dict:
    sess_result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    sess = sess_result.scalar_one_or_none()
    if sess is None:
        raise ValueError("Session not found")

    leaf_entries = await _rebuild_event_leaf_entries(db, session_id)
    tree = build_tree(leaf_entries)

    leaf_nodes_result = await db.execute(
        select(SessionTreeNode)
        .where(
            SessionTreeNode.session_id == session_id,
            SessionTreeNode.is_leaf.is_(True),
        )
        .order_by(SessionTreeNode.position.asc())
    )
    leaf_nodes = list(leaf_nodes_result.scalars().all())
    event_to_leaf = {ln.event_id: ln for ln in leaf_nodes}

    results = []
    for item in event_items:
        event_id = item["event_id"]
        payload = item["payload"]

        evt = await get_event(db, session_id, event_id)
        if evt is None:
            results.append(
                {"event_id": event_id, "valid": False, "reason": "Event not found"}
            )
            continue

        recomputed_hash = compute_event_hash(
            payload.get("event_type", ""),
            payload.get("executor_type", ""),
            payload.get("action", ""),
            payload.get("timestamp", ""),
            payload.get("data"),
        )
        if recomputed_hash != evt.event_hash:
            results.append(
                {"event_id": event_id, "valid": False, "reason": "Event hash mismatch"}
            )
            continue

        leaf_node = event_to_leaf.get(evt.id)
        if leaf_node is None:
            results.append(
                {"event_id": event_id, "valid": False, "reason": "Leaf not found in tree"}
            )
            continue

        if leaf_node.position == 0:
            prev = ZERO_HASH
        else:
            prev = leaf_entries[leaf_node.position - 1]

        recomputed_leaf = compute_leaf_hash(evt.event_hash, prev)
        if recomputed_leaf != leaf_node.entry:
            results.append(
                {"event_id": event_id, "valid": False, "reason": "Leaf hash mismatch"}
            )
            continue

        try:
            leaf_index = leaf_entries.index(leaf_node.entry)
        except ValueError:
            results.append(
                {"event_id": event_id, "valid": False, "reason": "Leaf not found in tree"}
            )
            continue

        proof_path = get_proof(tree, leaf_index)
        valid = verify_proof(leaf_node.entry, proof_path, sess.session_hash)

        results.append({"event_id": event_id, "valid": valid, "reason": None})

    all_valid = all(r["valid"] for r in results)
    return {
        "session_id": session_id,
        "hex_root": sess.session_hash,
        "results": results,
        "all_valid": all_valid,
    }


async def _update_session_hash(
    db: AsyncSession,
    session_id: uuid.UUID,
    hex_root: str,
) -> None:
    await db.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(session_hash=hex_root)
    )
