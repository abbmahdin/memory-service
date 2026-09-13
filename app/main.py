from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings

app = FastAPI(
    title="Memory-as-a-Service",
    description="Persistent context storage for AI agents — built on FastAPI, PostgreSQL, and Redis.",
    version="1.0.0",
    docs_url="/",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    from app.services.redis_service import redis_service
    from app.core.database import init_db

    await redis_service.connect()
    await init_db()


@app.on_event("shutdown")
async def shutdown():
    from app.services.redis_service import redis_service

    await redis_service.close()
