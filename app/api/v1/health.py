from fastapi import APIRouter
from app.schemas import HealthResponse
from app.services.memory_repository import MemoryRepository
from app.services.redis_service import redis_service
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from fastapi import Depends

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    repo = MemoryRepository(db)
    db_ok = await repo.health_check()
    redis_ok = await redis_service.ping()

    return HealthResponse(
        status="ok" if (db_ok and redis_ok) else "degraded",
        database="connected" if db_ok else "disconnected",
        redis="connected" if redis_ok else "disconnected",
    )
