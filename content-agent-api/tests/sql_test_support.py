"""Synthetic schema/fixtures for a disposable PostgreSQL + PostGIS database only."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import Column, ForeignKey, Table, Uuid, create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url

from canarias_site.db.base import Base
from canarias_site.models import design_db as m
from canarias_site.services.explore_import import RESOURCES
from canarias_site.utils.islands import VALID_ISLANDS
def check_import_database(url):
    parsed = make_url(url)
    if parsed.host not in {"jobdb", "localhost", "127.0.0.1", "::1"} or parsed.database != "canarias_cerca_jobs_test":
        raise RuntimeError("Only the disposable canarias_cerca_jobs_test database is permitted")


def uid(value: str):
    return uuid5(NAMESPACE_URL, "cc-isolated-fixture/" + value)


def initialize(url: str) -> None:
    check_import_database(url)
    # The test schema complements ORM metadata, never a production migration.
    if "design.provinces" not in Base.metadata.tables:
        Table(
            "provinces",
            Base.metadata,
            Column("entity_id", Uuid, ForeignKey("design.entities.id"), primary_key=True),
            schema="design",
        )
    engine = create_engine(make_url(url).set(drivername="postgresql+psycopg"))
    now = datetime.now(UTC)
    with engine.begin() as c:
        assert c.scalar(text("SELECT current_database()")) == "canarias_cerca_jobs_test"
        c.execute(text("CREATE SCHEMA IF NOT EXISTS design"))
        c.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        Base.metadata.create_all(c)
        # Existing worker smoke tests use these dedicated snapshot/state tables.
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS design.cc_legacy_monuments (sort_order integer PRIMARY KEY, payload jsonb NOT NULL)"
            )
        )
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS design.cc_cities (slug text PRIMARY KEY, sort_order integer NOT NULL, payload jsonb NOT NULL)"
            )
        )
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS design.cc_worker_fence (id integer PRIMARY KEY, generation bigint NOT NULL)"
            )
        )
        c.execute(text("INSERT INTO design.cc_worker_fence VALUES (1,0) ON CONFLICT DO NOTHING"))
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS design.cc_worker_state (name text PRIMARY KEY, payload jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS design.cc_titsa_stops (stop_id text PRIMARY KEY, stop_name text, stop_code text, latitude double precision NOT NULL, longitude double precision NOT NULL, sort_order integer NOT NULL)"
            )
        )
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS design.cc_titsa_routes (route_id text PRIMARY KEY, short_name text, long_name text, route_type text, route_color text, route_text_color text, features jsonb NOT NULL DEFAULT '[]', sort_order integer NOT NULL)"
            )
        )
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS design.cc_tilp_snapshot (snapshot_key text PRIMARY KEY, payload jsonb NOT NULL, imported_at timestamptz NOT NULL DEFAULT now())"
            )
        )

        c.execute(
            text(
                "INSERT INTO design.cc_worker_state (name,payload) VALUES ('sources','{}'),('plans','{\"plans\":{}}') ON CONFLICT DO NOTHING"
            )
        )

        def add(model, **values):
            c.execute(insert(model).values(**values).on_conflict_do_nothing())

        def entity(key, kind, name, slug=None):
            entity_id = uid(key)
            add(
                m.Entity,
                id=entity_id,
                entity_type=kind,
                canonical_name=name,
                slug=slug or key,
                lifecycle_status="active",
                created_at=now,
                updated_at=now,
            )
            return entity_id

        province_id = entity("province", "province", "Test province")
        c.execute(
            insert(Base.metadata.tables["design.provinces"])
            .values(entity_id=province_id)
            .on_conflict_do_nothing()
        )
        for island in VALID_ISLANDS:
            island_id = entity(
                "island/" + island, "island", island.replace("-", " ").title(), island
            )
            add(m.Island, entity_id=island_id, province_id=province_id, has_own_administration=True)
            for resource in RESOURCES:
                catalog = "explore_" + resource.replace("-", "_")
                kind = "route" if resource == "routes" else "place"
                key = resource + "/" + island
                entity_id = entity(key, kind, "SQL test " + resource + " " + island)
                add(
                    m.EntityCatalogMembership,
                    entity_id=entity_id,
                    catalog_code=catalog,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                add(
                    m.EntityTerritory,
                    entity_id=entity_id,
                    territory_entity_id=island_id,
                    relation_type="located_in",
                    is_primary=True,
                    created_at=now,
                )
                if resource == "routes":
                    add(m.Route, entity_id=entity_id, route_kind="hiking")
                    geo = "LINESTRING(-16.5 28.2,-16.4 28.3)"
                else:
                    add(
                        m.Place,
                        entity_id=entity_id,
                        place_kind="town" if resource == "places" else resource,
                    )
                    geo = "POINT(-16.5 28.2)"
                if not c.scalar(
                    text("SELECT 1 FROM design.entity_geometries WHERE entity_id=:id"),
                    {"id": entity_id},
                ):
                    c.execute(
                        text(
                            "INSERT INTO design.entity_geometries (entity_id, geom, geometry_role, is_canonical, source_name, created_at, updated_at) VALUES (:id,ST_GeomFromText(:geo,4326),'primary',true,'synthetic test',now(),now())"
                        ),
                        {"id": entity_id, "geo": geo},
                    )
                if not c.scalar(
                    text("SELECT 1 FROM design.entity_source_properties WHERE entity_id=:id"),
                    {"id": entity_id},
                ):
                    add(
                        m.EntitySourceProperty,
                        entity_id=entity_id,
                        provider="synthetic-test",
                        dataset_code=catalog,
                        properties_json={
                            "records": [
                                {
                                    "properties": {
                                        "id": key,
                                        "name": "SQL test " + resource,
                                        "category": "town",
                                        "island": island,
                                    }
                                }
                            ]
                        },
                        ingested_at=now,
                    )
            for resource in ("weather", "marine", "tides", "alerts", "seismic"):
                payload = {
                    "island": island,
                    "status": "ok",
                    "available": True,
                    "points": [],
                    "items": [],
                    "type": "FeatureCollection",
                    "features": [],
                }
                if resource == "seismic":
                    payload.update(
                        source="IGN", window_days=10, source_url="https://example.invalid/get10dias"
                    )
                add(
                    m.LiveSnapshot,
                    resource=resource,
                    target=island,
                    island_entity_id=island_id,
                    payload=payload,
                    available=True,
                    status="ok",
                    ingested_at=now,
                )
            add(
                m.ContentItem,
                id=uid("guide/" + island),
                island_entity_id=island_id,
                module="guide",
                section="history",
                content_key="synthetic",
                language="es",
                title="Synthetic history",
                slug="synthetic-history",
                featured=False,
                publication_status="published",
                metadata_json={},
                created_at=now,
                updated_at=now,
            )
    engine.dispose()

