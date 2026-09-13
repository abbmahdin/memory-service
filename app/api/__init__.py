from fastapi import APIRouter

from app.api.v1 import (
    agents,
    contexts,
    search,
    health,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(contexts.router, prefix="/contexts", tags=["contexts"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
