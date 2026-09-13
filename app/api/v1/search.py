from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas import (
    EmbeddingCreate,
    SearchResponse,
    SearchResult,
)
from app.services.memory_repository import MemoryRepository
import numpy as np

router = APIRouter()


def _get_query_embedding(text: str) -> list[float]:
    """Generate embedding for query text.

    Uses a simple hash-based approach if no embedding model is available.
    In production, replace with OpenAI/ Sentence-transformers embedding.
    """
    # Simple deterministic pseudo-embedding (for testing without a model server)
    # In production: call OpenAI embeddings API or use sentence-transformers
    np.random.seed(abs(hash(text)) % (2**32))
    embedding = np.random.uniform(-1, 1, settings.EMBEDDING_DIM).astype(float)
    # Normalize
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding.tolist()


@router.post("/", response_model=SearchResponse)
async def search_contexts(
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """Semantic search over contexts for a given agent.

    Body: {"agent_id": "...", "query": "...", "limit": 10}
    """
    agent_id = request.get("agent_id")
    query = request.get("query")
    limit = request.get("limit", 10)

    if not agent_id or not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agent_id and query are required",
        )

    repo = MemoryRepository(db)
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    query_embedding = _get_query_embedding(query)
    results = await repo.semantic_search(agent_id, query_embedding, limit=limit)

    response_results = []
    for ctx, score in results:
        response_results.append(
            SearchResult(
                context_id=ctx.id,
                key=ctx.key,
                data=ctx.data.decode("utf-8", errors="replace")
                if isinstance(ctx.data, bytes)
                else str(ctx.data),
                version=ctx.version,
                score=score,
                created_at=ctx.created_at,
            )
        )

    return SearchResponse(
        results=response_results,
        query=query,
        total=len(response_results),
    )


@router.post("/embeddings/{agent_id}", response_model=dict)
async def store_embedding(
    agent_id: str,
    payload: EmbeddingCreate,
    db: AsyncSession = Depends(get_db),
):
    """Store an embedding vector linked to a context."""
    repo = MemoryRepository(db)
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Verify context exists
    ctx = await repo.get_context(payload.context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")

    emb = await repo.store_embedding(
        agent_id=agent_id,
        context_id=payload.context_id,
        text=payload.text,
        embedding=payload.embedding,
    )
    return {"embedding_id": emb.id, "context_id": emb.context_id}
