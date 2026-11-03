"""Canonical SQL sessions belong exclusively to the standalone editor."""
import asyncio
from functools import lru_cache
import os
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request, Response
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from canarias_site.db.base import Base
from canarias_site.models.studio import StudioDocument, StudioRevision, StudioAsset
from src.core.auth import require_editor
from src.core.document_store import connection_string

_lock = asyncio.Lock()
_initialized = set()
_engines = set()


def database_url():
    from src.core.config import settings
    value = os.getenv("SITE_DATABASE_URL", "") or (settings.site_database_url.get_secret_value() if settings.site_database_url else "")
    if not value:
        raise HTTPException(503, "Skonfiguruj SITE_DATABASE_URL w osobnym Content Editorze.")
    return value


@lru_cache(maxsize=2)
def writer_engine(url):
    engine = create_async_engine(make_url(connection_string(url)).set(drivername="postgresql+psycopg"), pool_pre_ping=True, pool_size=2, max_overflow=0, connect_args={"options": "-c statement_timeout=30000 -c lock_timeout=2000"})
    _engines.add(engine)
    return engine


async def shutdown_engines():
    for engine in tuple(_engines):
        await engine.dispose()
    _engines.clear()
    _initialized.clear()
    writer_engine.cache_clear()


async def studio_session(request: Request, response: Response):
    require_editor(request)
    response.headers["Cache-Control"] = "no-store"
    async with session_scope() as session:
        yield session


@asynccontextmanager
async def session_scope():
    engine = writer_engine(database_url())
    async with _lock:
        if engine not in _initialized:
            async with engine.begin() as connection:
                await connection.run_sync(lambda c: Base.metadata.create_all(c, tables=[StudioDocument.__table__, StudioRevision.__table__, StudioAsset.__table__]))
            _initialized.add(engine)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.info["studio_atomic"] = True
        try:
            yield session
        finally:
            await session.rollback()
