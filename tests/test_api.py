import hashlib
import json
import uuid

import pytest
from httpx import AsyncClient

from src.services.merkle import verify_proof


def _compute_data_hash(payload: dict) -> str:
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload_str.encode()).hexdigest()


def _compute_event_hash(session_id: str, sequence_no: int, payload: dict) -> str:
    data_hash = _compute_data_hash(payload)
    return hashlib.sha256(f"{data_hash}{sequence_no}{session_id}".encode()).hexdigest()


def make_payload(i: int) -> dict:
    return {
        "action": f"step_{i}",
        "detail": f"event {i}",
    }


def make_events(n: int = 3) -> list[dict]:
    return [{"payload": make_payload(i)} for i in range(n)]


@pytest.mark.asyncio
async def test_full_workflow(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Test Workflow"},
    )
    assert wf_resp.status_code == 201
    wf = wf_resp.json()
    wf_id = wf["id"]

    sess1_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={
            "events": make_events(3),
            "started_at": "2026-01-01T00:00:00Z",
        },
    )
    assert sess1_resp.status_code == 201
    s1 = sess1_resp.json()
    assert len(s1["session_root"]) == 64

    sess2_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={
            "events": make_events(5),
            "started_at": "2026-01-01T00:01:00Z",
        },
    )
    assert sess2_resp.status_code == 201

    sess3_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={
            "events": make_events(2),
            "started_at": "2026-01-01T00:02:00Z",
        },
    )
    assert sess3_resp.status_code == 201

    wf_detail = await client.get(f"/api/v1/workflows/{wf_id}")
    assert wf_detail.status_code == 200
    wf_list = await client.get("/api/v1/workflows")
    assert wf_list.status_code == 200
    assert wf_list.json()["total"] >= 1

    sess_list = await client.get(f"/api/v1/workflows/{wf_id}/sessions")
    assert sess_list.status_code == 200
    assert sess_list.json()["total"] == 3

    sess_detail = await client.get(f"/api/v1/workflows/{wf_id}/sessions/{s1['id']}")
    assert sess_detail.status_code == 200
    assert "session_root" in sess_detail.json()

    event_proof_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{s1['id']}/events/proof",
        json={"sequence_no": 0, "payload": make_payload(0)},
    )
    assert event_proof_resp.status_code == 200
    event_proof = event_proof_resp.json()
    assert event_proof["sequence_no"] == 0
    assert len(event_proof["data_hash"]) == 64
    assert len(event_proof["event_hash"]) == 64
    assert event_proof["session_root"] == s1["session_root"]
    assert len(event_proof["proof_path"]) > 0

    client_computed_hash = _compute_event_hash(s1["id"], 0, make_payload(0))
    assert verify_proof(
        client_computed_hash, event_proof["proof_path"], event_proof["session_root"]
    )


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_workflow_with_meta(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Meta Workflow", "meta": {"env": "test", "version": 1}},
    )
    assert wf_resp.status_code == 201
    wf = wf_resp.json()
    assert wf["meta"] == {"env": "test", "version": 1}

    detail = await client.get(f"/api/v1/workflows/{wf['id']}")
    assert detail.status_code == 200
    assert detail.json()["meta"] == {"env": "test", "version": 1}


@pytest.mark.asyncio
async def test_update_workflow(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Original"},
    )
    assert wf_resp.status_code == 201
    wf_id = wf_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/workflows/{wf_id}",
        json={"name": "Updated", "meta": {"key": "val"}},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["name"] == "Updated"
    assert patched["meta"] == {"key": "val"}

    detail = await client.get(f"/api/v1/workflows/{wf_id}")
    assert detail.json()["name"] == "Updated"
    assert detail.json()["meta"] == {"key": "val"}

    patch_name_only = await client.patch(
        f"/api/v1/workflows/{wf_id}",
        json={"name": "Name Only"},
    )
    assert patch_name_only.status_code == 200
    assert patch_name_only.json()["name"] == "Name Only"
    assert patch_name_only.json()["meta"] == {"key": "val"}


