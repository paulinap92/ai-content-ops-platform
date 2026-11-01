from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from canarias_site.db.base import Base


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = {"schema": "design"}

    id: Mapped[UUID] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str | None] = mapped_column(Text)
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False)
    merged_into_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("design.entities.id")
    )
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class Island(Base):
    __tablename__ = "islands"
    __table_args__ = {"schema": "design"}

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    province_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.provinces.entity_id"),
        nullable=False,
    )
    has_own_administration: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    administrative_parent_island_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("design.islands.entity_id")
    )


class Municipality(Base):
    __tablename__ = "municipalities"
    __table_args__ = {"schema": "design"}

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    province_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.provinces.entity_id"),
        nullable=False,
    )


class MunicipalityIsland(Base):
    __tablename__ = "municipality_islands"
    __table_args__ = {"schema": "design"}

    municipality_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.municipalities.entity_id"),
        primary_key=True,
    )
    island_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.islands.entity_id"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Place(Base):
    __tablename__ = "places"
    __table_args__ = {"schema": "design"}

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    place_kind: Mapped[str] = mapped_column(Text, nullable=False)


class NaturalFeature(Base):
    __tablename__ = "natural_features"
    __table_args__ = {"schema": "design"}

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    feature_kind: Mapped[str] = mapped_column(Text, nullable=False)


class ProtectedArea(Base):
    __tablename__ = "protected_areas"
    __table_args__ = {"schema": "design"}

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    protected_area_kind: Mapped[str] = mapped_column(Text, nullable=False)


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = {"schema": "design"}

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    route_kind: Mapped[str] = mapped_column(Text, nullable=False)


class EntityGeometry(Base):
    __tablename__ = "entity_geometries"
    __table_args__ = {"schema": "design"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        nullable=False,
    )
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326),
        nullable=False,
    )
    geometry_role: Mapped[str] = mapped_column(Text, nullable=False)
    is_canonical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = {"schema": "design"}

    id: Mapped[UUID] = mapped_column(primary_key=True)
    entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("design.entities.id")
    )
    island_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("design.islands.entity_id")
    )

    module: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str] = mapped_column(Text, nullable=False)
    content_key: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)

    source_url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    image_credit: Mapped[str | None] = mapped_column(Text)
    image_source_url: Mapped[str | None] = mapped_column(Text)

    featured: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sort_order: Mapped[int | None] = mapped_column(Integer)
    publication_status: Mapped[str] = mapped_column(Text, nullable=False)

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class EntityTerritory(Base):
    __tablename__ = "entity_territories"
    __table_args__ = {"schema": "design"}

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    territory_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    relation_type: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime]


class ExternalIdentifier(Base):
    __tablename__ = "external_identifiers"
    __table_args__ = {"schema": "design"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_code: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime]


class EntitySourceProperty(Base):
    __tablename__ = "entity_source_properties"
    __table_args__ = {"schema": "design"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_code: Mapped[str] = mapped_column(Text, nullable=False)
    properties_json: Mapped[dict[str, Any]] = mapped_column(
        "properties",
        JSONB,
        nullable=False,
    )
    source_updated_at: Mapped[datetime | None]
    ingested_at: Mapped[datetime]


class EntityCatalogMembership(Base):
    __tablename__ = "entity_catalog_memberships"
    __table_args__ = {"schema": "design"}

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.entities.id"),
        primary_key=True,
    )
    catalog_code: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class LiveSnapshot(Base):
    __tablename__ = "live_snapshots"
    __table_args__ = (
        UniqueConstraint("resource", "target"),
        {"schema": "design"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    island_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("design.islands.entity_id")
    )
    available: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClimateObservation(Base):
    __tablename__ = "climate_observations"
    __table_args__ = (
        UniqueConstraint(
            "resource",
            "island_entity_id",
            "point_id",
            "observed_at",
        ),
        {"schema": "design"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    island_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.islands.entity_id"),
        nullable=False,
    )
    point_id: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SeismicEvent(Base):
    __tablename__ = "seismic_events"
    __table_args__ = {"schema": "design"}

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    island_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("design.islands.entity_id")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    depth_km: Mapped[float | None] = mapped_column(Float)
    magnitude: Mapped[float | None] = mapped_column(Float)
    magnitude_type: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VolcanicReport(Base):
    __tablename__ = "volcanic_reports"
    __table_args__ = {"schema": "design"}

    report_id: Mapped[str] = mapped_column(Text, primary_key=True)
    period: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    earthquakes_total: Mapped[int | None] = mapped_column(Integer)
    max_magnitude: Mapped[float | None] = mapped_column(Float)
    significant_deformation_detected: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NewsItem(Base):
    __tablename__ = "news_items"
    __table_args__ = (
        UniqueConstraint("news_key"),
        {"schema": "design"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    news_key: Mapped[str] = mapped_column(Text, nullable=False)
    island_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("design.islands.entity_id")
    )
    scope: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False)
    editorial_override: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint("island_entity_id", "event_key"),
        {"schema": "design"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    island_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("design.islands.entity_id"),
        nullable=False,
    )
    event_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[Any | None] = mapped_column(Date)
    end_date: Mapped[Any | None] = mapped_column(Date)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool | None] = mapped_column(Boolean)
    schedule_text: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(Text)
    location_name: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    municipality: Mapped[str | None] = mapped_column(Text)
    municipality_slug: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(Text)
    zone: Mapped[str | None] = mapped_column(Text)
    zone_name: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[str | None] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False)
    editorial_override: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CalendarEventMonth(Base):
    __tablename__ = "calendar_event_months"
    __table_args__ = {"schema": "design"}

    calendar_event_id: Mapped[int] = mapped_column(
        ForeignKey("design.calendar_events.id"),
        primary_key=True,
    )
    month: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class StatisticalSnapshot(Base):
    __tablename__ = "statistical_snapshots"
    __table_args__ = (
        UniqueConstraint("dataset", "target"),
        {"schema": "design"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dataset: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    island_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("design.islands.entity_id")
    )
    source: Mapped[str | None] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

