"""
Tests for context store/retrieve/update/delete endpoints.
"""
import pytest
from httpx import AsyncClient
from app.main import app
from app.core.database import get_db


async def _yield_session(session):
    yield session


class TestContextCRUD:
    @pytest.mark.asyncio
    async def test_store_context(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create agent
            await client.post("/api/v1/agents/", json={"agent_id": "ctx-agent", "name": "ctx-test"})
            # Store context
            response = await client.post(
                "/api/v1/contexts/ctx-agent",
                json={
                    "key": "conversation_1",
                    "data": "Hello, this is context data.",
                    "ttl": 3600
                }
            )
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "conversation_1"
        assert data["data"] == "Hello, this is context data."
        assert data["ttl"] == 3600
        assert data["version"] == 1
        assert "context_id" in data
        assert "expires_at" in data


    @pytest.mark.asyncio
    async def test_store_context_without_ttl(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "no-ttl-agent", "name": "no-ttl"})
            response = await client.post(
                "/api/v1/contexts/no-ttl-agent",
                json={"key": "persistent_ctx", "data": "no expiry here"}
            )
        assert response.status_code == 201
        data = response.json()
        assert data["ttl"] is None
        assert data["expires_at"] is None


    @pytest.mark.asyncio
    async def test_get_context(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "get-ctx-agent", "name": "test"})
            store_resp = await client.post(
                "/api/v1/contexts/get-ctx-agent",
                json={"key": "retrievable_ctx", "data": "data to retrieve"}
            )
            ctx_id = store_resp.json()["context_id"]
            response = await client.get(f"/api/v1/contexts/get-ctx-agent/{ctx_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == "data to retrieve"
        assert data["key"] == "retrievable_ctx"


    @pytest.mark.asyncio
    async def test_get_nonexistent_context(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "notfound-agent", "name": "test"})
            response = await client.get("/api/v1/contexts/notfound-agent/does-not-exist")
        assert response.status_code == 404


    @pytest.mark.asyncio
    async def test_list_contexts(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "list-agent", "name": "test"})
            # Store 3 contexts
            for i in range(3):
                await client.post(
                    "/api/v1/contexts/list-agent",
                    json={"key": f"key_{i}", "data": f"value_{i}"}
                )
            response = await client.get("/api/v1/contexts/list-agent")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["contexts"]) == 3
        assert data["has_more"] is False


    @pytest.mark.asyncio
    async def test_update_context(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "update-agent", "name": "test"})
            # Store
            store_resp = await client.post(
                "/api/v1/contexts/update-agent",
                json={"key": "update_key", "data": "original data"}
            )
            ctx = store_resp.json()
            ctx_id = ctx["context_id"]
            version = ctx["version"]

            # Update
            response = await client.put(
                f"/api/v1/contexts/update-agent/{ctx_id}",
                json={
                    "data": "updated data",
                    "version": version
                }
            )
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == "updated data"
        assert data["version"] == version + 1


    @pytest.mark.asyncio
    async def test_update_context_optimistic_lock(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "optimistic-agent", "name": "test"})
            store_resp = await client.post(
                "/api/v1/contexts/optimistic-agent",
                json={"key": "opt_key", "data": "v1"}
            )
            ctx_id = store_resp.json()["context_id"]
            # Try to update with wrong version
            response = await client.put(
                f"/api/v1/contexts/optimistic-agent/{ctx_id}",
                json={"data": "v2", "version": 999}
            )
        assert response.status_code == 409


    @pytest.mark.asyncio
    async def test_delete_context(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "del-ctx-agent", "name": "test"})
            store_resp = await client.post(
                "/api/v1/contexts/del-ctx-agent",
                json={"key": "to_delete", "data": "bye"}
            )
            ctx_id = store_resp.json()["context_id"]
            response = await client.delete(f"/api/v1/contexts/del-ctx-agent/{ctx_id}")
            assert response.status_code == 204
            # Verify gone
            response = await client.get(f"/api/v1/contexts/del-ctx-agent/{ctx_id}")
            assert response.status_code == 404


    @pytest.mark.asyncio
    async def test_delete_all_agent_contexts(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "purge-agent", "name": "test"})
            await client.post("/api/v1/contexts/purge-agent", json={"key": "k1", "data": "v1"})
            await client.post("/api/v1/contexts/purge-agent", json={"key": "k2", "data": "v2"})
            response = await client.delete("/api/v1/contexts/purge-agent")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 2


    @pytest.mark.asyncio
    async def test_create_context_version(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "version-agent", "name": "test"})
            # Store base
            store_resp = await client.post(
                "/api/v1/contexts/version-agent",
                json={"key": "versioned_key", "data": "version 1 data"}
            )
            ctx_id = store_resp.json()["context_id"]

            # Create a new version
            response = await client.post(
                f"/api/v1/contexts/version-agent/{ctx_id}/version",
                json={"key": "versioned_key", "data": "version 2 data"}
            )
        assert response.status_code == 201
        data = response.json()
        assert data["version"] == 2
        assert data["data"] == "version 2 data"


    @pytest.mark.asyncio
    async def test_get_context_versions(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "versions-agent", "name": "test"})
            store_resp = await client.post(
                "/api/v1/contexts/versions-agent",
                json={"key": "multi_version", "data": "v1"}
            )
            ctx_id = store_resp.json()["context_id"]
            # Create 2 more versions
            await client.post(
                f"/api/v1/contexts/versions-agent/{ctx_id}/version",
                json={"key": "multi_version", "data": "v2"}
            )
            response = await client.get(f"/api/v1/contexts/versions-agent/{ctx_id}/versions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Latest version should be first
        assert data[0]["version"] == 2
        assert data[1]["version"] == 1
