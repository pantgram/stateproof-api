from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.session import get_db
from src.middleware.config import settings
from src.models.auth import Client, Organization, User, UserRole, UserStatus

_bearer = HTTPBearer()


@dataclass
class Principal:
    id: uuid.UUID
    organization_id: uuid.UUID
    organization: Organization


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


async def _resolve_user(
    db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID
) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(
            User.id == user_id,
            User.organization_id == organization_id,
            User.status == UserStatus.active,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


async def _resolve_client(
    db: AsyncSession, client_id: uuid.UUID, organization_id: uuid.UUID
) -> Client:
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.organization))
        .where(
            Client.id == client_id,
            Client.organization_id == organization_id,
            Client.is_active.is_(True),
        )
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Client not found"
        )
    return client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = _decode_token(credentials.credentials)
    user_id = payload.get("sub")
    organization_id = payload.get("organization_id")
    if user_id is None or organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    return await _resolve_user(db, uuid.UUID(user_id), uuid.UUID(organization_id))


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    payload = _decode_token(credentials.credentials)
    sub = payload.get("sub")
    organization_id = payload.get("organization_id")
    if sub is None or organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    sub_uuid = uuid.UUID(sub)
    org_uuid = uuid.UUID(organization_id)

    if payload.get("type") == "api_key":
        client = await _resolve_client(db, sub_uuid, org_uuid)
        return Principal(
            id=client.id,
            organization_id=client.organization_id,
            organization=client.organization,
        )

    user = await _resolve_user(db, sub_uuid, org_uuid)
    return Principal(
        id=user.id, organization_id=user.organization_id, organization=user.organization
    )


async def get_api_key_principal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    payload = _decode_token(credentials.credentials)
    if payload.get("type") != "api_key":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key authentication required",
        )

    sub = payload.get("sub")
    organization_id = payload.get("organization_id")
    if sub is None or organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    client = await _resolve_client(db, uuid.UUID(sub), uuid.UUID(organization_id))
    return Principal(
        id=client.id,
        organization_id=client.organization_id,
        organization=client.organization,
    )


async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
