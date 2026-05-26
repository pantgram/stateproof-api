import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.db.base import engine
from src.main import app
from src.services.merkle import ZERO_HASH, verify_proof


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


def make_events(n: int = 3) -> list[dict]:
    return [
        {
            "sequence_no": i,
            "payload": {
                "event_type": "tool_call" if i % 2 == 0 else "decision",
                "executor_type": "agent" if i % 3 == 0 else "rpa",
                "action": f"step_{i}",
                "timestamp": f"2026-01-01T00:00:0{i}Z",
                "data": {"detail": f"event {i}"},
            },
        }
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
        json={"events": make_events(3)},
    )
    assert sess1_resp.status_code == 201
    s1 = sess1_resp.json()
    assert s1["hex_root"] != ZERO_HASH
    assert len(s1["session_hash"]) == 64
    root_after_1 = s1["hex_root"]

    sess2_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={"events": make_events(5)},
    )
    assert sess2_resp.status_code == 201
    s2 = sess2_resp.json()
    root_after_2 = s2["hex_root"]
    assert root_after_2 != root_after_1

    sess3_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions",
        json={"events": make_events(2)},
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

    events_list = await client.get(
        f"/api/v1/workflows/{wf_id}/sessions/{s1['id']}/events"
    )
    assert events_list.status_code == 200
    assert events_list.json()["total"] == 3
    assert len(events_list.json()["events"]) == 3

    first_event = events_list.json()["events"][0]
    event_detail = await client.get(
        f"/api/v1/workflows/{wf_id}/sessions/{s1['id']}/events/{first_event['id']}"
    )
    assert event_detail.status_code == 200
    assert event_detail.json()["event_hash"] == first_event["event_hash"]

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
        f"/api/v1/workflows/{wf_id}/sessions/{s1['id']}/events/{first_event['id']}/proof"
    )
    assert event_proof_resp.status_code == 200
    event_proof = event_proof_resp.json()
    assert len(event_proof["leaf_hash"]) == 64
    assert event_proof["hex_root"] == s1["session_hash"]
    assert len(event_proof["proof_path"]) > 0
    assert verify_proof(
        event_proof["leaf_hash"], event_proof["proof_path"], event_proof["hex_root"]
    )

    sess_verify_resp = await client.post(
        f"/api/v1/workflows/{wf_id}/sessions/{s1['id']}/verify",
        json={
            "events": [
                {
                    "event_id": first_event["id"],
                    "payload": {
                        "event_type": "tool_call",
                        "executor_type": "agent",
                        "action": "step_0",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "data": {"detail": "event 0"},
                    },
                }
            ]
        },
    )
    assert sess_verify_resp.status_code == 200
    assert sess_verify_resp.json()["all_valid"] is True

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
                    "events": [{"sequence_no": 0, "payload": {"event_type": "error", "executor_type": "system", "action": "bad", "timestamp": "2026-01-01T00:00:00Z"}}],
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
async def test_404s(client: AsyncClient):
    import uuid

    fake_id = str(uuid.uuid4())
    r = await client.get(f"/api/v1/workflows/{fake_id}")
    assert r.status_code == 404

    r = await client.post(
        f"/api/v1/workflows/{fake_id}/sessions",
        json={"events": make_events(1)},
    )
    assert r.status_code == 404
