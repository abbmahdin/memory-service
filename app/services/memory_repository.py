from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, delete, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models import Agent, MemoryContext, Embedding
from app.core.config import settings
import secrets


class MemoryRepository:
    """Repository for PostgreSQL-based memory operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- Agent operations ----

    async def create_agent(self, agent_id: str, name: str) -> Agent:
        agent = Agent(id=agent_id, name=name)
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
        return result.scalar_one_or_none()

    # ---- Context operations ----

    async def create_context(
        self,
        agent_id: str,
        key: str,
        data: bytes,
        ttl: Optional[float] = None,
        context_id: Optional[str] = None,
    ) -> MemoryContext:
        context_id = context_id or secrets.token_hex(16)
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl) if ttl else None

        ctx = MemoryContext(
            id=context_id,
            agent_id=agent_id,
            key=key,
            data=data,
            version=1,
            ttl=ttl,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        self.db.add(ctx)
        await self.db.commit()
        await self.db.refresh(ctx)
        return ctx

    async def create_context_version(
        self,
        agent_id: str,
        key: str,
        data: bytes,
        ttl: Optional[float] = None,
        base_context_id: Optional[str] = None,
    ) -> MemoryContext:
        """Create a new version of an existing context (versioning).
        If base_context_id provided, increments version from the latest.
        """
        new_version = 1
        if base_context_id:
            existing = await self.get_context(base_context_id)
            if existing:
                new_version = existing.version + 1

        new_context_id = secrets.token_hex(16)
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl) if ttl else None

        ctx = MemoryContext(
            id=new_context_id,
            agent_id=agent_id,
            key=key,
            data=data,
            version=new_version,
            ttl=ttl,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        self.db.add(ctx)
        await self.db.commit()
        await self.db.refresh(ctx)
        return ctx

    async def get_context(self, context_id: str) -> Optional[MemoryContext]:
        result = await self.db.execute(
            select(MemoryContext).where(MemoryContext.id == context_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_version(self, agent_id: str, key: str) -> Optional[MemoryContext]:
        result = await self.db.execute(
            select(MemoryContext)
            .where(
                and_(
                    MemoryContext.agent_id == agent_id,
                    MemoryContext.key == key,
                    or_(
                        MemoryContext.expires_at.is_(None),
                        MemoryContext.expires_at > datetime.utcnow(),
                    ),
                )
            )
            .order_by(MemoryContext.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_versions(self, agent_id: str, key: str) -> list[MemoryContext]:
        result = await self.db.execute(
            select(MemoryContext)
            .where(
                and_(
                    MemoryContext.agent_id == agent_id,
                    MemoryContext.key == key,
                )
            )
            .order_by(MemoryContext.version.desc())
        )
        return list(result.scalars().all())

    async def list_contexts(
        self,
        agent_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[MemoryContext], int]:
        # Only return non-expired contexts
        now = datetime.utcnow()
        condition = and_(
            MemoryContext.agent_id == agent_id,
            or_(
                MemoryContext.expires_at.is_(None),
                MemoryContext.expires_at > now,
            ),
        )

        total_result = await self.db.execute(
            select(func.count(MemoryContext.id)).where(condition)
        )
        total = total_result.scalar_one()

        result = await self.db.execute(
            select(MemoryContext)
            .where(condition)
            .order_by(MemoryContext.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        contexts = list(result.scalars().all())
        return contexts, total

    async def update_context(
        self,
        context_id: str,
        data: Optional[bytes] = None,
        ttl: Optional[float] = None,
        expected_version: Optional[int] = None,
    ) -> Optional[MemoryContext]:
        ctx = await self.get_context(context_id)
        if not ctx:
            return None

        if expected_version is not None and ctx.version != expected_version:
            raise ValueError("Version mismatch - optimistic lock failed")

        if data is not None:
            ctx.data = data
        if ttl is not None:
            ctx.ttl = ttl
            if ttl > 0:
                ctx.expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            else:
                ctx.expires_at = None

        ctx.version += 1
        ctx.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(ctx)
        return ctx

    async def delete_context(self, context_id: str) -> bool:
        result = await self.db.execute(
            delete(MemoryContext).where(MemoryContext.id == context_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def delete_all_agent_contexts(self, agent_id: str) -> int:
        result = await self.db.execute(
            delete(MemoryContext).where(MemoryContext.agent_id == agent_id)
        )
        await self.db.commit()
        return result.rowcount

    async def delete_expired(self) -> int:
        now = datetime.utcnow()
        result = await self.db.execute(
            delete(MemoryContext).where(
                and_(
                    MemoryContext.expires_at.isnot(None),
                    MemoryContext.expires_at <= now,
                )
            )
        )
        await self.db.commit()
        return result.rowcount

    # ---- Embedding / Search operations ----

    async def store_embedding(
        self,
        agent_id: str,
        context_id: Optional[str],
        text: str,
        embedding: list[float],
    ) -> Embedding:
        emb = Embedding(
            agent_id=agent_id,
            context_id=context_id,
            text=text,
            vector=embedding,
        )
        self.db.add(emb)
        await self.db.commit()
        await self.db.refresh(emb)
        return emb

    async def semantic_search(
        self,
        agent_id: str,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[tuple[MemoryContext, float]]:
        """Search contexts semantically using pgvector cosine distance."""
        now = datetime.utcnow()

        result = await self.db.execute(
            select(
                MemoryContext,
                Embedding,
                func.cosine_distance(Embedding.vector, query_embedding).label("distance"),
            )
            .join(Embedding, Embedding.context_id == MemoryContext.id)
            .where(
                and_(
                    MemoryContext.agent_id == agent_id,
                    or_(
                        MemoryContext.expires_at.is_(None),
                        MemoryContext.expires_at > now,
                    ),
                )
            )
            .order_by(func.cosine_distance(Embedding.vector, query_embedding))
            .limit(limit)
        )
        rows = result.fetchall()
        return [(row[0], 1.0 - float(row[2])) for row in rows]

    async def health_check(self) -> bool:
        try:
            await self.db.execute(select(func.now()))
            return True
        except Exception:
            return False
