"""
Tests for agent management endpoints.
"""
import pytest
from httpx import AsyncClient
from app.main import app
from app.core.database import get_db
from app.services.redis_service import redis_service


class TestAgentRegistration:
    @pytest.mark.asyncio
    async def test_register_agent_auto_id(self, db_session, monkeypatch):
        """Register an agent without specifying ID — should auto-generate."""
        monkeypatch.setattr(get_db.__self__, "__wrapped__", lambda: db_session)
        # Override the dependency
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)

        # Mock redis
        monkeypatch.setattr(redis_service, "store_context", _fake_store)
        monkeypatch.setattr(redis_service, "delete_context", _fake_delete)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/",
                json={"name": "test-agent"}
            )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-agent"
        assert data["agent_id"].startswith("agent_")
        assert "created_at" in data


    @pytest.mark.asyncio
    async def test_register_agent_custom_id(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agents/",
                json={"agent_id": "my-agent-01", "name": "custom-agent"}
            )
        assert response.status_code == 201
        data = response.json()
        assert data["agent_id"] == "my-agent-01"
        assert data["name"] == "custom-agent"


    @pytest.mark.asyncio
    async def test_register_duplicate_agent(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "dup-agent", "name": "first"})
            response = await client.post(
                "/api/v1/agents/",
                json={"agent_id": "dup-agent", "name": "second"}
            )
        assert response.status_code == 409


    @pytest.mark.asyncio
    async def test_get_agent(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "get-agent", "name": "retrievable"})
            response = await client.get("/api/v1/agents/get-agent")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "get-agent"
        assert data["name"] == "retrievable"


    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/agents/nonexistent")
        assert response.status_code == 404


    @pytest.mark.asyncio
    async def test_delete_agent(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "delete-me", "name": "to-delete"})
            response = await client.delete("/api/v1/agents/delete-me")
            assert response.status_code == 204
            # Verify it's gone
            response = await client.get("/api/v1/agents/delete-me")
            assert response.status_code == 404


# ---- Helpers ----

async def _yield_session(session):
    yield session


async def _fake_store(key, value, ttl=None):
    return True


async def _fake_delete(key):
    return True
