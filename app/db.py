# app/db.py
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Use env var in compose; fallback useful for local dev without compose
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://trellis:trellis@localhost:5432/trellisdb",
)

_engine: AsyncEngine | None = None
_Session: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _Session
    if _Session is None:
        _Session = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _Session


@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    """
    Transactional async session context manager.
    Commits on success, rolls back on error.
    """
    Session = get_sessionmaker()
    async with Session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def run_sql_file(path: str) -> None:
    """
    Idempotently apply SQL file (used by API / startup).
    Keep it safe to re-run on restarts.
    """
    engine = get_engine()
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    
    # Split SQL statements - asyncpg doesn't support multiple statements in one execute
    statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip()]
    
    async with engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))
