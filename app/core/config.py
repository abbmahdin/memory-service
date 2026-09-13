from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/memorydb"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Default TTL in seconds for contexts without explicit TTL
    DEFAULT_TTL_SECONDS: int = 3600

    # Max size for a single context blob (bytes)
    MAX_CONTEXT_SIZE: int = 1024 * 1024  # 1 MB

    # Embedding dimension for pgvector (compatible with OpenAI text-embedding-ada-002)
    EMBEDDING_DIM: int = 1536

    class Config:
        env_file = ".env"


settings = Settings()
