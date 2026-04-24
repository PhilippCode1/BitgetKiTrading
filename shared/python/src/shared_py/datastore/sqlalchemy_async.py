"""SQLAlchemy 2 Async-Engine mit festem Connection-Pool (institutionelle Last)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from shared_py.datastore.pool_config import (
    SQLALCHEMY_MAX_OVERFLOW,
    SQLALCHEMY_POOL_RECYCLE_SEC,
    SQLALCHEMY_POOL_SIZE,
)


def database_url_to_async_sqlalchemy(dsn: str) -> str:
    """
    postgresql://… bzw. postgres://… -> postgresql+asyncpg://…
    """
    s = (dsn or "").strip()
    if not s:
        return s
    if s.startswith("postgresql+asyncpg://"):
        return s
    s = re.sub(
        r"^postgres(ql)?(\+[^/]+)?://",
        "postgresql+asyncpg://",
        s,
        count=1,
        flags=re.IGNORECASE,
    )
    if not s.startswith("postgresql+asyncpg://"):
        if s.startswith("postgres://"):
            s = "postgresql+asyncpg://" + s[len("postgres://") :]
    return s


def create_pooled_async_engine(
    dsn: str,
    *,
    pool_size: int = SQLALCHEMY_POOL_SIZE,
    max_overflow: int = SQLALCHEMY_MAX_OVERFLOW,
    pool_recycle: int = SQLALCHEMY_POOL_RECYCLE_SEC,
    **kwargs: Any,
) -> AsyncEngine:
    url = database_url_to_async_sqlalchemy(dsn)
    if not url:
        raise ValueError("dsn leer")
    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=pool_recycle,
        **kwargs,
    )
