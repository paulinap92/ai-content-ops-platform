"""Private social drafts. Delivery is always an explicit owner action."""
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from beanie import PydanticObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.config import settings

CHANNELS = {"instagram", "facebook", "whatsapp"}


class SocialDraft(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    caption: str = Field(min_length=1, max_length=4000)
    platforms: list[str] = Field(min_length=1, max_length=3)
    image_url: str | None = Field(default=None, max_length=2048)
    image_alt: str = Field(default="", max_length=300)
    captions: dict[str, str] = Field(default_factory=dict)

    @field_validator("title", "caption")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Wpisz tytuł i treść posta.")
        return value.strip()

    @field_validator("image_url")
    @classmethod
    def image_link(cls, value):
        if not value:
            return None
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Zdjęcie musi mieć adres HTTPS bez danych logowania.")
        return value

    @model_validator(mode="after")
    def channels(self):
        if not set(self.platforms) <= CHANNELS or len(set(self.platforms)) != len(self.platforms):
            raise ValueError("Wybierz różne kanały: Instagram, Facebook lub WhatsApp.")
        if not set(self.captions) <= CHANNELS or any(len(v) > 4000 for v in self.captions.values()):
            raise ValueError("Nieprawidłowe wersje treści dla kanałów.")
        return self


class SocialUpdate(SocialDraft):
    version: int = Field(ge=1)


class SocialAction(BaseModel):
    version: int = Field(ge=1)
    action: Literal["ready", "draft", "archive", "restore", "confirm-published"]
    platform: Literal["instagram", "facebook", "whatsapp"] | None = None


def now():
    return datetime.now(timezone.utc).isoformat()


def channel_text(document, channel):
    return document.get("captions", {}).get(channel, "").strip() or document["caption"]


def validate_ready(document):
    if "instagram" in document["platforms"]:
        if not document.get("image_url"):
            raise HTTPException(422, "Instagram wymaga zdjęcia. Wybierz je z biblioteki.")
        if len(channel_text(document, "instagram")) > 2200:
            raise HTTPException(422, "Skróć wersję dla Instagrama do 2200 znaków.")


def public_document(document):
    # Only editor-owned fields are returned, without the database browser's text truncation.
    keys = {"id", "version", "title", "caption", "captions", "platforms", "image_url", "image_alt",
            "status", "created_at", "updated_at", "published_at", "history"}
    result = {k: v for k, v in document.items() if k in keys}
    result.setdefault("version", 1)
    result.setdefault("status", "draft")
    result.setdefault("history", [])
    result.setdefault("captions", {})
    return result


def mongo_row(document):
    return public_document({**document, "id": str(document["_id"])})


async def list_drafts():
    if settings.editor_storage == "postgres":
        from src.core.document_store import list_social
        return [public_document(d) for d in await list_social()]
    client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    try:
        rows = await client[settings.mongodb_db_name]["social_drafts"].find({}).sort("created_at", -1).limit(100).to_list(length=100)
        return [mongo_row(d) for d in rows]
    finally:
        client.close()


async def create_draft(draft):
    timestamp = now()
    document = {**draft.model_dump(), "status": "draft", "created_at": timestamp,
                "updated_at": timestamp, "published_at": None, "history": [], "version": 1}
    if settings.editor_storage == "postgres":
        from src.core.document_store import save_social
        document["id"] = await save_social(document)
    else:
        client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        try:
            result = await client[settings.mongodb_db_name]["social_drafts"].insert_one(document.copy())
            document["id"] = str(result.inserted_id)
        finally:
            client.close()
    return public_document(document)


def valid_id(identifier):
    if not PydanticObjectId.is_valid(identifier):
        raise HTTPException(404, "Nie znaleziono posta.")


async def read_draft(identifier):
    valid_id(identifier)
    if settings.editor_storage == "postgres":
        from src.core.document_store import read_social
        document = await read_social(identifier)
    else:
        client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        try:
            row = await client[settings.mongodb_db_name]["social_drafts"].find_one({"_id": PydanticObjectId(identifier)})
            document = mongo_row(row) if row else None
        finally:
            client.close()
    if not document:
        raise HTTPException(404, "Nie znaleziono posta.")
    return public_document(document)


async def write_draft(identifier, expected_version, document):
    document = {**document, "id": identifier, "version": expected_version + 1, "updated_at": now()}
    if settings.editor_storage == "postgres":
        from src.core.document_store import update_social
        matched = await update_social(identifier, expected_version, document)
    else:
        client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        try:
            query = {"_id": PydanticObjectId(identifier), "version": expected_version}
            if expected_version == 1:
                query = {"_id": PydanticObjectId(identifier), "$or": [{"version": 1}, {"version": {"$exists": False}}]}
            result = await client[settings.mongodb_db_name]["social_drafts"].update_one(query, {"$set": document})
            matched = result.matched_count == 1
        finally:
            client.close()
    if not matched:
        raise HTTPException(409, "Post zmienił się w innej karcie. Otwórz aktualną wersję przed zapisem.")
    return public_document(document)


async def update_draft(identifier, update):
    existing = await read_draft(identifier)
    if existing["status"] == "archived":
        raise HTTPException(409, "Przywróć post z archiwum przed edycją.")
    # Any content change requires approval again; delivery history keeps exact published text.
    return await write_draft(identifier, update.version,
        {**existing, **update.model_dump(exclude={"version"}), "status": "draft"})


async def act_on_draft(identifier, action):
    document = await read_draft(identifier)
    if document["version"] != action.version:
        raise HTTPException(409, "Post zmienił się w innej karcie. Otwórz aktualną wersję przed zapisem.")
    status = document["status"]
    if action.action == "restore":
        if status != "archived":
            raise HTTPException(409, "Ten post nie jest w archiwum.")
        document["status"] = "draft"
    elif status == "archived":
        raise HTTPException(409, "Przywróć post z archiwum przed zmianą.")
    elif action.action == "archive":
        document["status"] = "archived"
    elif action.action in {"ready", "draft"}:
        if action.action == "ready":
            validate_ready(document)
        document["status"] = action.action
    else:
        if status != "ready" or action.platform not in document["platforms"]:
            raise HTTPException(422, "Najpierw zatwierdź post i wybierz jego kanał.")
        validate_ready(document)
        history = document.get("history", [])
        if any(h.get("platform") == action.platform for h in history):
            raise HTTPException(409, "Publikacja w tym kanale została już potwierdzona. Nowy post zapisz jako osobny szkic.")
        document["history"] = [*history, {"platform": action.platform, "published_at": now(),
            "confirmation": "owner", "caption": channel_text(document, action.platform),
            "image_url": document.get("image_url"), "title": document["title"]}]
        document["published_at"] = document["history"][-1]["published_at"]
    return await write_draft(identifier, action.version, document)
