from __future__ import annotations

from typing import Any, Iterable


# west, south, east, north
ISLAND_BBOXES: dict[str, tuple[float, float, float, float]] = {
    "el-hierro": (-18.20, 27.55, -17.80, 27.90),
    "la-palma": (-18.05, 28.40, -17.65, 28.90),
    "la-gomera": (-17.40, 27.95, -17.00, 28.25),
    "tenerife": (-16.95, 27.95, -16.05, 28.65),
    "gran-canaria": (-15.90, 27.70, -15.25, 28.25),
    "fuerteventura": (-14.55, 27.95, -13.70, 28.80),
    "lanzarote": (-13.95, 28.80, -13.35, 29.30),
    "la-graciosa": (-13.60, 29.18, -13.45, 29.32),
}

VALID_ISLANDS = tuple(ISLAND_BBOXES.keys())


LA_GRACIOSA_POLYGON: tuple[tuple[float, float], ...] = (
    (-13.590, 29.240),
    (-13.580, 29.290),
    (-13.520, 29.310),
    (-13.460, 29.280),
    (-13.460, 29.245),
    (-13.490, 29.215),
    (-13.510, 29.190),
    (-13.560, 29.190),
)

# La Gomera is close to round but its bbox has large sea-only corners.  This
# conservative outline prevents imported bbox points from appearing offshore.
LA_GOMERA_POLYGON: tuple[tuple[float, float], ...] = (
    (-17.365, 28.145),
    (-17.340, 28.205),
    (-17.255, 28.220),
    (-17.165, 28.190),
    (-17.095, 28.135),
    (-17.090, 28.075),
    (-17.155, 28.025),
    (-17.245, 28.015),
    (-17.325, 28.045),
    (-17.365, 28.105),
)


def _point_in_polygon(
    longitude: float,
    latitude: float,
    polygon: tuple[tuple[float, float], ...],
) -> bool:
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        crosses = (yi > latitude) != (yj > latitude)
        if crosses:
            x_intersection = (xj - xi) * (latitude - yi) / (yj - yi) + xi
            if longitude < x_intersection:
                inside = not inside
        j = i
    return inside


def normalize_island(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = (
        value.strip()
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
    )

    aliases = {
        "grancanaria": "gran-canaria",
        "lapalma": "la-palma",
        "lagomera": "la-gomera",
        "elhierro": "el-hierro",
        "lagraciosa": "la-graciosa",
    }

    normalized = aliases.get(cleaned, cleaned)
    return normalized if normalized in ISLAND_BBOXES else None


def bbox_for_island(island: str) -> tuple[float, float, float, float]:
    normalized = normalize_island(island)
    if normalized is None:
        raise ValueError(f"Unknown island: {island}")
    return ISLAND_BBOXES[normalized]


def overpass_bbox(island: str | None) -> str:
    """Return south,west,north,east for Overpass queries."""
    if island is None:
        return "27.5,-18.3,29.5,-13.2"

    normalized = normalize_island(island)
    if normalized is None:
        return "27.5,-18.3,29.5,-13.2"

    west, south, east, north = ISLAND_BBOXES[normalized]
    return f"{south},{west},{north},{east}"


def _iter_coords(
    geometry: dict[str, Any],
) -> Iterable[tuple[float, float]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if coordinates is None:
        return

    if geometry_type == "Point":
        if len(coordinates) >= 2:
            yield float(coordinates[0]), float(coordinates[1])

    elif geometry_type == "LineString":
        for point in coordinates:
            if len(point) >= 2:
                yield float(point[0]), float(point[1])

    elif geometry_type == "MultiLineString":
        for line in coordinates:
            for point in line:
                if len(point) >= 2:
                    yield float(point[0]), float(point[1])


def geometry_center(
    geometry: dict[str, Any],
) -> tuple[float, float] | None:
    points = list(_iter_coords(geometry))
    if not points:
        return None

    longitude = sum(x for x, _ in points) / len(points)
    latitude = sum(y for _, y in points) / len(points)
    return longitude, latitude


def point_is_on_island(
    longitude: float,
    latitude: float,
    island: str,
) -> bool:
    normalized = normalize_island(island)
    if normalized is None:
        return False

    west, south, east, north = ISLAND_BBOXES[normalized]
    inside = west <= longitude <= east and south <= latitude <= north
    if not inside:
        return False

    on_graciosa = _point_in_polygon(longitude, latitude, LA_GRACIOSA_POLYGON)
    if normalized == "la-graciosa":
        return on_graciosa
    if normalized == "lanzarote" and on_graciosa:
        return False
    if normalized == "la-gomera":
        return _point_in_polygon(longitude, latitude, LA_GOMERA_POLYGON)

    return True


def filter_feature_collection_by_island(
    data: dict[str, Any],
    island: str | None,
) -> dict[str, Any]:
    if island is None:
        return data

    normalized = normalize_island(island)
    if normalized is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "filter": {"island": island, "valid": False},
        }

    features = []
    for feature in data.get("features", []):
        center = geometry_center(feature.get("geometry") or {})
        if center is None:
            continue
        longitude, latitude = center
        if point_is_on_island(longitude, latitude, normalized):
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
        "filter": {"island": normalized, "valid": True},
    }


def filter_records_by_island(
    records: list[dict[str, Any]],
    island: str | None,
    *,
    include_regional: bool = False,
) -> list[dict[str, Any]]:
    if island is None:
        return records

    normalized = normalize_island(island)
    if normalized is None:
        return []

    result = []
    for record in records:
        record_island = normalize_island(record.get("island"))
        if record_island == normalized:
            result.append(record)
        elif include_regional and record.get("island") is None:
            result.append(record)

    return result

