import pytest
from httpx import AsyncClient

from src.middleware.auth import _decode_token


@pytest.mark.asyncio
async def test_signup_new_org(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Fresh Corp",
            "email": "alice@fresh.com",
            "password": "secret123",
            "full_name": "Alice",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "active"
    assert data["access_token"] is not None
    assert data["refresh_token"] is not None
    assert "invite_link" not in data

    payload = _decode_token(data["access_token"])
    assert payload["type"] == "access"


@pytest.mark.asyncio
async def test_signup_existing_org(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Existing Corp",
            "email": "first@existing.com",
            "password": "secret123",
        },
    )

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Existing Corp",
            "email": "second@existing.com",
            "password": "secret456",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["access_token"] is None
    assert data["refresh_token"] is None


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Dup Corp",
            "email": "dup@dup.com",
            "password": "secret123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Dup Corp",
            "email": "dup@dup.com",
            "password": "secret456",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Login Corp",
            "email": "user@login.com",
            "password": "password123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@login.com", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Login Bad Corp",
            "email": "bad@login.com",
            "password": "password123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "bad@login.com", "password": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_exchange(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Token Corp",
            "email": "tok@token.com",
            "password": "secret123",
        },
    )
    access_token = signup_resp.json()["access_token"]
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "tok@token.com"
    assert me_resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_api_key_token_exchange(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "APIKey Corp",
            "email": "api@key.com",
            "password": "secret123",
        },
    )
    admin_token = signup_resp.json()["access_token"]

    client_resp = await client.post(
        "/api/v1/auth/clients",
        json={"name": "test-client"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert client_resp.status_code == 201
    api_key = client_resp.json()["api_key"]

    token_resp = await client.post(
        "/api/v1/auth/token",
        json={"api_key": api_key},
    )
    assert token_resp.status_code == 200
    data = token_resp.json()
    assert "access_token" in data
    payload = _decode_token(data["access_token"])
    assert payload["type"] == "api_key"


@pytest.mark.asyncio
async def test_api_key_invalid(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/token",
        json={"api_key": "sp_invalid_key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Refresh Corp",
            "email": "refresh@test.com",
            "password": "secret123",
        },
    )
    refresh = signup_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != refresh


@pytest.mark.asyncio
async def test_refresh_token_reuse(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Reuse Corp",
            "email": "reuse@test.com",
            "password": "secret123",
        },
    )
    refresh = signup_resp.json()["refresh_token"]

    await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_revoke_token(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Revoke Corp",
            "email": "revoke@test.com",
            "password": "secret123",
        },
    )
    refresh = signup_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/v1/auth/revoke",
        json={"refresh_token": refresh},
    )
    assert resp.status_code == 204

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_client_crud(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "CRUD Corp",
            "email": "crud@test.com",
            "password": "secret123",
        },
    )
    admin_token = signup_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_resp = await client.post(
        "/api/v1/auth/clients",
        json={"name": "my-client"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    client_id = create_resp.json()["id"]
    assert create_resp.json()["name"] == "my-client"

    list_resp = await client.get("/api/v1/auth/clients", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    rotate_resp = await client.post(
        f"/api/v1/auth/clients/{client_id}/rotate",
        headers=headers,
    )
    assert rotate_resp.status_code == 200
    new_key = rotate_resp.json()["api_key"]
    assert new_key != create_resp.json()["api_key"]

    delete_resp = await client.delete(
        f"/api/v1/auth/clients/{client_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_approve_flow(client: AsyncClient):
    admin_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Approve Corp",
            "email": "admin@approve.com",
            "password": "secret123",
        },
    )
    admin_token = admin_resp.json()["access_token"]

    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Approve Corp",
            "email": "pending@approve.com",
            "password": "secret123",
        },
    )

    headers = {"Authorization": f"Bearer {admin_token}"}
    invites_resp = await client.get(
        "/api/v1/auth/pending-invites",
        headers=headers,
    )
    assert invites_resp.status_code == 200
    invites = invites_resp.json()["invites"]
    assert len(invites) >= 1

    approve_resp = await client.post(
        f"/api/v1/auth/approve/{invites[0]['token']}",
        headers=headers,
    )
    assert approve_resp.status_code == 200
    assert "approved" in approve_resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_forgot_password_existing_email(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "Reset Corp",
            "email": "reset@test.com",
            "password": "oldpassword",
        },
    )

    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@test.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reset_token"] is not None
    assert "generated" in data["message"].lower()


