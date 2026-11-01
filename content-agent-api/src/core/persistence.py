from contextlib import contextmanager
from typing import Generator
from langgraph.checkpoint.mongodb import MongoDBSaver
from src.core.config import settings
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from src.core.document_store import connection_string

"""
Synchroniczny MongoDB Checkpointer dla LangGraph.

LangGraph MongoDBSaver używa sync PyMongo wewnętrznie — nie można tego zmienić.
Dlatego osobny sync klient tylko dla checkpointera.
Beanie/Motor (async) używamy oddzielnie dla metadanych artykułów.

Checkpointer tworzony RAZ w lifespan — nie per request.
"""

@contextmanager
def create_mongodb_checkpointer() -> Generator[MongoDBSaver, None, None]:
    """
    Context manager — tworzy MongoDBSaver i zamyka sync połączenie przy wyjściu.
    """
    with MongoDBSaver.from_conn_string(
        settings.mongodb_uri,
        settings.mongodb_db_name
    ) as checkpointer:
        yield checkpointer


@contextmanager
def create_editor_checkpointer():
    if settings.editor_storage == "mongodb":
        with create_mongodb_checkpointer() as checkpointer:
            yield checkpointer
        return
    value = settings.editor_database_url or settings.site_database_url
    if not value:
        raise ValueError("EDITOR_DATABASE_URL or SITE_DATABASE_URL is required")
    # Checkpoints and migrations stay in the private editor schema only.
    with ConnectionPool(connection_string(value.get_secret_value()), min_size=0, max_size=2,
            kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0,
                    "options": "-c search_path=cc_editor_private -c statement_timeout=30000 -c lock_timeout=2000"}) as pool:
        saver = PostgresSaver(pool)
        with pool.connection() as connection:
            connection.execute("SELECT pg_advisory_lock(192744, 2)")
            try:
                saver.setup()
            finally:
                connection.execute("SELECT pg_advisory_unlock(192744, 2)")
        yield saver
