"""Transactional, additive import into the canonical Explore model.

Caller owns the transaction. No commits, filesystem writes, or remote fetches.
Existing canonical rows, inactive memberships and editorial overrides win.
"""

from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from canarias_site.utils.islands import normalize_island

RESOURCES = (
    "places",
    "beaches",
    "routes",
    "fauna",
    "flora",
    "natural-pools",
    "marinas",
    "food-producers",
    "diving-spots",
    "leisure-centers",
    "museums-visits",
    "natural-spaces",
    "surf-spots",
    "stargazing",
    "markets",
    "volcanoes",
    "summits",
)
IMPORT_PROVIDER = "canarias-cerca-legacy"
EDITOR_PROVIDER = "canarias-cerca-editorial"


class ExploreImportError(ValueError):
    pass


def catalog_for(resource: str) -> str:
    if resource not in RESOURCES:
        raise ExploreImportError(f"Unknown Explore resource: {resource}")
    return "explore_" + resource.replace("-", "_")


def records(payload: dict) -> list[dict]:
    value = payload.get("records", [])
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def feature_id(feature: dict) -> str:
    p = feature.get("properties") or {}
    value = p.get("id") or p.get("route_id") or feature.get("id")
    if value is None or not str(value).strip():
        osm = osm_identity(p)
        if osm:
            return osm
        if p.get("gbif_id") is not None:
            return f"gbif:{p['gbif_id']}"
        raise ExploreImportError("Feature has no stable source identifier")
    return str(value)


def osm_identity(p: dict) -> str | None:
    raw = str(p.get("id") or "")
    match = re.fullmatch(r"osm[:/](node|way|relation)[:/](\d+)", raw)
    if match:
        return f"osm:{match[1]}:{match[2]}"
    kind, value = p.get("osm_type"), p.get("osm_id")
    if kind in {"node", "way", "relation"} and re.fullmatch(r"\d+", str(value)):
        return f"osm:{kind}:{value}"
    return None


def validate_feature(feature: dict, island: str, resource: str) -> dict:
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise ExploreImportError("Expected GeoJSON Feature")
    f = deepcopy(feature)
    p = f.get("properties")
    if not isinstance(p, dict):
        raise ExploreImportError("Feature properties must be an object")
    if p.get("island") is not None and normalize_island(p["island"]) != island:
        raise ExploreImportError("Feature island conflicts with source file")
    p["island"] = island
    for flag in ("hidden", "editorial_override", "featured"):
        if flag in p and not isinstance(p[flag], bool):
            raise ExploreImportError(f"{flag} must be boolean")
    p.setdefault("id", feature_id(f))
    name = p.get("name") or p.get("common_name") or p.get("scientific_name") or p.get("species")
    if not isinstance(name, str) or not name.strip():
        raise ExploreImportError(f"{p['id']}: missing name")
    p.setdefault("name", name.strip())
    g = f.get("geometry")
    if g is None and resource in {"fauna", "flora"}:
        return f  # Species can exist without a fabricated point.
    if not isinstance(g, dict):
        raise ExploreImportError(f"{p['id']}: missing real geometry")
    kind = g.get("type")
    if kind not in {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
    }:
        raise ExploreImportError(f"Unsupported geometry: {kind}")
    if resource == "routes" and kind not in {"LineString", "MultiLineString"}:
        raise ExploreImportError("Routes require real line geometry")

    def check(coords, depth):
        if not isinstance(coords, list) or not coords:
            raise ExploreImportError("Empty or malformed geometry coordinates")
        if depth:
            for item in coords:
                check(item, depth - 1)
        elif (
            len(coords) < 2
            or not all(
                isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
                for v in coords
            )
            or not (-180 <= coords[0] <= 180 and -90 <= coords[1] <= 90)
        ):
            raise ExploreImportError("Invalid geometry coordinate")

    check(
        g.get("coordinates"),
        {
            "Point": 0,
            "MultiPoint": 1,
            "LineString": 1,
            "MultiLineString": 2,
            "Polygon": 2,
            "MultiPolygon": 3,
        }[kind],
    )
    return f


@dataclass
class ImportResult:
    created: int = 0
    matched: int = 0
    imported: int = 0