@pytest.mark.asyncio
async def test_forgot_password_nonexistent_email(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@test.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reset_token"] is None


@pytest.mark.asyncio
async def test_reset_password_success(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "ResetPass Corp",
            "email": "resetpass@test.com",
            "password": "oldpassword",
        },
    )

    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "resetpass@test.com"},
    )
    reset_token = forgot_resp.json()["reset_token"]

    reset_resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpassword123"},
    )
    assert reset_resp.status_code == 200
    assert "reset" in reset_resp.json()["message"].lower()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "resetpass@test.com", "password": "newpassword123"},
    )
    assert login_resp.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "resetpass@test.com", "password": "oldpassword"},
    )
    assert old_login.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "invalid_token", "new_password": "newpassword123"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_revokes_refresh_tokens(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "RevokeReset Corp",
            "email": "revokereset@test.com",
            "password": "oldpassword",
        },
    )
    refresh_token = signup_resp.json()["refresh_token"]

    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "revokereset@test.com"},
    )
    reset_token = forgot_resp.json()["reset_token"]

    await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "newpassword123"},
    )

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_login_pending_user_rejected(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "PendingLogin Corp",
            "email": "admin@pendinglogin.com",
            "password": "secret123",
        },
    )
    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "PendingLogin Corp",
            "email": "pending@pendinglogin.com",
            "password": "secret123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "pending@pendinglogin.com", "password": "secret123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_cannot_create_client(client: AsyncClient):
    admin_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "NonAdminCreate Corp",
            "email": "admin@nonadmincreate.com",
            "password": "secret123",
        },
    )
    admin_token = admin_resp.json()["access_token"]

    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "NonAdminCreate Corp",
            "email": "member@nonadmincreate.com",
            "password": "secret123",
        },
    )

    invites_resp = await client.get(
        "/api/v1/auth/pending-invites",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    invites = invites_resp.json()["invites"]
    invite_token = invites[-1]["token"]

    await client.post(
        f"/api/v1/auth/approve/{invite_token}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    member_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "member@nonadmincreate.com", "password": "secret123"},
    )
    assert member_login.status_code == 200
    member_token = member_login.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/clients",
        json={"name": "unauthorized-client"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_list_clients(client: AsyncClient):
    admin_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "NonAdminList Corp",
            "email": "admin@nonadminlist.com",
            "password": "secret123",
        },
    )
    admin_token = admin_resp.json()["access_token"]

    await client.post(
        "/api/v1/auth/clients",
        json={"name": "test-client"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "NonAdminList Corp",
            "email": "member@nonadminlist.com",
            "password": "secret123",
        },
    )

    invites_resp = await client.get(
        "/api/v1/auth/pending-invites",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    invites = invites_resp.json()["invites"]
    invite_token = invites[-1]["token"]

    await client.post(
        f"/api/v1/auth/approve/{invite_token}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    member_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "member@nonadminlist.com", "password": "secret123"},
    )
    member_token = member_login.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/clients",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_with_full_name(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "FullName Corp",
            "email": "fullname@test.com",
            "password": "secret123",
            "full_name": "Test User",
        },
    )
    token = signup_resp.json()["access_token"]
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["email"] == "fullname@test.com"
    assert data["full_name"] == "Test User"
    assert data["role"] == "admin"
    assert "organization" in data
    assert data["organization"]["name"] == "FullName Corp"


@pytest.mark.asyncio
async def test_revoke_nonexistent_token(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/revoke",
        json={"refresh_token": "nonexistent_token_value"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_client(client: AsyncClient):
    import uuid

    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "DeleteNonexist Corp",
            "email": "delnone@test.com",
            "password": "secret123",
        },
    )
    admin_token = signup_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.delete(f"/api/v1/auth/clients/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rotate_nonexistent_client(client: AsyncClient):
    import uuid

    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "RotateNonexist Corp",
            "email": "rotatenone@test.com",
            "password": "secret123",
        },
    )
    admin_token = signup_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.post(
        f"/api/v1/auth/clients/{uuid.uuid4()}/rotate", headers=headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_invalid_token(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "BadApprove Corp",
            "email": "badapprove@test.com",
            "password": "secret123",
        },
    )
    admin_token = signup_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.post(
        "/api/v1/auth/approve/invalid_token_value",
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_key_refresh_cycle(client: AsyncClient):
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "organization_name": "APIKeyRefresh Corp",
            "email": "apirefresh@test.com",
            "password": "secret123",
        },
    )
    admin_token = signup_resp.json()["access_token"]

    client_resp = await client.post(
        "/api/v1/auth/clients",
        json={"name": "refresh-test-client"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    api_key = client_resp.json()["api_key"]

    token_resp = await client.post(
        "/api/v1/auth/token",
        json={"api_key": api_key},
    )
    assert token_resp.status_code == 200
    refresh = token_resp.json()["refresh_token"]

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()
    assert "refresh_token" in refresh_resp.json()

    reuse_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert reuse_resp.status_code == 401
