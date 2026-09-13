from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class AgentCreate(AgentBase):
    agent_id: Optional[str] = None


class AgentRead(AgentBase):
    agent_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContextBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=512)
    data: str = Field(..., min_length=1)
    ttl: Optional[float] = Field(default=None, description="TTL in seconds; null = no expiry")
    metadata: Optional[dict] = Field(default=None)


class ContextCreate(ContextBase):
    context_id: Optional[str] = None  # If provided, creates a new version; else random UUID


class ContextUpdate(BaseModel):
    data: Optional[str] = None
    ttl: Optional[float] = None
    metadata: Optional[dict] = None
    version: Optional[int] = None  # optimistic locking


class ContextRead(ContextBase):
    context_id: str
    agent_id: str
    version: int
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ContextListResponse(BaseModel):
    contexts: list[ContextRead]
    total: int
    has_more: bool


class SearchResult(BaseModel):
    context_id: str
    key: str
    data: str
    version: int
    score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int


class EmbeddingCreate(BaseModel):
    context_id: str
    text: str
    embedding: list[float]


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str
    redis: str
    version: str = "1.0.0"