class ExploreImporter:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def island_id(self, island: str) -> UUID:
        if normalize_island(island) != island:
            raise ExploreImportError(f"Invalid island: {island}")
        rows = (
            (
                await self.session.execute(
                    text("""
            SELECT e.id FROM design.entities e JOIN design.islands i ON i.entity_id=e.id
            WHERE e.lifecycle_status='active' AND
              (lower(e.slug)=:island OR lower(e.slug) LIKE :pattern
               OR lower(e.canonical_name)=:name)
        """),
                    {
                        "island": island,
                        "pattern": f"island-{island}-%",
                        "name": island.replace("-", " "),
                    },
                )
            )
            .scalars()
            .all()
        )
        if len(rows) != 1:
            raise ExploreImportError(f"Expected one canonical island: {island}")
        return rows[0]

    async def resolve(self, entity_id: UUID) -> UUID:
        seen = set()
        while entity_id not in seen:
            seen.add(entity_id)
            row = (
                (
                    await self.session.execute(
                        text("""
                SELECT lifecycle_status, merged_into_entity_id
                FROM design.entities WHERE id=:id FOR UPDATE
            """),
                        {"id": entity_id},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ExploreImportError(f"Missing canonical entity: {entity_id}")
            if row["merged_into_entity_id"] is not None:
                entity_id = row["merged_into_entity_id"]
            elif row["lifecycle_status"] == "active":
                return entity_id
            else:
                raise ExploreImportError(f"Inactive canonical entity: {entity_id}")
        raise ExploreImportError("Cycle in canonical merge lineage")

    async def match(self, feature: dict, catalog: str, island: str, island_id: UUID) -> UUID | None:
        p = feature["properties"]
        identity = feature_id(feature)
        gbif = (
            str(p["gbif_id"])
            if p.get("gbif_id") is not None
            else (identity.removeprefix("gbif:") if identity.startswith("gbif:") else None)
        )
        candidates: set[UUID] = set()
        if p.get("canonical_id"):
            try:
                candidates.add(UUID(str(p["canonical_id"])))
            except ValueError as exc:
                raise ExploreImportError("Invalid canonical_id") from exc
        # Stable legacy IDs are scoped to catalog and island; OSM is typed and global.
        matches = (
            (
                await self.session.execute(
                    text("""
            SELECT entity_id FROM design.external_identifiers
            WHERE (provider=:provider AND dataset_code=:catalog AND external_id=:key)
               OR (lower(provider) IN ('openstreetmap','osm') AND external_id=ANY(:osm_ids))
               OR (lower(provider)='gbif' AND external_id=:gbif)
            UNION
            SELECT esp.entity_id FROM design.entity_source_properties esp
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof(esp.properties->'records')='array'
                THEN esp.properties->'records' ELSE '[]'::jsonb END
            ) r
            WHERE (esp.dataset_code=:catalog
                AND COALESCE(r->'properties'->>'id',r->>'id')=:identity
                AND (r->'properties'->>'island'=:island OR EXISTS (
                    SELECT 1 FROM design.entity_territories et
                    WHERE et.entity_id=esp.entity_id AND et.territory_entity_id=:island_id)))
                OR (CAST(:osm AS text) IS NOT NULL AND (
                    r->'properties'->>'id'=:osm OR
                    ('osm:' || (r->'properties'->>'osm_type') || ':' ||
                     (r->'properties'->>'osm_id'))=:osm))
                OR (CAST(:gbif AS text) IS NOT NULL AND r->'properties'->>'gbif_id'=:gbif)
        """),
                    {
                        "provider": IMPORT_PROVIDER,
                        "catalog": catalog,
                        "key": f"{island}:{identity}",
                        "identity": identity,
                        "island": island,
                        "island_id": island_id,
                        "osm": osm_identity(p),
                        "osm_ids": self.osm_aliases(p),
                        "gbif": gbif,
                    },
                )
            )
            .scalars()
            .all()
        )
        candidates.update(matches)
        if not candidates and osm_identity(p):
            untyped = await self.session.scalar(
                text("""
                SELECT count(*) FROM design.external_identifiers
                WHERE lower(provider) IN ('openstreetmap','osm') AND external_id=:number
            """),
                {"number": osm_identity(p).rsplit(":", 1)[1]},
            )
            if untyped:
                raise ExploreImportError(
                    f"Untyped OSM identifier requires review, refusing to duplicate: {identity}"
                )
        resolved = {await self.resolve(value) for value in sorted(candidates, key=str)}
        if len(resolved) > 1:
            raise ExploreImportError(f"Ambiguous canonical match: {catalog}/{island}/{identity}")
        if resolved:
            return resolved.pop()
        # Conservative fallback: same catalog, same island and same name. Ambiguity
        # requires review; do not silently create a second canonical entity.
        names = (
            (
                await self.session.execute(
                    text("""
            SELECT DISTINCT e.id FROM design.entities e
            JOIN design.entity_catalog_memberships cm ON cm.entity_id=e.id
            JOIN design.entity_territories et ON et.entity_id=e.id
            WHERE cm.catalog_code=:catalog AND et.territory_entity_id=:island_id
              AND lower(trim(e.canonical_name))=lower(trim(:name))
        """),
                    {"catalog": catalog, "island_id": island_id, "name": p["name"]},
                )
            )
            .scalars()
            .all()
        )
        resolved = {await self.resolve(value) for value in sorted(names, key=str)}
        nearby = set()
        for candidate in resolved:
            geometry = feature.get("geometry")
            if geometry is not None:
                distance = await self.session.scalar(
                    text("""
                    SELECT min(ST_Distance(geom::geography,
                        ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)::geography))
                    FROM design.entity_geometries WHERE entity_id=:id
                """),
                    {"geometry": json.dumps(geometry), "id": candidate},
                )
                if distance is not None and distance <= 100:
                    nearby.add(candidate)
        if len(nearby) > 1:
            raise ExploreImportError(f"Ambiguous same-name nearby entities: {identity}")
        if nearby:
            return nearby.pop()
        return None

    @staticmethod
    def osm_aliases(p: dict) -> list[str]:
        osm = osm_identity(p)
        if osm is None:
            return []
        _, kind, value = osm.split(":")
        return [osm, f"{kind}:{value}", f"{kind}/{value}"]

    async def import_feature(self, feature: dict, resource: str, island: str) -> tuple[UUID, bool]:
        # Share the strict catalog importer's lock so both maintenance entry
        # points resolve identities against a current transaction snapshot.
        await self.session.execute(text("SELECT pg_advisory_xact_lock(1750261027)"))
        catalog = catalog_for(resource)
        island_id = await self.island_id(island)
        f = validate_feature(feature, island, resource)
        p = f["properties"]
        entity_id = await self.match(f, catalog, island, island_id)
        created = entity_id is None
        if created:
            entity_id = uuid4()
            # Reuse the deployed catalog's entity type where possible.
            entity_type = await self.session.scalar(
                text("""
                SELECT e.entity_type FROM design.entities e
                JOIN design.entity_catalog_memberships cm ON cm.entity_id=e.id
                WHERE cm.catalog_code=:catalog GROUP BY e.entity_type
                ORDER BY count(*) DESC,e.entity_type LIMIT 1
            """),
                {"catalog": catalog},
            )
            entity_type = entity_type or (
                "route"
                if resource == "routes"
                else "taxon"
                if resource in {"fauna", "flora"}
                else "natural_feature"
                if resource in {"beaches", "natural-pools", "volcanoes", "summits"}
                else "place"
            )
            await self.session.execute(
                text("""
                INSERT INTO design.entities(id,entity_type,canonical_name,slug,lifecycle_status,created_at,updated_at)
                VALUES (:id,:type,:name,:slug,'active',now(),now())
            """),
                {
                    "id": entity_id,
                    "type": entity_type,
                    "name": p["name"],
                    "slug": f"cc-{resource}-{island}-{entity_id}",
                },
            )
            subtype = {
                "place": ("places", "place_kind", "point_of_interest"),
                "natural_feature": ("natural_features", "feature_kind", "natural_feature"),
                "route": ("routes", "route_kind", "walking"),
                "protected_area": ("protected_areas", "protected_area_kind", "protected_area"),
            }.get(entity_type)
            if subtype:
                table, column, fallback = subtype
                kind = await self.session.scalar(
                    text(f"""
                    SELECT s.{column} FROM design.{table} s
                    JOIN design.entity_catalog_memberships cm ON cm.entity_id=s.entity_id
                    WHERE cm.catalog_code=:catalog GROUP BY s.{column}
                    ORDER BY count(*) DESC,s.{column} LIMIT 1
                """),
                    {"catalog": catalog},
                )
                await self.session.execute(
                    text(f"INSERT INTO design.{table}(entity_id,{column}) VALUES (:id,:kind)"),
                    {"id": entity_id, "kind": kind or p.get("category") or fallback},
                )
        # Inactive membership is an editorial tombstone, never reactivate it.
        await self.session.execute(
            text("""
            INSERT INTO design.entity_catalog_memberships(entity_id,catalog_code,is_active,created_at,updated_at)
            VALUES (:id,:catalog,true,now(),now()) ON CONFLICT DO NOTHING
        """),
            {"id": entity_id, "catalog": catalog},
        )
        other_islands = (
            (
                await self.session.execute(
                    text("""
            SELECT et.territory_entity_id FROM design.entity_territories et
            JOIN design.islands i ON i.entity_id=et.territory_entity_id
            WHERE et.entity_id=:id AND et.territory_entity_id<>:island
        """),
                    {"id": entity_id, "island": island_id},
                )
            )
            .scalars()
            .all()
        )
        # Species may have populations on several islands; a POI/route may not.
        if other_islands and resource not in {"fauna", "flora"}:
            raise ExploreImportError(f"Canonical island conflict: {feature_id(f)}")
        await self.session.execute(
            text("""
            INSERT INTO design.entity_territories(entity_id,territory_entity_id,relation_type,is_primary,created_at)
            SELECT :id,:island,'located_in',true,now()
            WHERE NOT EXISTS (SELECT 1 FROM design.entity_territories
                WHERE entity_id=:id AND territory_entity_id=:island)
        """),
            {"id": entity_id, "island": island_id},
        )
        g = f.get("geometry")
        if g is not None:
            valid = await self.session.scalar(
                text("""
                SELECT NOT ST_IsEmpty(g) AND ST_IsValid(g) FROM
                (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326) g) q
            """),
                {"geometry": json.dumps(g)},
            )
            if not valid:
                raise ExploreImportError(f"Invalid PostGIS geometry: {feature_id(f)}")
            await self.session.execute(
                text("""
                INSERT INTO design.entity_geometries(entity_id,geom,geometry_role,is_canonical,source_name,created_at,updated_at)
                SELECT :id,ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326),'primary',true,:source,now(),now()
                WHERE NOT EXISTS (SELECT 1 FROM design.entity_geometries WHERE entity_id=:id)
            """),
                {"id": entity_id, "geometry": json.dumps(g), "source": IMPORT_PROVIDER},
            )
        await self.save_record(entity_id, catalog, f)
        await self.session.execute(
            text("""
            INSERT INTO design.external_identifiers(entity_id,provider,dataset_code,external_id,source_label,created_at)
            SELECT :id,:provider,:catalog,:key,:provider,now() WHERE NOT EXISTS (
                SELECT 1 FROM design.external_identifiers WHERE provider=:provider
                    AND dataset_code=:catalog AND external_id=:key)
        """),
            {
                "id": entity_id,
                "provider": IMPORT_PROVIDER,
                "catalog": catalog,
                "key": f"{island}:{feature_id(f)}",
            },
        )
        return entity_id, created

    async def save_record(self, entity_id: UUID, catalog: str, feature: dict, *, editorial=False):
        provider = EDITOR_PROVIDER if editorial else IMPORT_PROVIDER
        rows = (
            (
                await self.session.execute(
                    text("""
            SELECT id,properties FROM design.entity_source_properties
            WHERE entity_id=:id AND provider=:provider AND dataset_code=:catalog FOR UPDATE
        """),
                    {"id": entity_id, "provider": provider, "catalog": catalog},
                )
            )
            .mappings()
            .all()
        )
        if len(rows) > 1:
            raise ExploreImportError("Duplicate canonical source rows need review")
        document = deepcopy(rows[0]["properties"]) if rows else {}
        old_records = records(document)
        key = (feature_id(feature), feature["properties"].get("island"))
        replaced = False
        for index, old in enumerate(old_records):
            if (feature_id(old), (old.get("properties") or {}).get("island")) == key:
                # Existing SQL editorial corrections always win over reimports.
                if editorial or not (old.get("properties") or {}).get("editorial_override"):
                    old_records[index] = feature
                replaced = True
        if not replaced:
            old_records.append(feature)
        document["records"] = old_records
        params = {
            "id": entity_id,
            "provider": provider,
            "catalog": catalog,
            "payload": json.dumps(document, ensure_ascii=False),
        }
        if rows:
            params["row_id"] = rows[0]["id"]
            await self.session.execute(
                text("""
                UPDATE design.entity_source_properties SET properties=CAST(:payload AS jsonb),ingested_at=now()
                WHERE id=:row_id AND properties IS DISTINCT FROM CAST(:payload AS jsonb)
            """),
                params,
            )
        else:
            await self.session.execute(
                text("""
                INSERT INTO design.entity_source_properties(entity_id,provider,dataset_code,properties,source_updated_at,ingested_at)
                VALUES (:id,:provider,:catalog,CAST(:payload AS jsonb),NULL,now())
            """),
                params,
            )

