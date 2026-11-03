"""Content Studio control plane. Public reads and editorial writes use separate sessions."""
from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from canarias_site.models.studio import StudioDocument
from canarias_site.services import studio as service, studio_media
from canarias_site.services.site_settings import SECTIONS, FEATURES, COPY_DEFAULTS, published_settings
from canarias_site.services.studio_auth import studio_session
from canarias_site.utils.islands import VALID_ISLANDS

router = APIRouter(tags=["content-studio"])
Session = Annotated[AsyncSession, Depends(studio_session)]
ASSETS = Path(__file__).resolve().parents[1] / "studio"




class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: dict[str, str]
    payload: dict
    expected_version: int = Field(ge=0)
    base_fingerprint: str = Field(min_length=64, max_length=64)


class Version(BaseModel):
    expected_version: int = Field(ge=1)


class Restore(Version):
    version: int = Field(ge=0)


class Upload(BaseModel):
    island: str
    filename: str = Field(min_length=1, max_length=180)
    data: str = Field(max_length=7_000_000)
    alt: str = Field("",max_length=300)
    credit: str = Field("",max_length=200)


def translate_error(exc):
    if isinstance(exc, HTTPException):
        raise exc
    raise HTTPException(400, str(exc)) from exc






@router.get("/site/", include_in_schema=False)
async def studio_page():
    return FileResponse(ASSETS / "index.html", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/site/assets/{name}", include_in_schema=False)
async def studio_asset(name: str):
    if name not in {"studio.js", "studio.css", "editorialText.js", "inspector.js", "charts.js"}:
        raise HTTPException(404)
    return FileResponse(ASSETS / name, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})






@router.get("/site/api/options", include_in_schema=False)
async def options(session: Session, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"islands": list(VALID_ISLANDS), "sections": SECTIONS, "features": FEATURES, "copy_defaults": COPY_DEFAULTS, "media_upload_enabled": studio_media.enabled()}


@router.get("/site/api/records", include_in_schema=False)
async def records(session: Session, kind: str, island: str, resource: str, q: str = Query("", max_length=200), offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
    try:
        return await service.list_records(session, kind, island, resource, q, offset, limit)
    except ValueError as exc:
        translate_error(exc)


@router.get("/site/api/current", include_in_schema=False)
async def current(session: Session, kind: str, island: str, resource: str, record_key: str):
    try:
        identity=service.validate_identity(dict(kind=kind,island=island,resource=resource,record_key=record_key))
        value=service.json_value(await service.canonical_value(session,identity))
        return {"published":value,"base_fingerprint":service.fingerprint(value)}
    except ValueError as exc:translate_error(exc)


@router.put("/site/api/draft", include_in_schema=False)
async def save_draft(payload: Draft, session: Session):
    try:
        return await service.save_draft(session, **payload.model_dump())
    except ValueError as exc:
        translate_error(exc)


@router.post("/site/api/documents/{document_id}/publish", include_in_schema=False)
async def publish(document_id: str, payload: Version, session: Session):
    try:
        return await service.publish(session, document_id, payload.expected_version)
    except ValueError as exc:
        translate_error(exc)


@router.get("/site/api/documents/{document_id}/history", include_in_schema=False)
async def history(document_id: str, session: Session):
    try:
        return await service.history(session, document_id)
    except ValueError as exc:
        translate_error(exc)


@router.post("/site/api/documents/{document_id}/restore", include_in_schema=False)
async def restore(document_id: str, payload: Restore, session: Session):
    try:
        return await service.restore(session, document_id, **payload.model_dump())
    except ValueError as exc:
        translate_error(exc)


@router.get("/site/api/media", include_in_schema=False)
async def media(session: Session, island: str):
    if island not in (*VALID_ISLANDS,"global"):
        raise HTTPException(400, "Unknown island")
    query=select(StudioDocument).where(StudioDocument.kind=="media")
    if island!="global":query=query.where(StudioDocument.island==island)
    rows=(await session.scalars(query.order_by(StudioDocument.updated_at.desc()).limit(200))).all()
    return {"items": [row.published for row in rows], "upload_enabled": studio_media.enabled()}


@router.post("/site/api/documents/{document_id}/rebase", include_in_schema=False)
async def rebase(document_id: str, payload: Version, session: Session):
    try:
        return await service.rebase(session, document_id, payload.expected_version)
    except ValueError as exc:
        translate_error(exc)


@router.post("/site/api/media", include_in_schema=False)
async def upload(payload: Upload, session: Session):
    try:
        return await studio_media.upload(session, payload.island, payload.filename, payload.data, payload.alt, payload.credit)
    except ValueError as exc:
        translate_error(exc)
