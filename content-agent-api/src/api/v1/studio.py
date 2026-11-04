"""Local Content Studio: bounded database browser and social draft queue.

No SQL executor, no database writes from the browser view, and no direct
publication to Meta. Publishing must use a separately authorized integration.
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorClient
from src.services.social_service import SocialDraft, SocialUpdate, SocialAction

from src.core.config import settings

async def require_local(request: Request) -> None:
    from src.core.auth import require_editor
    require_editor(request)


router = APIRouter(prefix="/api/studio", tags=["Studio"], dependencies=[Depends(require_local)])
REDACT = ("password", "secret", "token", "api_key", "credential", "authorization")


def safe(value: Any, key: str = "") -> Any:
    if any(word in key.lower() for word in REDACT):
        return "[redacted]"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): safe(v, str(k)) for k, v in value.items() if str(k) != "_id"}
    if isinstance(value, list):
        return [safe(v) for v in value[:30]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) else value[:2000]
    return str(value)[:200]


def client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)


@router.get("/database/collections")
async def collections() -> dict[str, Any]:
    if settings.editor_storage == "postgres":
        from src.core.document_store import collection_names
        return {"database": "Content Editor · prywatne dane PostgreSQL", "collections": await collection_names()}
    db_client = client()
    try:
        db = db_client[settings.mongodb_db_name]
        names = await db.list_collection_names()
        # Ignore system/internal collections; never expose arbitrary external DBs.
        names = sorted(n for n in names if not n.startswith(("system.", "_")))
        return {"database": "Content Studio · MongoDB", "collections": names[:100]}
    finally:
        db_client.close()


@router.get("/database/collections/{name}")
async def collection_rows(name: str, limit: int = Query(25, ge=1, le=100),
                          skip: int = Query(0, ge=0)) -> dict[str, Any]:
    if settings.editor_storage == "postgres":
        from src.core.document_store import browse, collection_names
        if name not in await collection_names():
            raise HTTPException(404, "Collection not found")
        count, rows = await browse(name, limit, skip)
        return {"collection": name, "count": count, "skip": skip, "rows": [safe(r) for r in rows]}
    db_client = client()
    try:
        db = db_client[settings.mongodb_db_name]
        names = await db.list_collection_names()
        if name not in names or name.startswith(("system.", "_")):
            raise HTTPException(status_code=404, detail="Collection not found")
        rows = await db[name].find({}, limit=limit, skip=skip).to_list(length=limit)
        count = await db[name].count_documents({})
        return {"collection": name, "count": count, "skip": skip,
                "rows": [safe(row) for row in rows]}
    finally:
        db_client.close()


@router.get("/social/drafts")
async def social_drafts() -> dict[str, Any]:
    from src.services.social_service import list_drafts
    return {"drafts": await list_drafts(), "publishing_connected": False,
            "delivery_mode": "manual", "metricool_url": "https://app.metricool.com/"}


@router.post("/social/drafts", status_code=201)
async def create_social_draft(draft: SocialDraft) -> dict[str, Any]:
    from src.services.social_service import create_draft
    return await create_draft(draft)


@router.put("/social/drafts/{identifier}")
async def edit_social_draft(identifier: str, draft: SocialUpdate):
    from src.services.social_service import update_draft
    return await update_draft(identifier, draft)


@router.post("/social/drafts/{identifier}/actions")
async def social_action(identifier: str, action: SocialAction):
    from src.services.social_service import act_on_draft
    return await act_on_draft(identifier, action)

