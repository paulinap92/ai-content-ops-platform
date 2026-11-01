from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from canarias_site.models.design_db import (
    CalendarEvent,
    CalendarEventMonth,
    ClimateObservation,
    Entity,
    Island,
    LiveSnapshot,
    NewsItem,
    SeismicEvent,
    StatisticalSnapshot,
    VolcanicReport,
)
from canarias_site.repositories.base import GenericRepository


class _IslandLookupMixin:
    session: AsyncSession

    @staticmethod
    def island_conditions(island_entity: type[Entity], island: str):
        normalized = island.strip().lower()
        friendly = normalized.replace("-", " ")
        return or_(
            func.lower(island_entity.slug) == normalized,
            func.lower(island_entity.canonical_name) == friendly,
            func.lower(island_entity.slug).like(f"island-{normalized}-%"),
        )

    async def island_entity_id(self, island: str):
        island_entity = aliased(Entity)
        canonical_island = aliased(Island)
        stmt = (
            select(canonical_island.entity_id)
            .join(
                island_entity,
                island_entity.id == canonical_island.entity_id,
            )
            .where(self.island_conditions(island_entity, island))
            .limit(1)
        )
        return (await self.session.scalars(stmt)).first()


class LiveSnapshotRepository(
    _IslandLookupMixin,
    GenericRepository[LiveSnapshot],
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(LiveSnapshot, session)

    async def find_snapshot(
        self,
        *,
        resource: str,
        target: str,
    ) -> LiveSnapshot | None:
        stmt = (
            select(LiveSnapshot)
            .where(
                LiveSnapshot.resource == resource,
                LiveSnapshot.target == target,
            )
            .limit(1)
        )
        return (await self.session.scalars(stmt)).first()

    async def upsert_snapshot(
        self,
        *,
        resource: str,
        target: str,
        payload: dict[str, Any],
    ) -> None:
        island_id = (
            await self.island_entity_id(target)
            if target != "canarias"
            else None
        )
        stmt = pg_insert(LiveSnapshot).values(
            resource=resource,
            target=target,
            island_entity_id=island_id,
            available=payload.get("available"),
            status=payload.get("status"),
            source=payload.get("source"),
            source_updated_at=_as_datetime(payload.get("updated_at")),
            payload=payload,
            ingested_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                LiveSnapshot.resource,
                LiveSnapshot.target,
            ],
            set_={
                "island_entity_id": stmt.excluded.island_entity_id,
                "available": stmt.excluded.available,
                "status": stmt.excluded.status,
                "source": stmt.excluded.source,
                "source_updated_at": stmt.excluded.source_updated_at,
                "payload": stmt.excluded.payload,
                "ingested_at": func.now(),
            },
        )
        await self.session.execute(stmt)


