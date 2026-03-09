"""
Async SQLAlchemy session factory and engine management.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import select

from app.config import get_settings

logger = logging.getLogger(__name__)


def create_engine():
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300,
    )


engine = None
async_session_factory = None


async def seed_default_user() -> None:
    """Create default admin user for testing if it doesn't exist."""
    from sqlalchemy import text
    from uuid import uuid4

    try:
        async with async_session_factory() as session:
            # Check if admin user exists
            result = await session.execute(
                select(text("1")).select_from(
                    text("users WHERE username = 'admin'")
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                # Use pre-hashed password created externally
                # Password: "admin123" hashed with bcrypt
                from app.auth.password import hash_password
                hashed = hash_password("admin123")

                await session.execute(
                    text("""
                    INSERT INTO users (id, username, email, password_hash, role, is_active, created_at, updated_at)
                    VALUES (:id, :username, :email, :password_hash, :role, :is_active, NOW(), NOW())
                    """),
                    {
                        "id": str(uuid4()),
                        "username": "admin",
                        "email": "admin@pensy.local",
                        "password_hash": hashed,
                        "role": "ADMIN",
                        "is_active": True,
                    },
                )
                await session.commit()
                logger.info("✓ Created default admin user: admin / admin123")
            else:
                logger.info("✓ Admin user already exists")
    except Exception as e:
        logger.warning(f"Could not seed default user: {e}")


def init_db() -> None:
    global engine, async_session_factory
    engine = create_engine()
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def init_db_async() -> None:
    """Create tables and seed data. Call this from async context (e.g., lifespan)."""
    from app.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await seed_default_user()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        init_db()
    assert async_session_factory is not None
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    global engine
    if engine:
        await engine.dispose()
