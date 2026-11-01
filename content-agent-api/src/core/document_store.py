"""PostgreSQL persistence for Studio's existing typed documents.

Only the private editor schema is used. Query fields and values are parameters;
this module is not a SQL console and does not touch public canonical records.
MongoDB remains available for existing local installations.
"""
from __future__ import annotations

from typing import Any, ClassVar

from beanie import PydanticObjectId
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from sqlalchemy.engine import make_url

_pool: AsyncConnectionPool | None = None
TABLE = sql.Identifier("cc_editor_private", "documents")


def connection_string(url):
    parsed = make_url(url).set(drivername="postgresql")
    if parsed.host and parsed.host.endswith(".neon.tech"):
        parsed = parsed.set(host=parsed.host.replace("-pooler.", "."))
    return parsed.render_as_string(hide_password=False)


async def initialize(url):
    global _pool
    _pool = AsyncConnectionPool(connection_string(url), min_size=0, max_size=2, open=False,
        kwargs={"row_factory": dict_row, "options": "-c statement_timeout=30000 -c lock_timeout=2000"})
    await _pool.open()
    async with _pool.connection() as conn:
        await conn.execute("SELECT pg_advisory_xact_lock(192744, 1)")
        await conn.execute("CREATE SCHEMA IF NOT EXISTS cc_editor_private")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cc_editor_private.documents (
            collection text NOT NULL, id text NOT NULL, payload jsonb NOT NULL,
            version integer NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY(collection,id))""")
        for collection, field in [("content_drafts", "thread_id"), ("photos", "source_key"),
                ("event_sources", "source_id"), ("event_source_reviews", "source_id"),
                ("event_source_catalog_state", "key")]:
            await conn.execute(sql.SQL("CREATE UNIQUE INDEX IF NOT EXISTS {} ON {} (collection,(payload->>{})) WHERE collection={}").format(
                sql.Identifier("unique_" + collection), TABLE, sql.Literal(field), sql.Literal(collection)))


async def shutdown():
    global _pool
    if _pool:
        await _pool.close()
    _pool = None


def pool():
    if _pool is None:
        raise RuntimeError("Editor storage is not initialized")
    return _pool


class FieldRef(str):
    def __eq__(self, value):
        return {str(self): value}
    __hash__ = str.__hash__


class DocumentMeta(type(BaseModel)):
    def __getattr__(cls, name):
        fields = type.__getattribute__(cls, "__dict__").get("__pydantic_fields__", {})
        if not name.startswith("_") and name in fields:
            return FieldRef(name)
        return super().__getattr__(name)


class Document(BaseModel, metaclass=DocumentMeta):
    model_config = ConfigDict(arbitrary_types_allowed=True, ignored_types=(type,))
    id: PydanticObjectId = Field(default_factory=PydanticObjectId)
    _version: int = PrivateAttr(default=0)

    @classmethod
    def collection(cls):
        return cls.Settings.name

    @classmethod
    def find(cls, *filters):
        return Query(cls, filters)

    @classmethod
    def find_all(cls):
        return cls.find()

    @classmethod
    async def find_one(cls, *filters):
        rows = await cls.find(*filters).limit(1).to_list()
        return rows[0] if rows else None

    @classmethod
    async def get(cls, object_id):
        return await cls.find_one({"id": str(object_id)})

    async def insert(self):
        async with pool().connection() as conn:
            await conn.execute(sql.SQL("INSERT INTO {} (collection,id,payload) VALUES (%s,%s,%s)").format(TABLE),
                (self.collection(), str(self.id), Jsonb(self.model_dump(mode="json"))))
        self._version = 1
        return self

    async def save(self):
        if not self._version:
            return await self.insert()
        async with pool().connection() as conn:
            result = await conn.execute(sql.SQL("UPDATE {} SET payload=%s,version=version+1,updated_at=now() WHERE collection=%s AND id=%s AND version=%s RETURNING version").format(TABLE),
                (Jsonb(self.model_dump(mode="json")), self.collection(), str(self.id), self._version))
            row = await result.fetchone()
            if row is None:
                from src.services.exceptions import ConflictException
                raise ConflictException("Dokument został zmieniony. Odśwież przed zapisem.")
            self._version = row["version"]
        return self

    async def save_changes(self):
        return await self.save()

    async def delete(self):
        async with pool().connection() as conn:
            result = await conn.execute(sql.SQL("DELETE FROM {} WHERE collection=%s AND id=%s AND version=%s").format(TABLE),
                (self.collection(), str(self.id), self._version))
            if result.rowcount != 1:
                from src.services.exceptions import ConflictException
                raise ConflictException("Dokument został zmieniony. Odśwież przed usunięciem.")


class Query:
    def __init__(self, model, filters):
        self.model, self.filters = model, filters
        self.order = []
        self.maximum, self.offset = 10000, 0

    def sort(self, fields):
        self.order = fields
        return self

    def limit(self, value):
        self.maximum = max(0, min(int(value), 10000))
        return self

    def skip(self, value):
        self.offset = max(0, int(value))
        return self

    def where(self):
        pieces, args = [sql.SQL("collection=%s")], [self.model.collection()]
        for criterion in self.filters:
            if not isinstance(criterion, dict):
                raise ValueError("Invalid editor document filter")
            for field, value in criterion.items():
                if field not in self.model.model_fields:
                    raise ValueError("Unknown document field")
                if isinstance(value, dict) and "$regex" in value:
                    operator = sql.SQL("~*") if "i" in value.get("$options", "") else sql.SQL("~")
                    pieces.append(sql.SQL("payload->>%s {} %s").format(operator))
                    args.extend([field, value["$regex"]])
                else:
                    pieces.append(sql.SQL("payload @> %s"))
                    args.append(Jsonb({field: value}))
        return sql.SQL(" AND ").join(pieces), args

    async def to_list(self, length=None):
        clause, args = self.where()
        query = sql.SQL("SELECT payload,version FROM {} WHERE {}").format(TABLE, clause)
        if self.order:
            order = []
            for field, direction in self.order:
                if field not in self.model.model_fields:
                    raise ValueError("Unknown sort field")
                order.append(sql.SQL("payload->%s {} NULLS LAST").format(sql.SQL("DESC" if int(direction) < 0 else "ASC")))
                args.append(field)
            query += sql.SQL(" ORDER BY ") + sql.SQL(",").join(order)
        query += sql.SQL(" LIMIT %s OFFSET %s")
        args.extend([min(self.maximum, int(length)) if length is not None else self.maximum, self.offset])
        async with pool().connection() as conn:
            rows = await (await conn.execute(query, args)).fetchall()
        result = []
        for row in rows:
            item = self.model.model_validate(row["payload"])
            item._version = row["version"]
            result.append(item)
        return result


async def collection_names():
    async with pool().connection() as conn:
        rows = await (await conn.execute("SELECT DISTINCT collection FROM cc_editor_private.documents ORDER BY collection")).fetchall()
    return [r["collection"] for r in rows]


async def browse(collection, maximum=25, offset=0):
    async with pool().connection() as conn:
        count = (await (await conn.execute("SELECT count(*) AS count FROM cc_editor_private.documents WHERE collection=%s", (collection,))).fetchone())["count"]
        rows = await (await conn.execute("SELECT payload FROM cc_editor_private.documents WHERE collection=%s ORDER BY updated_at DESC LIMIT %s OFFSET %s", (collection, maximum, offset))).fetchall()
    return count, [row["payload"] for row in rows]


async def save_social(document):
    item_id = str(PydanticObjectId())
    async with pool().connection() as conn:
        await conn.execute("INSERT INTO cc_editor_private.documents(collection,id,payload) VALUES ('social_drafts',%s,%s)", (item_id, Jsonb(document)))
    return item_id
