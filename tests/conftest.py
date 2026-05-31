import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.db.session import get_db
from src.main import app
from src.middleware.auth import Principal, get_api_key_principal, get_current_principal
from src.middleware.config import settings
from src.middleware.rate_limit import limiter
from src.models import Base
from src.models.auth import Organization, User, UserRole, UserStatus
from src.models.base import WorkflowTreeNode, SessionTreeNode, Session, Workflow

TEST_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

test_engine = create_async_engine(settings.test_database_url, echo=False)
TestSessionFactory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_data():
    yield
    async with TestSessionFactory() as db:
        await db.execute(delete(WorkflowTreeNode))
        await db.execute(delete(SessionTreeNode))
        await db.execute(delete(Session))
        await db.execute(delete(Workflow))
        await db.execute(delete(User).where(User.id != TEST_USER_ID))
        await db.commit()
    limiter.reset()


@pytest_asyncio.fixture(autouse=True)
async def _ensure_seed():
    async with TestSessionFactory() as db:
        result = await db.execute(select(Organization).where(Organization.id == TEST_ORG_ID))
        if result.scalar_one_or_none() is None:
            db.add(Organization(id=TEST_ORG_ID, name="Test Org"))
        result = await db.execute(select(User).where(User.id == TEST_USER_ID))
        if result.scalar_one_or_none() is None:
            db.add(User(
                id=TEST_USER_ID,
                organization_id=TEST_ORG_ID,
                email="test@test.com",
                hashed_password="x",
                status=UserStatus.active,
                role=UserRole.admin,
            ))
        await db.commit()


test_principal = Principal(
    id=TEST_USER_ID,
    organization_id=TEST_ORG_ID,
    organization=Organization(id=TEST_ORG_ID, name="Test Org"),
)


def _override_principal():
    return test_principal


app.dependency_overrides[get_current_principal] = _override_principal
app.dependency_overrides[get_api_key_principal] = _override_principal


async def _get_test_db():
    async with TestSessionFactory() as session:
        yield session


app.dependency_overrides[get_db] = _get_test_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
