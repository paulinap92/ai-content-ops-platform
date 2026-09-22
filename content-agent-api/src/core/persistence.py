from contextlib import contextmanager
from typing import Generator
from langgraph.checkpoint.mongodb import MongoDBSaver
from src.core.config import settings

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