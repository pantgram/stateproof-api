import hashlib
import json

import pytest
from httpx import AsyncClient

from src.services.merkle import ZERO_HASH, verify_proof


def _compute_event_hash(sequence_no: int, payload: dict) -> str:
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{sequence_no}{payload_str}".encode()).hexdigest()


def make_payload(i: int) -> dict:
    return {
        "action": f"step_{i}",
        "detail": f"event {i}",
    }


def make_events(n: int = 3) -> list[dict]:
    return [
        {"sequence_no": i, "payload": make_payload(i)}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_full_workflow(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Test Workflow"},
    )
    assert wf_resp.status_code == 201
    wf = wf_resp.json()
    wf_id = wf["id"]
    assert wf["hex_root"] == ZERO_HASH

    sess1_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={
            "events": make_events(3),
            "started_at": "2026-01-01T00:00:00Z",
        },
    )
    assert sess1_resp.status_code == 201
    s1 = sess1_resp.json()
    assert s1["hex_root"] != ZERO_HASH
    assert len(s1["session_hash"]) == 64
    root_after_1 = s1["hex_root"]

    sess2_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={
            "events": make_events(5),
            "started_at": "2026-01-01T00:01:00Z",
        },
    )
    assert sess2_resp.status_code == 201
    s2 = sess2_resp.json()
    root_after_2 = s2["hex_root"]
    assert root_after_2 != root_after_1

    sess3_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={
            "events": make_events(2),
            "started_at": "2026-01-01T00:02:00Z",
        },
    )
    assert sess3_resp.status_code == 201
    s3 = sess3_resp.json()

    wf_detail = await client.get(f"/api/v1/workflows/{wf_id}")
    assert wf_detail.status_code == 200
    wf_list = await client.get("/api/v1/workflows")
    assert wf_list.status_code == 200
    assert wf_list.json()["total"] >= 1

    sess_list = await client.get(f"/api/v1/workflows/{wf_id}/sessions")
    assert sess_list.status_code == 200
    assert sess_list.json()["total"] == 3

    sess_detail = await client.get(
        f"/api/v1/workflows/{wf_id}/sessions/{s1['id']}"
    )
    assert sess_detail.status_code == 200
    assert "session_hash" in sess_detail.json()

    proof_resp = await client.get(
        f"/api/v1/workflows/{wf_id}/sessions/{s2['id']}/proof"
    )
    assert proof_resp.status_code == 200
    proof = proof_resp.json()
    assert len(proof["leaf_hash"]) == 64
    assert proof["hex_root"] == s3["hex_root"]
    assert len(proof["proof_path"]) > 0

    assert verify_proof(
        proof["leaf_hash"], proof["proof_path"], proof["hex_root"]
    )

    event_proof_resp = await client.get(
        f"/api/v1/workflows/{wf_id}/sessions/{s1['id']}/events/0/proof"
    )
    assert event_proof_resp.status_code == 200
    event_proof = event_proof_resp.json()
    assert event_proof["sequence_no"] == 0
    assert len(event_proof["event_hash"]) == 64
    assert event_proof["session_hash"] == s1["session_hash"]
    assert len(event_proof["proof_path"]) > 0

    client_computed_hash = _compute_event_hash(0, make_payload(0))
    assert verify_proof(
        client_computed_hash, event_proof["proof_path"], event_proof["session_hash"]
    )

    verify_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/verify",
        json={
            "sessions": [
                {"session_id": s1["id"], "events": make_events(3)},
                {"session_id": s2["id"], "events": make_events(5)},
                {"session_id": s3["id"], "events": make_events(2)},
            ]
        },
    )
    assert verify_resp.status_code == 200
    vdata = verify_resp.json()
    assert vdata["all_valid"] is True
    assert all(r["valid"] for r in vdata["results"])

    verify_bad = await client.post(
        f"/api/v1/workflows/{wf_id}/verify",
        json={
            "sessions": [
                {
                    "session_id": s1["id"],
                    "events": [{"sequence_no": 0, "payload": {"wrong": "data"}}],
                }
            ]
        },
    )
    assert verify_bad.status_code == 200
    assert verify_bad.json()["all_valid"] is False

    stateless = await client.post(
        "/api/v1/verify",
        json={
            "leaf_hash": proof["leaf_hash"],
            "proof_path": proof["proof_path"],
            "hex_root": proof["hex_root"],
        },
    )
    assert stateless.status_code == 200
    assert stateless.json()["valid"] is True

    stateless_bad = await client.post(
        "/api/v1/verify",
        json={
            "leaf_hash": "ff" * 32,
            "proof_path": proof["proof_path"],
            "hex_root": proof["hex_root"],
        },
    )
    assert stateless_bad.status_code == 200
    assert stateless_bad.json()["valid"] is False


@pytest.mark.asyncio
async def test_verify_with_raw_events(client: AsyncClient):
    wf_resp = await client.post(
        "/api/v1/workflows",
        json={"name": "Verify Raw Events"},
    )
    assert wf_resp.status_code == 201
    wf_id = wf_resp.json()["id"]

    sess_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={
            "events": make_events(2),
            "started_at": "2026-01-01T00:00:00Z",
        },
    )
    assert sess_resp.status_code == 201
    s = sess_resp.json()

    verify_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/verify",
        json={
            "sessions": [
                {"session_id": s["id"], "events": make_events(2)},
            ]
        },
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["all_valid"] is True


@pytest.mark.asyncio
async def test_404s(client: AsyncClient):
    import uuid

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
