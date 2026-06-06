import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.middleware.auth import get_admin_user, get_current_user
from src.middleware.rate_limit import limiter
from src.models.auth import User
from src.schemas.auth import (
    ApproveResponse,
    ClientCreate,
    ClientListResponse,
    ClientResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    RefreshRequest,
    RefreshResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SignupResponse,
    TokenRequest,
    TokenResponse,
    UserLogin,
    UserMeResponse,
    UserSignup,
)
from src.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse, status_code=201)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    data: UserSignup,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await auth_service.signup_user(db, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await db.commit()
    return result


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.authenticate_user(db, data.email, data.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    tokens = await auth_service.create_user_tokens(db, user)
    await db.commit()
    return tokens


@router.post("/token", response_model=TokenResponse)
@limiter.limit("10/minute")
async def obtain_token(
    request: Request,
    data: TokenRequest,
    db: AsyncSession = Depends(get_db),
):
    client = await auth_service.authenticate_by_api_key(db, data.api_key)
    if client is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    tokens = await auth_service.create_client_tokens(db, client)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.refresh_user_token(db, data.refresh_token)
    if tokens is None:
        tokens = await auth_service.refresh_client_token(db, data.refresh_token)
    if tokens is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    await db.commit()
    return tokens


@router.post("/revoke", status_code=204)
async def revoke_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    revoked = await auth_service.revoke_user_refresh_token(db, data.refresh_token)
    if not revoked:
        revoked = await auth_service.revoke_client_refresh_token(db, data.refresh_token)
    if not revoked:
        raise HTTPException(status_code=404, detail="Refresh token not found")
    await db.commit()


@router.post("/approve/{token}", response_model=ApproveResponse)
async def approve_user(
    token: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.approve_user(
        db, token, organization_id=admin.organization_id
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Invalid or expired invite token")

    await db.commit()
    await db.refresh(user)
    return {
        "message": f"User {user.email} has been approved.",
        "user": user,
    }


@router.get("/clients", response_model=ClientListResponse)
async def list_clients(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    clients, total = await auth_service.list_clients(
        db, admin.organization_id, offset, limit
    )
    return {"clients": clients, "total": total}


@router.post("/clients", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    client = await auth_service.create_client(db, admin.organization_id, data)
    await db.commit()
    await db.refresh(client)
    return client


@router.delete("/clients/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await auth_service.delete_client(db, admin.organization_id, client_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.commit()


@router.post("/clients/{client_id}/rotate", response_model=ClientResponse)
async def rotate_client_key(
    client_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    client = await auth_service.rotate_client_key(db, admin.organization_id, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.commit()
    await db.refresh(client)
    return client


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    reset_token = await auth_service.request_password_reset(db, data.email)
    await db.commit()
    return {
        "message": "If the email exists, a reset token has been generated.",
        "reset_token": reset_token,
    }


@router.post("/reset-password", response_model=ResetPasswordResponse)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.reset_password(db, data.token, data.new_password)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    await db.commit()
    return {"message": "Password has been reset successfully."}


@router.get("/pending-invites")
async def list_pending_invites(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    invites = await auth_service.list_pending_invites(db, admin.organization_id)
    return {"invites": invites}
