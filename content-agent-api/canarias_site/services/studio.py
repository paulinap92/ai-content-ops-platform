"""Draft -> review -> atomic publication to existing canonical repositories."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, text

from canarias_site.models.design_db import ContentItem, CalendarEvent, CalendarEventMonth, NewsItem
from canarias_site.models.studio import StudioDocument, StudioRevision
from canarias_site.services import sql_editor
from canarias_site.services.admin_editor import EXPLORE_RESOURCES, _key
from canarias_site.services.content import VALID_SECTIONS
from canarias_site.services.dynamic_data.mappers import calendar_event_to_payload, news_item_to_payload
from canarias_site.services.guide_content.mappers import content_item_to_dto
from canarias_site.api.guide_content_mappers import guide_content_to_legacy_item
from canarias_site.services.site_settings import empty_settings, normalize_settings
from canarias_site.services.editorial_privacy import public_payload
from canarias_site.utils.islands import VALID_ISLANDS

def json_value(value):
    return json.loads(json.dumps(value, default=lambda v: v.isoformat() if hasattr(v, "isoformat") else str(v), allow_nan=False))


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(json_value(value), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def validate_identity(identity: dict) -> dict:
    if set(identity) != {"kind", "island", "resource", "record_key"}:
        raise ValueError("Invalid content identity")
    kind, island, resource = (identity[k] for k in ("kind", "island", "resource"))
    key = identity["record_key"]
    if not isinstance(key, str) or not 1 <= len(key) <= 200:
        raise ValueError("Invalid record key")
    if kind == "settings":
        if (island, resource, key) != ("global", "site", "site"):
            raise ValueError("Invalid settings identity")
    elif island not in VALID_ISLANDS and not (kind == "news" and island == "canarias"):
        raise ValueError("Unknown island")
    elif kind == "guide" and resource in VALID_SECTIONS:
        pass
    elif kind == "explore" and resource in EXPLORE_RESOURCES:
        pass
    elif kind == "calendar" and re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", resource):
        pass
    elif kind == "news" and resource == "news":
        pass
    else:
        raise ValueError("Unknown resource")
    return identity


def validate_payload(identity: dict, payload: dict) -> dict:
    value = json_value(payload)
    if len(json.dumps(value)) > 250_000:
        raise ValueError("Content is too large")
    if identity["kind"] == "settings":
        return normalize_settings(value)
    if not str(value.get("name") or value.get("title") or "").strip():
        raise ValueError("Tytuł jest wymagany.")
    for field in ("url", "source_url", "image_url", "image_source_url", "website"):
        url = value.get(field)
        if url and (not isinstance(url, str) or not re.match(r"^https?://[^\s]+$", url)):
            raise ValueError(f"{field}: wymagany pełny adres https:// lub http://")
    for field, low, high in (("latitude", -90, 90), ("longitude", -180, 180)):
        if value.get(field) not in (None, ""):
            number = float(value[field])
            if not math.isfinite(number) or not low <= number <= high:
                raise ValueError(f"Nieprawidłowe {field}")
            value[field] = number
    if "hidden" in value and type(value["hidden"]) is not bool:
        raise ValueError("hidden must be a boolean")
    if identity["kind"] == "guide":
        sql_editor._validate_item(value)
    if identity["kind"] == "calendar":
        start = str(value.get("start_date") or "")
        end = str(value.get("end_date") or start)
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if (last - first).days > 3660:
            raise ValueError("Zakres wydarzenia jest zbyt długi.")
        if end < start:
            raise ValueError("Data końca poprzedza początek.")
    return value


def identity_of(row):
    return {k: getattr(row, k) for k in ("kind", "island", "resource", "record_key")}


def document_view(row):
    return {"id": str(row.id), "identity": identity_of(row), "version": row.version,
            "status": row.status, "draft": row.draft, "published": row.published,
            "base_fingerprint": row.base_fingerprint, "updated_at": row.updated_at.isoformat()}


def document_query(identity):
    return select(StudioDocument).where(*(getattr(StudioDocument, k) == v for k, v in identity.items()))


async def canonical_items(session, kind, island, resource, *, lock=False):
    validate_identity({"kind": kind, "island": island, "resource": resource, "record_key": "listing" if kind != "settings" else "site"})
    if kind == "settings":
        row = await session.scalar(select(StudioDocument).where(StudioDocument.kind == "settings"))
        return [("site", row.published if row and row.published is not None else empty_settings())]
    if kind == "guide":
        island_id = await sql_editor.ExploreImporter(session).island_id(island)
        query = select(ContentItem).where(ContentItem.module == "guide", ContentItem.island_entity_id == island_id, ContentItem.section == resource)
        if lock:
            query = query.with_for_update()
        rows = list((await session.scalars(query.execution_options(populate_existing=True))).all())
        return [(str(row.id), {**guide_content_to_legacy_item(content_item_to_dto(row)), "hidden": row.publication_status == "hidden", "language": row.language}) for row in rows]
    if kind == "explore":
        if lock:
            await sql_editor._explore_lock(session)
        features = await sql_editor._explore_features(session, island, resource)
        return [(f["properties"]["canonical_id"], {**sql_editor._flatten_feature(f), "_editor_key": f["properties"]["canonical_id"], "geometry": f.get("geometry")}) for f in features]
    island_id = None if kind == "news" and island == "canarias" else await sql_editor.ExploreImporter(session).island_id(island)
    if kind == "calendar":
        query = select(CalendarEvent).join(CalendarEventMonth, CalendarEventMonth.calendar_event_id == CalendarEvent.id).where(CalendarEvent.island_entity_id == island_id, CalendarEventMonth.month == resource)
        if lock:
            query = query.with_for_update(of=CalendarEvent)
        rows = (await session.scalars(query.execution_options(populate_existing=True))).all()
        return [(_key(r.event_key), calendar_event_to_payload(r)) for r in rows]
    query = select(NewsItem).where(NewsItem.island_entity_id == island_id)
    if lock:
        query = query.with_for_update()
    rows = (await session.scalars(query.execution_options(populate_existing=True))).all()
    return [(_key(r.news_key), news_item_to_payload(r)) for r in rows]


async def canonical_value(session, identity, *, lock=False):
    values = await canonical_items(session, **{k: identity[k] for k in ("kind", "island", "resource")}, lock=lock)
    return next((payload for key, payload in values if key == identity["record_key"]), None)


async def list_records(session, kind, island, resource, q="", offset=0, limit=100):
    values = dict(await canonical_items(session, kind, island, resource))
    documents = (await session.scalars(select(StudioDocument).where(StudioDocument.kind == kind, StudioDocument.island == island, StudioDocument.resource == resource))).all()
    by_key = {row.record_key: row for row in documents}
    results = []
    for key in values.keys() | by_key.keys():
        if key in by_key:
            item = document_view(by_key[key])
        else:
            payload = json_value(values[key])
            item = {"id": None, "identity": {"kind": kind, "island": island, "resource": resource, "record_key": key}, "version": 0, "status": "published", "draft": payload, "published": payload, "base_fingerprint": fingerprint(payload)}
        title = str(item["draft"].get("name") or item["draft"].get("title") or key)
        if not q or q.casefold() in (title + json.dumps(item["draft"], ensure_ascii=False)).casefold():
            results.append(item)
    results.sort(key=lambda r: str(r["draft"].get("name") or r["draft"].get("title") or "").casefold())
    return {"items": results[offset:offset + limit], "count": len(results), "offset": offset, "limit": limit}


async def _revision(session, row, action):
    session.add(StudioRevision(id=uuid4(), document_id=row.id, version=row.version, action=action, payload=row.draft, created_at=datetime.now(timezone.utc)))


async def save_draft(session, identity, payload, expected_version, base_fingerprint):
    identity = validate_identity(identity)
    payload = validate_payload(identity, payload)
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "studio:" + fingerprint(identity)})
    row = await session.scalar(document_query(identity).with_for_update())
    if row and row.version != expected_version or not row and expected_version != 0:
        raise HTTPException(409, "Treść zmieniła się w innym oknie. Wczytaj nowszą wersję.")
    if not row:
        current = json_value(await canonical_value(session, identity))
        if fingerprint(current) != base_fingerprint:
            raise HTTPException(409, "Dane źródłowe zmieniły się. Odśwież wpis przed zapisem.")
        row = StudioDocument(id=uuid4(), **identity, published=current, draft={}, base_fingerprint=base_fingerprint, version=0, status="draft", updated_at=datetime.now(timezone.utc))
        session.add(row)
        await session.flush()
        if current is not None:
            session.add(StudioRevision(id=uuid4(), document_id=row.id, version=0, action="before_first_edit", payload=current, created_at=datetime.now(timezone.utc)))
    row.draft, row.status = payload, "draft"
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await _revision(session, row, "save_draft")
    await session.commit()
    return document_view(row)


async def _locked_document(session, document_id, expected_version):
    row = await session.get(StudioDocument, UUID(document_id), with_for_update=True)
    if not row:
        raise HTTPException(404, "Draft nie istnieje.")
    if row.version != expected_version:
        raise HTTPException(409, "Nowsza wersja jest już zapisana. Odśwież wpis.")
    return row


async def publish(session, document_id, expected_version):
    row = await _locked_document(session, document_id, expected_version)
    identity = identity_of(row)
    current = json_value(await canonical_value(session, identity, lock=True))
    if fingerprint(current) != row.base_fingerprint:
        raise HTTPException(409, "Wpis na stronie zmienił się od rozpoczęcia edycji. Wczytaj i porównaj aktualną treść.")
    payload = validate_payload(identity, row.draft)
    public = public_payload(payload)
    kind, island, resource = (identity[k] for k in ("kind", "island", "resource"))
    if kind == "settings":
        row.published = public
    elif kind == "guide":
        if current is None:
            await sql_editor.create_item(session, island, resource, public)
            model = await sql_editor.GuideContentRepository(session).find_item_by_slug(island=island, section=resource, slug=public["slug"])
            row.record_key = str(model.id)
        else:
            await sql_editor.update_item(session, island, resource, current["slug"], public)
            model = await session.get(ContentItem, UUID(row.record_key))
        model.publication_status = "hidden" if public.get("hidden") else "published"
        model.language = public.get("language", "es")
    elif kind == "explore":
        if current is None:
            saved = await sql_editor.create_explore(session, island, resource, public, allow_geometry=True)
            row.record_key = saved["_editor_key"]
        else:
            await sql_editor.update_explore(session, island, resource, row.record_key, public, allow_geometry=True)
    elif kind == "calendar":
        target_month = public["start_date"][:7]
        if current is None:
            saved = await sql_editor.create_event(session, island, target_month, public)
            row.record_key = saved["_editor_key"]
        else:
            await sql_editor.update_event(session, island, resource, row.record_key, public, allow_editorial_fields=True)
        events = (await session.scalars(select(CalendarEvent).where(CalendarEvent.island_entity_id == await sql_editor.ExploreImporter(session).island_id(island)))).all()
        event = next(r for r in events if _key(r.event_key) == row.record_key)
        await session.execute(delete(CalendarEventMonth).where(CalendarEventMonth.calendar_event_id == event.id))
        first, last = date.fromisoformat(public["start_date"][:7] + "-01"), date.fromisoformat((public.get("end_date") or public["start_date"])[:7] + "-01")
        while first <= last:
            session.add(CalendarEventMonth(calendar_event_id=event.id, month=first.strftime("%Y-%m"), created_at=datetime.now(timezone.utc)))
            first = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
        row.resource = target_month
    elif kind == "news":
        if current is None:
            from canarias_site.repositories.dynamic_data import NewsItemRepository
            news_id = f"manual:{uuid4()}"
            if public.get("url") and await session.scalar(select(NewsItem.id).where(NewsItem.news_key == public["url"])):
                raise HTTPException(409, "Aktualność o tym adresie już istnieje. Otwórz istniejący wpis.")
            public = {**public, "id": news_id, "island": island, "editorial_override": True, "source": public.get("source") or "Canarias Cerca editorial"}
            await NewsItemRepository(session).upsert_item(item=public)
            row.record_key = _key(public.get("url") or news_id)
        else:
            await sql_editor.update_news(session, row.record_key, public, allow_editorial_fields=True)
    await session.flush()
    row.published = json_value(await canonical_value(session, identity_of(row)))
    row.base_fingerprint = fingerprint(row.published)
    row.status = "hidden" if public.get("hidden") else "published"
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)
    await _revision(session, row, "publish")
    await session.commit()
    return document_view(row)


async def history(session, document_id):
    rows = (await session.scalars(select(StudioRevision).where(StudioRevision.document_id == UUID(document_id)).order_by(StudioRevision.version.desc()).limit(100))).all()
    return {"items": [{"version": r.version, "action": r.action, "payload": r.payload, "created_at": r.created_at.isoformat()} for r in rows]}


async def restore(session, document_id, version, expected_version):
    row = await _locked_document(session, document_id, expected_version)
    revision = await session.scalar(select(StudioRevision).where(StudioRevision.document_id == row.id, StudioRevision.version == version))
    if not revision:
        raise HTTPException(404, "Nie znaleziono wersji.")
    row.draft = revision.payload
    row.base_fingerprint = fingerprint(await canonical_value(session, identity_of(row), lock=True))
    row.version += 1
    row.status = "draft"
    row.updated_at = datetime.now(timezone.utc)
    await _revision(session, row, "restore_draft")
    await session.commit()
    return document_view(row)


async def rebase(session, document_id, expected_version):
    row = await _locked_document(session, document_id, expected_version)
    current = json_value(await canonical_value(session, identity_of(row), lock=True))
    row.published = current
    row.base_fingerprint = fingerprint(current)
    row.version += 1
    row.status = "draft"
    row.updated_at = datetime.now(timezone.utc)
    await _revision(session, row, "refresh_public_baseline")
    await session.commit()
    return document_view(row)
