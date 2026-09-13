"""
Conftest for test setup: SQLite in-memory + fakeredis.
"""
import asyncio
import pytest
import pytest_asyncio
import fakeredis
import fakeredis.aioredis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import Base
from app.core.database import get_db


# ---- Override database for testing (SQLite in-memory) ----

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
async def db_engine():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# ---- Redis fixture (fakeredis) ----

@pytest.fixture
async def redis_mock():
    redis_client = fakeredis.aioredis.FakeRedis()
    yield redis_client
    await redis_client.flushall()


@pytest.fixture
def override_get_db(db_session):
    async def _override():
        yield db_session
    return _override


@pytest.fixture
def override_redis(redis_mock):
    async def _store(key, value, ttl=None):
        return await redis_mock.set(key, value, ex=ttl)

    async def _get(key):
        return await redis_mock.get(key)

    async def _delete(key):
        return await redis_mock.delete(key)

    async def _ping():
        await redis_mock.ping()
        return True

    return _store, _get, _delete, _ping
