from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text, Float
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(255), primary_key=True)  # UUID or custom ID
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    contexts = relationship("MemoryContext", back_populates="agent", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="agent", cascade="all, delete-orphan")


class MemoryContext(Base):
    __tablename__ = "memory_contexts"

    id = Column(String(255), primary_key=True)  # UUID hex
    agent_id = Column(String(255), ForeignKey("agents.id"), nullable=False)
    key = Column(String(512), nullable=False, index=True)
    data = Column(LargeBinary, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    ttl = Column(Float, nullable=True)  # seconds; NULL means no expiry
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="contexts")
    embeddings = relationship("Embedding", back_populates="context", cascade="all, delete-orphan")


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = ({"postgresql_using": "ivfflat"},)

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(255), ForeignKey("agents.id"), nullable=False)
    context_id = Column(String(255), ForeignKey("memory_contexts.id"), nullable=True)
    vector = Column(Vector(1536), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="embeddings")
    context = relationship("MemoryContext", back_populates="embeddings")