class NewsItemRepository(
    _IslandLookupMixin,
    GenericRepository[NewsItem],
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(NewsItem, session)

    async def find_items(
        self,
        *,
        island: str | None,
        limit: int,
    ) -> list[NewsItem]:
        stmt = select(NewsItem).where(NewsItem.hidden.is_(False))

        if island is not None:
            island_entity = aliased(Entity)
            stmt = (
                stmt.outerjoin(
                    island_entity,
                    island_entity.id == NewsItem.island_entity_id,
                )
                .where(
                    or_(
                        NewsItem.island_entity_id.is_(None),
                        self.island_conditions(island_entity, island),
                    )
                )
            )

        stmt = (
            stmt.order_by(
                NewsItem.published_at.desc().nulls_last(),
                NewsItem.id.desc(),
            )
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())

    async def upsert_item(
        self,
        *,
        item: dict[str, Any],
    ) -> None:
        key = str(
            item.get("url")
            or item.get("id")
            or item.get("title")
            or ""
        ).strip()
        if not key:
            return

        island = str(item.get("island") or "").strip()
        island_id = await self.island_entity_id(island) if island else None

        stmt = pg_insert(NewsItem).values(
            news_key=key,
            island_entity_id=island_id,
            scope=item.get("scope"),
            title=str(item.get("title") or key),
            summary=item.get("summary"),
            image_url=item.get("image_url"),
            url=item.get("url"),
            published_at=_as_datetime(item.get("published_at")),
            source=item.get("source"),
            hidden=bool(item.get("hidden")),
            editorial_override=bool(item.get("editorial_override")),
            payload=item,
            created_at=func.now(),
            updated_at=func.now(),
        )
        updates = {
            "island_entity_id": stmt.excluded.island_entity_id,
            "scope": stmt.excluded.scope,
            "title": stmt.excluded.title,
            "summary": stmt.excluded.summary,
            "image_url": stmt.excluded.image_url,
            "url": stmt.excluded.url,
            "published_at": stmt.excluded.published_at,
            "source": stmt.excluded.source,
            "hidden": stmt.excluded.hidden,
            "editorial_override": stmt.excluded.editorial_override,
            "payload": stmt.excluded.payload,
            "updated_at": func.now(),
        }
        # Protect editor changes even if a refresh bypasses the batch worker.
        stmt = stmt.on_conflict_do_update(
            index_elements=[NewsItem.news_key],
            set_={
                key: case(
                    (NewsItem.editorial_override.is_(True), getattr(NewsItem, key)),
                    else_=value,
                )
                for key, value in updates.items()
            },
        )
        await self.session.execute(stmt)


class CalendarEventRepository(
    _IslandLookupMixin,
    GenericRepository[CalendarEvent],
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CalendarEvent, session)

    async def find_items(
        self,
        *,
        island: str,
        month: str,
        category: str | None,
        limit: int,
    ) -> list[CalendarEvent]:
        island_entity = aliased(Entity)
        stmt = (
            select(CalendarEvent)
            .join(
                island_entity,
                island_entity.id == CalendarEvent.island_entity_id,
            )
            .join(
                CalendarEventMonth,
                CalendarEventMonth.calendar_event_id == CalendarEvent.id,
            )
            .where(
                self.island_conditions(island_entity, island),
                CalendarEventMonth.month == month,
                CalendarEvent.hidden.is_(False),
            )
        )
        if category:
            stmt = stmt.where(CalendarEvent.category == category)

        stmt = (
            stmt.order_by(
                CalendarEvent.start_date.asc().nulls_last(),
                CalendarEvent.title.asc(),
            )
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())

    async def find_all_for_island(
        self,
        *,
        island: str,
    ) -> list[CalendarEvent]:
        island_entity = aliased(Entity)
        stmt = (
            select(CalendarEvent)
            .join(
                island_entity,
                island_entity.id == CalendarEvent.island_entity_id,
            )
            .where(
                self.island_conditions(island_entity, island),
                CalendarEvent.hidden.is_(False),
            )
            .order_by(
                CalendarEvent.start_date.desc().nulls_last(),
                CalendarEvent.title.asc(),
            )
        )
        return list((await self.session.scalars(stmt)).all())

    async def find_month_memberships(
        self,
        *,
        island: str,
    ) -> list[tuple[CalendarEvent, str]]:
        island_entity = aliased(Entity)
        stmt = (
            select(CalendarEvent, CalendarEventMonth.month)
            .join(
                island_entity,
                island_entity.id == CalendarEvent.island_entity_id,
            )
            .join(
                CalendarEventMonth,
                CalendarEventMonth.calendar_event_id == CalendarEvent.id,
            )
            .where(
                self.island_conditions(island_entity, island),
                CalendarEvent.hidden.is_(False),
            )
            .order_by(
                CalendarEventMonth.month.desc(),
                CalendarEvent.start_date.asc().nulls_last(),
                CalendarEvent.title.asc(),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return [(row[0], str(row[1])) for row in rows]

    async def upsert_item(
        self,
        *,
        island: str,
        month: str,
        item: dict[str, Any],
    ) -> None:
        event_key = str(
            item.get("id")
            or item.get("url")
            or (
                f"{item.get('title', '')}|"
                f"{item.get('start_date') or item.get('start_at') or ''}"
            )
        ).strip()
        if not event_key:
            return

        island_id = await self.island_entity_id(island)
        if island_id is None:
            raise ValueError(f"Unknown canonical island: {island}")

        values = {
            "island_entity_id": island_id,
            "event_key": event_key,
            "title": str(item.get("title") or event_key),
            "category": item.get("category"),
            "start_date": _as_date(item.get("start_date")),
            "end_date": _as_date(item.get("end_date")),
            "start_at": _as_datetime(item.get("start_at")),
            "end_at": _as_datetime(item.get("end_at")),
            "all_day": item.get("all_day"),
            "schedule_text": item.get("schedule_text"),
            "summary": item.get("summary"),
            "image_url": item.get("image_url"),
            "url": item.get("url"),
            "source": item.get("source"),
            "source_id": item.get("source_id"),
            "location_name": item.get("location_name"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "municipality": item.get("municipality"),
            "municipality_slug": item.get("municipality_slug"),
            "locality": item.get("locality"),
            "zone": item.get("zone"),
            "zone_name": item.get("zone_name"),
            "importance": item.get("importance"),
            "hidden": bool(item.get("hidden")),
            "editorial_override": bool(item.get("editorial_override")),
            "payload": item,
            "created_at": func.now(),
            "updated_at": func.now(),
        }

        stmt = pg_insert(CalendarEvent).values(**values)
        update_values = {
            key: getattr(stmt.excluded, key)
            for key in values
            if key not in {
                "island_entity_id",
                "event_key",
                "created_at",
            }
        }
        update_values["updated_at"] = func.now()
        # Keep editorial overrides, including hidden events. Still RETURN
        # the existing event id so new month membership can be recorded.
        update_values = {
            key: case(
                (CalendarEvent.editorial_override.is_(True), getattr(CalendarEvent, key)),
                else_=value,
            )
            for key, value in update_values.items()
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                CalendarEvent.island_entity_id,
                CalendarEvent.event_key,
            ],
            set_=update_values,
        )
        event_id = await self.session.scalar(
            stmt.returning(CalendarEvent.id)
        )
        if event_id is None:
            return

        membership = pg_insert(CalendarEventMonth).values(
            calendar_event_id=event_id,
            month=month,
            created_at=func.now(),
        )
        membership = membership.on_conflict_do_nothing(
            index_elements=[
                CalendarEventMonth.calendar_event_id,
                CalendarEventMonth.month,
            ]
        )
        await self.session.execute(membership)


class StatisticalSnapshotRepository(
    _IslandLookupMixin,
    GenericRepository[StatisticalSnapshot],
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(StatisticalSnapshot, session)

    async def find_snapshot(
        self,
        *,
        dataset: str,
        target: str,
    ) -> StatisticalSnapshot | None:
        stmt = (
            select(StatisticalSnapshot)
            .where(
                StatisticalSnapshot.dataset == dataset,
                StatisticalSnapshot.target == target,
            )
            .limit(1)
        )
        return (await self.session.scalars(stmt)).first()

    async def upsert_snapshot(
        self,
        *,
        dataset: str,
        target: str,
        payload: dict[str, Any],
        source: str | None = None,
    ) -> None:
        island_id = (
            await self.island_entity_id(target)
            if target != "canarias"
            else None
        )
        stmt = pg_insert(StatisticalSnapshot).values(
            dataset=dataset,
            target=target,
            island_entity_id=island_id,
            source=source or payload.get("source"),
            source_updated_at=_as_datetime(payload.get("updated_at")),
            payload=payload,
            ingested_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                StatisticalSnapshot.dataset,
                StatisticalSnapshot.target,
            ],
            set_={
                "island_entity_id": stmt.excluded.island_entity_id,
                "source": stmt.excluded.source,
                "source_updated_at": stmt.excluded.source_updated_at,
                "payload": stmt.excluded.payload,
                "ingested_at": func.now(),
            },
        )
        await self.session.execute(stmt)


class ClimateObservationRepository(
    _IslandLookupMixin,
    GenericRepository[ClimateObservation],
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ClimateObservation, session)

    async def find_observations(
        self,
        *,
        resource: str,
        island: str,
        since: datetime,
        point_id: str | None,
    ) -> list[ClimateObservation]:
        island_entity = aliased(Entity)
        stmt = (
            select(ClimateObservation)
            .join(
                island_entity,
                island_entity.id == ClimateObservation.island_entity_id,
            )
            .where(
                ClimateObservation.resource == resource,
                self.island_conditions(island_entity, island),
                ClimateObservation.observed_at >= since,
            )
        )
        if point_id:
            stmt = stmt.where(
                ClimateObservation.point_id == point_id
            )
        stmt = stmt.order_by(ClimateObservation.observed_at.asc())
        return list((await self.session.scalars(stmt)).all())

    async def upsert_observation(
        self,
        *,
        resource: str,
        island: str,
        point_id: str,
        observed_at: datetime,
        item: dict[str, Any],
    ) -> None:
        island_id = await self.island_entity_id(island)
        if island_id is None:
            raise ValueError(f"Unknown canonical island: {island}")

        stmt = pg_insert(ClimateObservation).values(
            resource=resource,
            island_entity_id=island_id,
            point_id=point_id,
            observed_at=observed_at,
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            source=item.get("source"),
            payload=item,
            ingested_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ClimateObservation.resource,
                ClimateObservation.island_entity_id,
                ClimateObservation.point_id,
                ClimateObservation.observed_at,
            ],
            set_={
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
                "source": stmt.excluded.source,
                "payload": stmt.excluded.payload,
                "ingested_at": func.now(),
            },
        )
        await self.session.execute(stmt)

    async def compact_history(
        self, *, resource: str, island: str, since: datetime,
        point_id: str | None = None, daily: bool = False,
    ) -> list[dict[str, Any]]:
        """Project only chart inputs; never load thousands of full ORM payloads."""
        island_entity = aliased(Entity)
        model = ClimateObservation
        fields = (
            ("temperature", "apparent_temperature", "humidity", "wind_speed", "precipitation")
            if resource == "weather" else ("pm10", "pm25", "dust", "aod")
        )
        observed = (
            func.date_trunc("day", model.observed_at, "UTC")
            if daily else model.observed_at
        )
        name = model.payload["name"].as_string()
        columns = [model.point_id, observed.label("observed_at")]
        for column, label in ((name, "name"), (model.latitude, "latitude"), (model.longitude, "longitude")):
            columns.append((func.max(column) if daily else column).label(label))
        for field in fields:
            value = model.payload[field].as_float()
            columns.append((func.avg(value) if daily else value).label(field))
        if daily:
            columns.append(func.count().label("samples"))
        stmt = select(*columns).join(island_entity, island_entity.id == model.island_entity_id).where(
            model.resource == resource, self.island_conditions(island_entity, island),
            model.observed_at >= since, model.observed_at <= datetime.now(timezone.utc),
        )
        if point_id:
            stmt = stmt.where(model.point_id == point_id)
        if daily:
            stmt = stmt.group_by(model.point_id, observed)
        stmt = stmt.order_by(observed, model.point_id)
        return [dict(row) for row in (await self.session.execute(stmt)).mappings()]

    async def bulk_upsert_observations(
        self,
        *,
        resource: str,
        island: str,
        items: list[dict[str, Any]],
        batch_size: int = 1000,
        overwrite: bool = True,
    ) -> int:
        if not items:
            return 0

        island_id = await self.island_entity_id(island)
        if island_id is None:
            raise ValueError(f"Unknown canonical island: {island}")

        written = 0
        for offset in range(0, len(items), batch_size):
            batch = items[offset:offset + batch_size]
            now = datetime.now(timezone.utc)
            rows: list[dict[str, Any]] = []

            for item in batch:
                point_id = str(item.get("point_id") or "").strip()
                observed_at = _as_datetime(item.get("observed_at"))
                if not point_id or observed_at is None:
                    continue

                rows.append(
                    {
                        "resource": resource,
                        "island_entity_id": island_id,
                        "point_id": point_id,
                        "observed_at": observed_at,
                        "latitude": item.get("latitude"),
                        "longitude": item.get("longitude"),
                        "source": item.get("source"),
                        "payload": item,
                        "ingested_at": now,
                    }
                )

            if not rows:
                continue

            stmt = pg_insert(ClimateObservation).values(rows)
            if not overwrite:
                # Existing imported values win. Backfill may add a previously
                # missing field (e.g. precipitation), never replace a known value.
                merged = func.jsonb_strip_nulls(stmt.excluded.payload).op("||")(
                    func.jsonb_strip_nulls(ClimateObservation.payload)
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[ClimateObservation.resource, ClimateObservation.island_entity_id,
                                    ClimateObservation.point_id, ClimateObservation.observed_at],
                    set_={"payload": merged},
                    where=ClimateObservation.payload.is_distinct_from(merged),
                )
                # psycopg may report rowcount=-1. RETURNING counts real inserts
                # or changed rows and reports zero for an idempotent replay.
                result = await self.session.execute(stmt.returning(ClimateObservation.id))
                written += len(result.scalars().all())
                continue
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    ClimateObservation.resource,
                    ClimateObservation.island_entity_id,
                    ClimateObservation.point_id,
                    ClimateObservation.observed_at,
                ],
                set_={
                    "latitude": stmt.excluded.latitude,
                    "longitude": stmt.excluded.longitude,
                    "source": stmt.excluded.source,
                    "payload": stmt.excluded.payload,
                    "ingested_at": stmt.excluded.ingested_at,
                },
            )
            await self.session.execute(stmt)
            written += len(rows)

        return written


