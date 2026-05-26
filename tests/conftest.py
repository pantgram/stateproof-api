import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.db.base import async_session_factory, engine
from src.main import app
from src.middleware.auth import Principal, get_api_key_principal, get_current_principal
from src.models.auth import Organization

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

test_principal = Principal(
    id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
    organization_id=ORG_ID,
    organization=Organization(id=ORG_ID, name="Test Org"),
)

app.dependency_overrides[get_current_principal] = lambda: test_principal
app.dependency_overrides[get_api_key_principal] = lambda: test_principal


@pytest_asyncio.fixture(autouse=True)
async def _ensure_org():
    async with async_session_factory() as db:
        result = await db.execute(select(Organization).where(Organization.id == ORG_ID))
        if result.scalar_one_or_none() is None:
            db.add(Organization(id=ORG_ID, name="Test Org"))
            await db.commit()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()
