"""Catalog constants and identities; no JSON writers or source loaders."""
import hashlib
from typing import Any
from canarias_site.services.identity import feature_key

EXPLORE_RESOURCES = (
    "places", "beaches", "natural-pools", "marinas", "food-producers",
    "diving-spots", "leisure-centers", "museums-visits", "natural-spaces",
    "surf-spots", "stargazing", "markets", "volcanoes", "summits",
    "routes", "fauna", "flora",
)


LIVE_RESOURCES = ("weather", "air-quality", "marine", "tides", "alerts", "seismic", "volcanic", "webcams")


class AdminEditorError(ValueError):
    pass


def _key(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _feature_identity(feature: dict[str, Any]) -> str:
    return feature_key(feature)


def _flatten_feature(feature: dict[str, Any]) -> dict[str, Any]:
    props = dict(feature.get("properties") or {})
    geometry = dict(feature.get("geometry") or {})
    identity = _feature_identity(feature)
    result = {**props, "_editor_key": _key(identity), "_identity": identity, "_geometry_type": geometry.get("type")}
    coords = geometry.get("coordinates")
    if geometry.get("type") == "Point" and isinstance(coords, list) and len(coords) >= 2:
        result["longitude"], result["latitude"] = coords[0], coords[1]
    return result