class SeismicEventRepository(
    _IslandLookupMixin,
    GenericRepository[SeismicEvent],
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SeismicEvent, session)

    async def find_events(
        self,
        *,
        island: str | None,
        since: datetime,
    ) -> list[SeismicEvent]:
        stmt = select(SeismicEvent).where(
            SeismicEvent.occurred_at >= since
        )
        if island:
            island_entity = aliased(Entity)
            stmt = (
                stmt.join(
                    island_entity,
                    island_entity.id == SeismicEvent.island_entity_id,
                )
                .where(self.island_conditions(island_entity, island))
            )
        stmt = stmt.order_by(SeismicEvent.occurred_at.desc())
        return list((await self.session.scalars(stmt)).all())

    async def upsert_event(
        self,
        *,
        item: dict[str, Any],
    ) -> None:
        event_id = str(item.get("event_id") or "").strip()
        occurred_at = _as_datetime(item.get("occurred_at"))
        if not event_id or occurred_at is None:
            return

        island = str(item.get("island") or item.get("island_slug") or "").strip()
        island_id = await self.island_entity_id(island) if island else None

        stmt = pg_insert(SeismicEvent).values(
            event_id=event_id,
            island_entity_id=island_id,
            occurred_at=occurred_at,
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            depth_km=item.get("depth_km"),
            magnitude=item.get("magnitude"),
            magnitude_type=item.get("magnitude_type"),
            location=item.get("location"),
            source=item.get("source") or "IGN",
            source_url=item.get("source_url"),
            payload=item,
            ingested_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SeismicEvent.event_id],
            set_={
                "island_entity_id": func.coalesce(stmt.excluded.island_entity_id, SeismicEvent.island_entity_id),
                "occurred_at": stmt.excluded.occurred_at,
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
                "depth_km": func.coalesce(stmt.excluded.depth_km, SeismicEvent.depth_km),
                "magnitude": func.coalesce(stmt.excluded.magnitude, SeismicEvent.magnitude),
                "magnitude_type": func.coalesce(stmt.excluded.magnitude_type, SeismicEvent.magnitude_type),
                "location": stmt.excluded.location,
                "source": stmt.excluded.source,
                "source_url": stmt.excluded.source_url,
                "payload": stmt.excluded.payload,
                "ingested_at": func.now(),
            },
        )
        await self.session.execute(stmt)