@pytest.mark.asyncio
async def test_update_workflow_404(client: AsyncClient):
    r = await client.patch(
        f"/api/v1/workflows/{uuid.uuid4()}",
        json={"name": "Nope"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_404s(client: AsyncClient):
    fake_id = str(uuid.uuid4())
    r = await client.get(f"/api/v1/workflows/{fake_id}")
    assert r.status_code == 404

    r = await client.post(
        f"/api/v1/workflows/{fake_id}/sessions",
        json={
            "events": make_events(1),
            "started_at": "2026-01-01T00:00:00Z",
        },
    )
    assert r.status_code == 404

    r = await client.get(f"/api/v1/workflows/{fake_id}/sessions/{uuid.uuid4()}")
    assert r.status_code == 404

    r = await client.post(
        f"/api/v1/workflows/{fake_id}/sessions/{uuid.uuid4()}/events/proof",
        json={"sequence_no": 0, "payload": {"x": 1}},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_event_proof_out_of_range(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Event 404 WF"},
    )
    wf_id = wf_resp.json()["id"]

    sess_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={"events": make_events(2), "started_at": "2026-01-01T00:00:00Z"},
    )
    sess_id = sess_resp.json()["id"]

    r = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events/proof",
        json={"sequence_no": 99, "payload": {"x": 1}},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_event_proof_wrong_payload(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Wrong Payload WF"},
    )
    wf_id = wf_resp.json()["id"]

    sess_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={"events": make_events(2), "started_at": "2026-01-01T00:00:00Z"},
    )
    sess_id = sess_resp.json()["id"]

    r = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events/proof",
        json={"sequence_no": 0, "payload": {"wrong": "data"}},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_incremental_session_full_flow(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Incremental WF"},
    )
    assert wf_resp.status_code == 201
    wf_id = wf_resp.json()["id"]

    start_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/start",
        json={},
    )
    assert start_resp.status_code == 201
    sess = start_resp.json()
    sess_id = sess["id"]
    assert sess["status"] == "pending"
    assert sess["session_root"] is None

    add1_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events",
        json={"events": [{"payload": make_payload(0)}, {"payload": make_payload(1)}]},
    )
    assert add1_resp.status_code == 200
    add1 = add1_resp.json()
    assert len(add1["events"]) == 2
    assert add1["events"][0]["sequence_no"] == 0
    assert add1["events"][1]["sequence_no"] == 1
    for ev in add1["events"]:
        assert len(ev["event_hash"]) == 64

    add2_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events",
        json={
            "events": [
                {"payload": make_payload(2)},
                {"payload": make_payload(3)},
                {"payload": make_payload(4)},
            ]
        },
    )
    assert add2_resp.status_code == 200
    add2 = add2_resp.json()
    assert len(add2["events"]) == 3
    assert add2["events"][0]["sequence_no"] == 2
    assert add2["events"][1]["sequence_no"] == 3
    assert add2["events"][2]["sequence_no"] == 4

    close_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/close",
        json={},
    )
    assert close_resp.status_code == 200
    closed = close_resp.json()
    assert closed["status"] == "completed"
    assert len(closed["session_root"]) == 64
    assert len(closed["event_proofs"]) == 5

    for i, ep in enumerate(closed["event_proofs"]):
        assert ep["sequence_no"] == i
        assert len(ep["data_hash"]) == 64
        assert len(ep["event_hash"]) == 64
        assert len(ep["proof_path"]) > 0
        client_hash = _compute_event_hash(sess_id, i, make_payload(i))
        assert ep["event_hash"] == client_hash
        assert verify_proof(client_hash, ep["proof_path"], closed["session_root"])

    detail_resp = await client.get(f"/api/v1/workflows/{wf_id}/sessions/{sess_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["session_root"] == closed["session_root"]
    assert detail_resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_incremental_session_cannot_add_to_closed(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Closed Add WF"},
    )
    wf_id = wf_resp.json()["id"]

    start_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/start",
        json={},
    )
    sess_id = start_resp.json()["id"]

    await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events",
        json={"events": [{"payload": {"x": 1}}]},
    )

    await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/close",
        json={},
    )

    r = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events",
        json={"events": [{"payload": {"y": 2}}]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_incremental_session_cannot_close_empty(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Empty Close WF"},
    )
    wf_id = wf_resp.json()["id"]

    start_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/start",
        json={},
    )
    sess_id = start_resp.json()["id"]

    r = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/close",
        json={},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_incremental_session_cannot_double_close(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Double Close WF"},
    )
    wf_id = wf_resp.json()["id"]

    start_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/start",
        json={},
    )
    sess_id = start_resp.json()["id"]

    await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events",
        json={"events": [{"payload": {"x": 1}}]},
    )

    r1 = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/close",
        json={},
    )
    assert r1.status_code == 200

    r2 = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/close",
        json={},
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_incremental_session_start_with_meta(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Meta Start WF"},
    )
    wf_id = wf_resp.json()["id"]

    start_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/start",
        json={"meta": {"source": "stream"}, "started_at": "2026-06-01T10:00:00Z"},
    )
    assert start_resp.status_code == 201
    sess = start_resp.json()
    assert sess["status"] == "pending"

    detail_resp = await client.get(f"/api/v1/workflows/{wf_id}/sessions/{sess['id']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["meta"] == {"source": "stream"}


@pytest.mark.asyncio
async def test_incremental_session_proofs_match_individual_proof(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Proof Match WF"},
    )
    wf_id = wf_resp.json()["id"]

    start_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/start",
        json={},
    )
    sess_id = start_resp.json()["id"]

    await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events",
        json={
            "events": [
                {"payload": make_payload(0)},
                {"payload": make_payload(1)},
                {"payload": make_payload(2)},
            ]
        },
    )

    close_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/close",
        json={},
    )
    closed = close_resp.json()

    for ep in closed["event_proofs"]:
        individual_resp = await client.post(
            f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events/proof",
            json={
                "sequence_no": ep["sequence_no"],
                "payload": make_payload(ep["sequence_no"]),
            },
        )
        assert individual_resp.status_code == 200
        individual = individual_resp.json()
        assert individual["proof_path"] == ep["proof_path"]
        assert individual["event_hash"] == ep["event_hash"]
        assert individual["session_root"] == closed["session_root"]


@pytest.mark.asyncio
async def test_incremental_session_close_with_failed_status(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Failed Status WF"},
    )
    wf_id = wf_resp.json()["id"]

    start_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/start",
        json={},
    )
    sess_id = start_resp.json()["id"]

    await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/events",
        json={"events": [{"payload": make_payload(0)}, {"payload": make_payload(1)}]},
    )

    close_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{sess_id}/close",
        json={"status": "failed"},
    )
    assert close_resp.status_code == 200
    closed = close_resp.json()
    assert closed["status"] == "failed"
    assert len(closed["session_root"]) == 64
    assert len(closed["event_proofs"]) == 2

    for ep in closed["event_proofs"]:
        client_hash = _compute_event_hash(
            sess_id, ep["sequence_no"], make_payload(ep["sequence_no"])
        )
        assert verify_proof(client_hash, ep["proof_path"], closed["session_root"])

    detail_resp = await client.get(f"/api/v1/workflows/{wf_id}/sessions/{sess_id}")
    assert detail_resp.json()["status"] == "failed"
