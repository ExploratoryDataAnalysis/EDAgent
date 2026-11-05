"""
Database Connection & Session Management
Supports PostgreSQL (asyncpg/psycopg2) and SQLite fallback.
"""

from typing import AsyncGenerator
from app.core.config import settings

try:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from sqlalchemy.orm import declarative_base

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    Base = declarative_base()

    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

except ImportError:
    # Minimal stub when SQLAlchemy is pending installation
    Base = object  # type: ignore

    async def get_db():  # type: ignore
        yield None