class VolcanicReportRepository(GenericRepository[VolcanicReport]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(VolcanicReport, session)

    async def find_reports(
        self,
        *,
        limit: int,
    ) -> list[VolcanicReport]:
        stmt = (
            select(VolcanicReport)
            .order_by(
                VolcanicReport.last_seen_at.desc().nulls_last(),
                VolcanicReport.first_seen_at.desc().nulls_last(),
            )
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())

    async def upsert_report(
        self,
        *,
        report_id: str,
        item: dict[str, Any],
    ) -> None:
        stmt = pg_insert(VolcanicReport).values(
            report_id=report_id,
            period=item.get("period"),
            title=item.get("title"),
            summary=item.get("summary"),
            earthquakes_total=item.get("earthquakes_total"),
            max_magnitude=item.get("max_magnitude"),
            significant_deformation_detected=item.get(
                "significant_deformation_detected"
            ),
            source=item.get("source") or "IGN",
            source_url=item.get("source_url"),
            first_seen_at=_as_datetime(item.get("first_seen_at")),
            last_seen_at=_as_datetime(item.get("last_seen_at")),
            payload=item,
            ingested_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[VolcanicReport.report_id],
            set_={
                "period": stmt.excluded.period,
                "title": stmt.excluded.title,
                "summary": stmt.excluded.summary,
                "earthquakes_total": stmt.excluded.earthquakes_total,
                "max_magnitude": stmt.excluded.max_magnitude,
                "significant_deformation_detected":
                    stmt.excluded.significant_deformation_detected,
                "source": stmt.excluded.source,
                "source_url": stmt.excluded.source_url,
                "first_seen_at": func.coalesce(
                    VolcanicReport.first_seen_at,
                    stmt.excluded.first_seen_at,
                ),
                "last_seen_at": stmt.excluded.last_seen_at,
                "payload": stmt.excluded.payload,
                "ingested_at": func.now(),
            },
        )
        await self.session.execute(stmt)


def _as_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    return parsed


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
