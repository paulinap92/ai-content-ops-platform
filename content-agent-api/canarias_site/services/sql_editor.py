"""Authenticated editor operations against canonical PostgreSQL only."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, text

from canarias_site.api.explore_canonical.mappers import to_legacy_geojson_feature
from canarias_site.api.guide_content_mappers import guide_content_to_legacy_item
from canarias_site.models.design_db import ContentItem, CalendarEvent, CalendarEventMonth, NewsItem
from canarias_site.repositories.explore_entity import ExploreEntityRepository
from canarias_site.repositories.guide_content import GuideContentRepository
from canarias_site.repositories.dynamic_data import CalendarEventRepository, _as_date, _as_datetime
from canarias_site.services.admin_editor import AdminEditorError, _key, _flatten_feature
from canarias_site.services.content import VALID_SECTIONS
from canarias_site.services.content_editor import ContentEditorError, _validate_item
from canarias_site.services.dynamic_data.mappers import calendar_event_to_payload, news_item_to_payload
from canarias_site.services.explore_entities.mappers import explore_entity_to_dto
from canarias_site.services.explore_import import ExploreImporter, catalog_for, validate_feature, feature_id
from canarias_site.services.guide_content.mappers import content_item_to_dto
from canarias_site.utils.islands import normalize_island


async def _save(session):
    if session.info.get("studio_atomic"):
        await session.flush()
    else:
        await session.commit()


def _island(island):
    value = normalize_island(island)
    if value is None:
        raise AdminEditorError("Unknown island")
    return value


def _month(value):
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value) is None:
        raise AdminEditorError("month must use YYYY-MM")
    return value


async def _explore_lock(session):
    await session.execute(text("SELECT pg_advisory_xact_lock(1750261027)"))
    await session.execute(text("SELECT pg_advisory_xact_lock(164661461,2)"))


async def _explore_features(session, island, resource):
    island = _island(island)
    # Editor includes hidden records; public repository applies visibility by default.
    rows = await ExploreEntityRepository(session).find_by_catalog(
        catalog_for(resource), limit=10000, island=island, include_hidden=True
    )
    return [to_legacy_geojson_feature(explore_entity_to_dto(*row, island=island)) for row in rows]


async def read_explore(session, island, resource):
    items = []
    for f in await _explore_features(session, island, resource):
        item = _flatten_feature(f)
        item["_editor_key"] = f["properties"]["canonical_id"]
        items.append(item)
    return {
        "island": _island(island),
        "resource": resource,
        "items": items,
        "count": len(items),
        "can_create": resource != "routes",
        "delete_mode": "hide",
    }


async def update_explore(session, island, resource, editor_key, item, *, allow_geometry=False):
    await _explore_lock(session)
    features = await _explore_features(session, island, resource)
    f = next(
        (
            f
            for f in features
            if f["properties"]["canonical_id"] == editor_key or _key(feature_id(f)) == editor_key
        ),
        None,
    )
    if f is None:
        raise AdminEditorError("Explore item not found")
    p = f["properties"]
    protected = {
        "id",
        "route_id",
        "osm_id",
        "osm_type",
        "gbif_id",
        "canonical_id",
        "canonical_slug",
        "entity_type",
        "catalog_code",
        "island",
    }
    p.update(
        {
            k: v
            for k, v in item.items()
            if not k.startswith("_") and k not in protected | {"latitude", "longitude", "geometry"}
        }
    )
    p["editorial_override"] = True
    g = f.get("geometry")
    if allow_geometry and item.get("geometry") is not None:
        from copy import deepcopy
        g = deepcopy(item["geometry"])
        p["geometry_override"] = True
        f["geometry"] = g
    if g and g.get("type") == "Point":
        coords = list(g["coordinates"])
        for index, key in enumerate(("longitude", "latitude")):
            if item.get(key) not in (None, ""):
                coords[index] = float(item[key])
        if coords != g["coordinates"]:
            p["geometry_override"] = True
        g["coordinates"] = coords
    f = validate_feature(f, _island(island), resource)
    await ExploreImporter(session).save_record(
        UUID(p["canonical_id"]), catalog_for(resource), f, editorial=True
    )
    await _save(session)
    saved = _flatten_feature(f)
    saved["_editor_key"] = p["canonical_id"]
    return saved


async def create_explore(session, island, resource, item, *, allow_geometry=False):
    if resource == "routes" and not (allow_geometry and item.get("geometry")):
        raise AdminEditorError("Routes need real line geometry and cannot be created here")
    await _explore_lock(session)
    island = _island(island)
    p = {
        k: v
        for k, v in item.items()
        if not k.startswith("_") and k not in {"canonical_id", "id", "latitude", "longitude", "geometry"}
    }
    p.update(
        id=f"editor-{uuid4()}",
        island=island,
        editorial_override=True,
        source="canarias-cerca-editorial",
        cc_curated=True,
    )
    if allow_geometry and resource in {"fauna", "flora"} and not item.get("geometry") and item.get("latitude") is None:
        geometry = None
    elif allow_geometry and item.get("geometry"):
        geometry = item["geometry"]
    else:
        if item.get("longitude") in (None, "") or item.get("latitude") in (None, ""):
            raise AdminEditorError("Wskaż szerokość i długość geograficzną miejsca przed publikacją.")
        geometry = {"type": "Point", "coordinates": [float(item["longitude"]), float(item["latitude"])]}
    f = validate_feature(
        {
            "type": "Feature",
            "properties": p,
            "geometry": geometry,
        },
        island,
        resource,
    )
    entity_id, _ = await ExploreImporter(session).import_feature(f, resource, island)
    await ExploreImporter(session).save_record(entity_id, catalog_for(resource), f, editorial=True)
    await _save(session)
    saved = _flatten_feature(f)
    saved["_editor_key"] = str(entity_id)
    return saved


async def hide_explore(session, island, resource, editor_key):
    return await update_explore(session, island, resource, editor_key, {"hidden": True})


def _content_payload(row):
    return guide_content_to_legacy_item(content_item_to_dto(row))


async def read_items(session, island, section):
    if section not in VALID_SECTIONS:
        raise ContentEditorError("Unknown section")
    rows = await GuideContentRepository(session).find_items(
        island=_island(island), section=section, limit=10000, include_nonpublic=True
    )
    return [_content_payload(row) for row in rows]


def _set_content(row, clean):
    row.title = str(clean.get("name") or clean.get("title"))
    row.slug = clean["slug"]
    row.category = clean.get("category")
    row.short_description = clean.get("short_description")
    row.body = clean.get("description")
    for key in ("source_url", "image_url", "image_credit", "image_source_url"):
        setattr(row, key, clean.get(key))
    row.featured = bool(clean.get("featured"))
    row.sort_order = clean.get("order")
    row.metadata_json = {**(row.metadata_json or {}), **clean, "editorial_override": True}
    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)


async def create_item(session, island, section, item):
    if section not in VALID_SECTIONS:
        raise ContentEditorError("Unknown section")
    clean = _validate_item(item)
    island = _island(island)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"editor-content:{island}:{section}"},
    )
    repo = GuideContentRepository(session)
    if await repo.find_item_by_slug(island=island, section=section, slug=clean["slug"]):
        raise ContentEditorError("slug already exists")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = ContentItem(
        id=uuid4(),
        island_entity_id=await ExploreImporter(session).island_id(island),
        module="guide",
        section=section,
        content_key=f"{section}-{island}-{clean['slug']}",
        language="es",
        publication_status="published",
        metadata_json={},
        created_at=now,
    )
    _set_content(row, clean)
    session.add(row)
    await _save(session)
    return _content_payload(row)


async def update_item(session, island, section, slug, item):
    if section not in VALID_SECTIONS:
        raise ContentEditorError("Unknown section")
    clean = _validate_item({**item, "slug": slug})
    row = await GuideContentRepository(session).find_item_by_slug(
        island=_island(island), section=section, slug=slug, include_nonpublic=True
    )
    if row is None:
        raise ContentEditorError("Item not found")
    await session.refresh(row, with_for_update=True)
    _set_content(row, clean)
    await _save(session)
    return _content_payload(row)


async def delete_item(session, island, section, slug):
    if section not in VALID_SECTIONS:
        raise ContentEditorError("Unknown section")
    row = await GuideContentRepository(session).find_item_by_slug(
        island=_island(island), section=section, slug=slug, include_nonpublic=True
    )
    if row is None:
        raise ContentEditorError("Item not found")
    await session.delete(row)
    await _save(session)


async def _events(session, island, month):
    island_id = await ExploreImporter(session).island_id(_island(island))
    return list(
        (
            await session.scalars(
                select(CalendarEvent)
                .join(CalendarEventMonth, CalendarEventMonth.calendar_event_id == CalendarEvent.id)
                .where(
                    CalendarEvent.island_entity_id == island_id,
                    CalendarEventMonth.month == _month(month),
                )
            )
        ).all()
    )


async def read_events(session, island, month):
    rows = await _events(session, island, month)
    items = [{**calendar_event_to_payload(row), "_editor_key": _key(row.event_key)} for row in rows]
    return {"island": _island(island), "month": month, "items": items, "count": len(items)}


def _edit_dynamic(row, item, protected):
    payload = dict(row.payload)
    payload.update({k: v for k, v in item.items() if not k.startswith("_") and k not in protected})
    payload["editorial_override"] = True
    for column in row.__table__.columns:
        key = column.name
        if key in payload and key not in protected | {
            "payload",
            "created_at",
            "updated_at",
            "id",
            "island_entity_id",
            "event_key",
            "news_key",
        }:
            value = payload[key]
            if key.endswith("_date"):
                value = _as_date(value)
            elif key.endswith("_at"):
                value = _as_datetime(value)
            setattr(row, key, value)
    row.payload = payload
    row.editorial_override = True
    row.updated_at = datetime.now(timezone.utc)


async def update_event(session, island, month, editor_key, item, *, allow_editorial_fields=False):
    rows = await _events(session, island, month)
    row = next((r for r in rows if _key(r.event_key) == editor_key), None)
    if row is None:
        raise AdminEditorError("Event not found")
    await session.refresh(row, with_for_update=True)
    protected = {"id", "source_id", "island"} if allow_editorial_fields else {"id", "url", "source", "source_id", "island"}
    _edit_dynamic(row, item, protected)
    await _save(session)
    return {**calendar_event_to_payload(row), "_editor_key": _key(row.event_key)}


async def create_event(session, island, month, item):
    month = _month(month)
    if not str(item.get("title") or "").strip() or not str(item.get("start_date") or "").startswith(
        month
    ):
        raise AdminEditorError("title and start_date in selected month are required")
    date.fromisoformat(item["start_date"])
    saved = {
        **item,
        "id": f"manual:{uuid4()}",
        "island": _island(island),
        "source": "Canarias Cerca editorial",
        "source_id": "canarias-cerca-editorial",
        "editorial_override": True,
        "hidden": False,
    }
    saved.setdefault("end_date", saved["start_date"])
    saved.setdefault("all_day", True)
    await CalendarEventRepository(session).upsert_item(
        island=_island(island), month=month, item=saved
    )
    await _save(session)
    return {**saved, "_editor_key": _key(saved["id"])}


async def hide_event(session, island, month, editor_key):
    return await update_event(session, island, month, editor_key, {"hidden": True})


async def read_news(session, island=None):
    rows = list((await session.scalars(select(NewsItem).order_by(NewsItem.id))).all())
    items = [
        {**news_item_to_payload(row), "_editor_key": _key(row.news_key)}
        for row in rows
        if not island or island == "canarias" or row.payload.get("island") == _island(island)
    ]
    return {"items": items, "count": len(items)}


async def update_news(session, editor_key, item, *, allow_editorial_fields=False):
    rows = list((await session.scalars(select(NewsItem))).all())
    row = next((r for r in rows if _key(r.news_key) == editor_key), None)
    if row is None:
        raise AdminEditorError("News item not found")
    await session.refresh(row, with_for_update=True)
    _edit_dynamic(row, item, {"id", "island"} if allow_editorial_fields else {"id", "url", "source", "island"})
    await _save(session)
    return {**news_item_to_payload(row), "_editor_key": _key(row.news_key)}


async def hide_news(session, editor_key):
    return await update_news(session, editor_key, {"hidden": True})





