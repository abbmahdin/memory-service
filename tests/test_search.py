"""
Tests for semantic search and health endpoints.
"""
import pytest
from httpx import AsyncClient
from app.main import app
from app.core.database import get_db


async def _yield_session(session):
    yield session


class TestSearch:
    @pytest.mark.asyncio
    async def test_semantic_search_empty(self, db_session):
        """Search with no contexts returns empty results."""
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "search-agent", "name": "test"})
            # Store a context + embedding
            store_resp = await client.post(
                "/api/v1/contexts/search-agent",
                json={"key": "doc_1", "data": "Python is a programming language."}
            )
            ctx_id = store_resp.json()["context_id"]
            await client.post(
                f"/api/v1/search/embeddings/search-agent",
                json={
                    "context_id": ctx_id,
                    "text": "Python is a programming language.",
                    "embedding": [0.1] * 1536
                }
            )
            # Search
            response = await client.post(
                "/api/v1/search/",
                json={"agent_id": "search-agent", "query": "programming language", "limit": 5}
            )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "programming language"


    @pytest.mark.asyncio
    async def test_search_missing_fields(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/search/",
                json={"query": "missing agent_id"}
            )
        assert response.status_code == 400


    @pytest.mark.asyncio
    async def test_search_nonexistent_agent(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/search/",
                json={"agent_id": "ghost", "query": "nothing"}
            )
        assert response.status_code == 404


    @pytest.mark.asyncio
    async def test_store_embedding_missing_context(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            await client.post("/api/v1/agents/", json={"agent_id": "emb-agent", "name": "test"})
            response = await client.post(
                "/api/v1/search/embeddings/emb-agent",
                json={
                    "context_id": "nonexistent-ctx",
                    "text": "some text",
                    "embedding": [0.1] * 1536
                }
            )
        assert response.status_code == 404


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_check(self, db_session):
        app.dependency_overrides[get_db] = lambda: _yield_session(db_session)
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")
        assert "version" in data
