from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas import ContextCreate, ContextRead, ContextListResponse, ContextUpdate
from app.services.memory_repository import MemoryRepository
from app.services.redis_service import redis_service

router = APIRouter()


def _build_read_schema(ctx) -> ContextRead:
    return ContextRead(
        context_id=ctx.id,
        agent_id=ctx.agent_id,
        key=ctx.key,
        data=ctx.data.decode("utf-8", errors="replace") if isinstance(ctx.data, bytes) else ctx.data,
        version=ctx.version,
        ttl=ctx.ttl,
        metadata=None,
        expires_at=ctx.expires_at,
        created_at=ctx.created_at,
        updated_at=ctx.updated_at,
    )


@router.post("/{agent_id}", response_model=ContextRead, status_code=status.HTTP_201_CREATED)
async def store_context(
    agent_id: str,
    payload: ContextCreate,
    db: AsyncSession = Depends(get_db),
):
    """Store a context under an agent ID with optional TTL."""
    repo = MemoryRepository(db)
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    data_bytes = payload.data.encode("utf-8")

    ctx = await repo.create_context(
        agent_id=agent_id,
        key=payload.key,
        data=data_bytes,
        ttl=payload.ttl,
        context_id=payload.context_id,
    )

    # Cache in Redis if TTL set
    if payload.ttl and ctx.id:
        redis_key = f"context:{ctx.id}"
        await redis_service.store_context(redis_key, payload.data, ttl=payload.ttl)

    return _build_read_schema(ctx)


@router.get("/{agent_id}/{context_id}", response_model=ContextRead)
async def get_context(
    agent_id: str,
    context_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a context by agent ID and context ID."""
    repo = MemoryRepository(db)
    ctx = await repo.get_context(context_id)
    if not ctx or ctx.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Context not found")

    # Check expiry
    if ctx.expires_at and ctx.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=404, detail="Context expired")

    return _build_read_schema(ctx)


@router.get("/{agent_id}", response_model=ContextListResponse)
async def list_contexts(
    agent_id: str,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all non-expired contexts for an agent (paginated)."""
    repo = MemoryRepository(db)
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    contexts, total = await repo.list_contexts(agent_id, limit=limit, offset=offset)
    result = [_build_read_schema(c) for c in contexts]
    return ContextListResponse(
        contexts=result,
        total=total,
        has_more=offset + len(result) < total,
    )


@router.put("/{agent_id}/{context_id}", response_model=ContextRead)
async def update_context(
    agent_id: str,
    context_id: str,
    payload: ContextUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a context with optimistic locking via version."""
    repo = MemoryRepository(db)
    ctx = await repo.get_context(context_id)
    if not ctx or ctx.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Context not found")

    data_bytes = None
    if payload.data is not None:
        data_bytes = payload.data.encode("utf-8")

    try:
        updated = await repo.update_context(
            context_id=context_id,
            data=data_bytes,
            ttl=payload.ttl,
            expected_version=payload.version,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version mismatch",
        )

    if not updated:
        raise HTTPException(status_code=404, detail="Context not found")

    return _build_read_schema(updated)


@router.delete("/{agent_id}/{context_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_context(
    agent_id: str,
    context_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a single context."""
    repo = MemoryRepository(db)
    ctx = await repo.get_context(context_id)
    if not ctx or ctx.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Context not found")

    await repo.delete_context(context_id)
    await redis_service.delete_context(f"context:{context_id}")
    return None


@router.delete("/{agent_id}", response_model=dict)
async def delete_all_agent_contexts(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete ALL contexts for a given agent."""
    repo = MemoryRepository(db)
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    deleted = await repo.delete_all_agent_contexts(agent_id)
    return {"deleted": deleted}


@router.post("/{agent_id}/{context_id}/version", response_model=ContextRead)
async def create_context_version(
    agent_id: str,
    context_id: str,
    payload: ContextCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of an existing context (versioning)."""
    repo = MemoryRepository(db)
    base = await repo.get_context(context_id)
    if not base or base.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Base context not found")

    data_bytes = payload.data.encode("utf-8")
    new_ctx = await repo.create_context_version(
        agent_id=agent_id,
        key=payload.key,
        data=data_bytes,
        ttl=payload.ttl,
        base_context_id=context_id,
    )
    return _build_read_schema(new_ctx)


@router.get("/{agent_id}/{context_id}/versions", response_model=list[ContextRead])
async def get_context_versions(
    agent_id: str,
    context_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all versions of a context (by key lookup)."""
    repo = MemoryRepository(db)
    base = await repo.get_context(context_id)
    if not base or base.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Context not found")

    versions = await repo.get_all_versions(agent_id, base.key)
    return [_build_read_schema(v) for v in versions]
