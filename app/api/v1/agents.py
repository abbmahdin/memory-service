from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models import Agent
from app.schemas import AgentCreate, AgentRead
from app.services.memory_repository import MemoryRepository

router = APIRouter()


@router.post("/", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def register_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = MemoryRepository(db)
    existing = await repo.get_agent(payload.agent_id or "")
    # For registration, if agent_id provided, check uniqueness
    if payload.agent_id:
        existing = await repo.get_agent(payload.agent_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent ID already registered",
            )
    else:
        payload.agent_id = None  # will be generated below

    import secrets as _secrets

    agent_id = payload.agent_id or f"agent_{_secrets.token_hex(8)}"
    agent = await repo.create_agent(agent_id, payload.name)
    return AgentRead.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = MemoryRepository(db)
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return AgentRead.model_validate(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = MemoryRepository(db)
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    await repo.delete_all_agent_contexts(agent_id)
    await db.delete(agent)
    await db.commit()
    return None
