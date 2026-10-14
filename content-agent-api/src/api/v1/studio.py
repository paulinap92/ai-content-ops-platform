"""Local Content Studio: bounded database browser and social draft queue.

No SQL executor, no database writes from the browser view, and no direct
publication to Meta. Publishing must use a separately authorized integration.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from src.core.config import settings

async def require_local(request: Request) -> None:
    # Local operator tool, not a public administration endpoint.
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Studio admin API is localhost-only")


router = APIRouter(prefix="/api/studio", tags=["Studio"], dependencies=[Depends(require_local)])
REDACT = ("password", "secret", "token", "api_key", "credential", "authorization")
ALLOWED_PLATFORMS = {"instagram", "facebook"}


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


class SocialDraft(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    caption: str = Field(min_length=1, max_length=4000)
    platforms: list[str] = Field(min_length=1, max_length=2)
    image_url: str | None = Field(default=None, max_length=2048)


@router.get("/social/drafts")
async def social_drafts() -> dict[str, Any]:
    db_client = client()
    try:
        cursor = db_client[settings.mongodb_db_name]["social_drafts"].find({}).sort(
            "created_at", -1).limit(100)
        return {"drafts": [safe(x) for x in await cursor.to_list(length=100)],
                "publishing_connected": False}
    finally:
        db_client.close()


@router.post("/social/drafts", status_code=201)
async def create_social_draft(draft: SocialDraft) -> dict[str, Any]:
    if not set(draft.platforms).issubset(ALLOWED_PLATFORMS) or len(set(draft.platforms)) != len(draft.platforms):
        raise HTTPException(status_code=422, detail="Only unique instagram/facebook platforms are supported")
    db_client = client()
    try:
        document = {
            **draft.model_dump(), "status": "draft",
            "created_at": datetime.now(timezone.utc),
            "published_at": None,
        }
        result = await db_client[settings.mongodb_db_name]["social_drafts"].insert_one(document)
        return {"id": str(result.inserted_id), "status": "draft",
                "message": "Saved locally. Nothing has been posted to social media."}
    finally:
        db_client.close()
