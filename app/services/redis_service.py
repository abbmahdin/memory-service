"""Redis service for TTL-based context caching."""
import json
from typing import Optional

import redis.asyncio as redis
from app.core.config import settings


class RedisService:
    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    @property
    def client(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._redis

    async def store_context(self, key: str, value: str, ttl: Optional[float] = None) -> bool:
        """Store a context blob in Redis with optional TTL."""
        try:
            await self.client.set(key, value, ex=ttl)
            return True
        except Exception:
            return False

    async def get_context(self, key: str) -> Optional[str]:
        """Retrieve a context blob from Redis cache."""
        try:
            return await self.client.get(key)
        except Exception:
            return None

    async def delete_context(self, key: str) -> bool:
        """Delete a context from Redis cache."""
        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception:
            return False

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            await self.client.ping()
            return True
        except Exception:
            return False


redis_service = RedisService()
