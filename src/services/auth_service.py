from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt as _bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.middleware.config import settings
from src.models.auth import (
    Client,
    ClientRefreshToken,
    InviteToken,
    Organization,
    PasswordResetToken,
    User,
    UserRefreshToken,
    UserRole,
    UserStatus,
)
from src.schemas.auth import ClientCreate, UserSignup

def _generate_api_key() -> str:
    return f"sp_{secrets.token_hex(32)}"


def _generate_refresh_token_value() -> str:
    return secrets.token_urlsafe(64)


def _generate_invite_token_value() -> str:
    return secrets.token_urlsafe(48)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password[:72].encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain[:72].encode(), hashed.encode())


def create_access_token(
    sub: uuid.UUID, organization_id: uuid.UUID, token_type: str = "access"
) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_in = settings.access_token_expire_minutes * 60
    expire = now + timedelta(seconds=expires_in)
    payload = {
        "sub": str(sub),
        "organization_id": str(organization_id),
        "type": token_type,
        "iat": now,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


async def create_user_tokens(db: AsyncSession, user: User) -> dict:
    access_token, expires_in = create_access_token(user.id, user.organization_id)

    now = datetime.now(timezone.utc)
    refresh_value = _generate_refresh_token_value()
    refresh_expire = now + timedelta(days=settings.refresh_token_expire_days)

    rt = UserRefreshToken(
        user_id=user.id,
        token=refresh_value,
        expires_at=refresh_expire,
    )
    db.add(rt)
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": refresh_value,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


async def create_client_tokens(db: AsyncSession, client: Client) -> dict:
    access_token, expires_in = create_access_token(client.id, client.organization_id, "api_key")

    now = datetime.now(timezone.utc)
    refresh_value = _generate_refresh_token_value()
    refresh_expire = now + timedelta(days=settings.refresh_token_expire_days)

    rt = ClientRefreshToken(
        client_id=client.id,
        token=refresh_value,
        expires_at=refresh_expire,
    )
    db.add(rt)
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": refresh_value,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


async def signup_user(db: AsyncSession, data: UserSignup) -> dict:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none() is not None:
        raise ValueError("Email already registered")

    result = await db.execute(
        select(Organization).where(Organization.name == data.organization_name)
    )
    org = result.scalar_one_or_none()

    if org is None:
        org = Organization(name=data.organization_name)
        db.add(org)
        await db.flush()

        user = User(
            organization_id=org.id,
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            status=UserStatus.active,
            role=UserRole.admin,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        tokens = await create_user_tokens(db, user)
        return {
            "status": "active",
            "message": "Account created. You are now logged in.",
            **tokens,
        }

    user = User(
        organization_id=org.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        status=UserStatus.pending,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    await _create_invite_token(db, user.id, org.id)

    return {
        "status": "pending",
        "message": "Organization already exists. Your account is pending approval.",
        "access_token": None,
        "refresh_token": None,
        "token_type": "bearer",
        "expires_in": None,
    }


async def _create_invite_token(
    db: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID
) -> InviteToken:
    now = datetime.now(timezone.utc)
    invite = InviteToken(
        user_id=user_id,
        organization_id=organization_id,
        token=_generate_invite_token_value(),
        expires_at=now + timedelta(days=7),
    )
    db.add(invite)
    await db.flush()
    await db.refresh(invite)
    return invite


async def approve_user(db: AsyncSession, token: str, organization_id: uuid.UUID | None = None) -> User | None:
    result = await db.execute(
        select(InviteToken).where(InviteToken.token == token)
    )
    invite = result.scalar_one_or_none()

    if invite is None or invite.used:
        return None

    if organization_id is not None and invite.organization_id != organization_id:
        return None

    now = datetime.now(timezone.utc)
    if invite.expires_at < now:
        return None

    result = await db.execute(select(User).where(User.id == invite.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None

    user.status = UserStatus.active
    invite.used = True
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email, User.status == UserStatus.active)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def authenticate_by_api_key(
    db: AsyncSession, api_key: str
) -> Client | None:
    result = await db.execute(
        select(Client).where(Client.api_key == api_key, Client.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def refresh_user_token(
    db: AsyncSession, refresh_token_value: str
) -> dict | None:
    result = await db.execute(
        select(UserRefreshToken).where(UserRefreshToken.token == refresh_token_value)
    )
    rt = result.scalar_one_or_none()

    if rt is None or rt.revoked:
        return None

    now = datetime.now(timezone.utc)
    if rt.expires_at < now:
        return None

    result = await db.execute(select(User).where(User.id == rt.user_id))
    user = result.scalar_one_or_none()

    if user is None or user.status != UserStatus.active:
        return None

    rt.revoked = True
    tokens = await create_user_tokens(db, user)
    await db.flush()
    return tokens


async def refresh_client_token(
    db: AsyncSession, refresh_token_value: str
) -> dict | None:
    result = await db.execute(
        select(ClientRefreshToken).where(ClientRefreshToken.token == refresh_token_value)
    )
    rt = result.scalar_one_or_none()

    if rt is None or rt.revoked:
        return None

    now = datetime.now(timezone.utc)
    if rt.expires_at < now:
        return None

    result = await db.execute(select(Client).where(Client.id == rt.client_id))
    client = result.scalar_one_or_none()

    if client is None or not client.is_active:
        return None

    rt.revoked = True
    tokens = await create_client_tokens(db, client)
    await db.flush()
    return tokens


async def create_client(
    db: AsyncSession, organization_id: uuid.UUID, data: ClientCreate
) -> Client:
    client = Client(
        organization_id=organization_id,
        name=data.name,
        api_key=_generate_api_key(),
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


async def get_client(
    db: AsyncSession, organization_id: uuid.UUID, client_id: uuid.UUID
) -> Client | None:
    result = await db.execute(
        select(Client).where(
            Client.id == client_id, Client.organization_id == organization_id
        )
    )
    return result.scalar_one_or_none()


async def list_clients(
    db: AsyncSession, organization_id: uuid.UUID, offset: int = 0, limit: int = 50
) -> tuple[list[Client], int]:
    cond = Client.organization_id == organization_id
    total = (await db.execute(select(func.count()).select_from(Client).where(cond))).scalar_one()
    result = await db.execute(
        select(Client).where(cond).order_by(Client.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def delete_client(
    db: AsyncSession, organization_id: uuid.UUID, client_id: uuid.UUID
) -> bool:
    client = await get_client(db, organization_id, client_id)
    if client is None:
        return False
    await db.delete(client)
    await db.flush()
    return True


async def rotate_client_key(
    db: AsyncSession, organization_id: uuid.UUID, client_id: uuid.UUID
) -> Client | None:
    client = await get_client(db, organization_id, client_id)
    if client is None:
        return None
    client.api_key = _generate_api_key()
    await db.flush()
    await db.refresh(client)
    return client


async def revoke_user_refresh_token(
    db: AsyncSession, refresh_token_value: str
) -> bool:
    result = await db.execute(
        select(UserRefreshToken).where(UserRefreshToken.token == refresh_token_value)
    )
    rt = result.scalar_one_or_none()
    if rt is None:
        return False
    rt.revoked = True
    await db.flush()
    return True


async def revoke_client_refresh_token(
    db: AsyncSession, refresh_token_value: str
) -> bool:
    result = await db.execute(
        select(ClientRefreshToken).where(ClientRefreshToken.token == refresh_token_value)
    )
    rt = result.scalar_one_or_none()
    if rt is None:
        return False
    rt.revoked = True
    await db.flush()
    return True


async def list_pending_invites(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(InviteToken, User.email)
        .join(User, InviteToken.user_id == User.id)
        .where(
            InviteToken.organization_id == organization_id,
            InviteToken.used.is_(False),
            InviteToken.expires_at > now,
        )
    )
    rows = result.all()
    return [
        {
            "token": row.InviteToken.token,
            "email": row.email,
            "expires_at": row.InviteToken.expires_at.isoformat(),
            "approve_url": f"/api/v1/auth/approve/{row.InviteToken.token}",
        }
        for row in rows
    ]


async def request_password_reset(db: AsyncSession, email: str) -> str | None:
    result = await db.execute(
        select(User).where(User.email == email, User.status == UserStatus.active)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None

    now = datetime.now(timezone.utc)
    reset = PasswordResetToken(
        user_id=user.id,
        token=secrets.token_urlsafe(48),
        expires_at=now + timedelta(hours=settings.password_reset_token_expire_hours),
    )
    db.add(reset)
    await db.flush()
    await db.refresh(reset)
    return reset.token


async def reset_password(db: AsyncSession, token: str, new_password: str) -> User | None:
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == token)
    )
    reset = result.scalar_one_or_none()

    if reset is None or reset.used:
        return None

    now = datetime.now(timezone.utc)
    if reset.expires_at < now:
        return None

    result = await db.execute(select(User).where(User.id == reset.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None

    user.hashed_password = hash_password(new_password)
    reset.used = True

    result = await db.execute(
        select(UserRefreshToken).where(
            UserRefreshToken.user_id == user.id,
            UserRefreshToken.revoked.is_(False),
        )
    )
    for rt in result.scalars().all():
        rt.revoked = True

    await db.flush()
    await db.refresh(user)
    return user
