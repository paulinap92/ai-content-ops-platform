"""Bounded, read-only readiness checks. Never return credentials or content."""
import asyncio

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from psycopg import Error as PostgresError
from pymongo.errors import PyMongoError

from src.core.config import settings
from src.core import document_store
from canarias_site.services.studio_auth import database_url, writer_engine


async def editor_ready(app):
    if not getattr(app.state, "storage_ready", False) or not settings.canarias_publish_enabled:
        return False

    async def check():
        if settings.editor_storage == "postgres":
            async with document_store.pool().connection() as connection:
                await connection.execute("SELECT 1")
        else:
            await app.state.mongo_client.admin.command("ping")
        async with writer_engine(database_url()).connect() as connection:
            return await connection.scalar(text("SELECT count(*) FROM design.islands")) == 8

    try:
        return await asyncio.wait_for(check(), timeout=4)
    except (TimeoutError, SQLAlchemyError, PostgresError, PyMongoError, HTTPException, OSError, RuntimeError):
        return False
