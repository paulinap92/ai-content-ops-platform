from typing import Any

def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().strip().split())


def _feature_key(feature: dict[str, Any]) -> str:
    p = feature.get("properties") or {}
    for candidate in (
        p.get("id"),
        p.get("route_id"),
        f"osm:{p.get('osm_type')}:{p.get('osm_id')}" if p.get("osm_id") else None,
        f"gbif:{p.get('gbif_id')}" if p.get("gbif_id") else None,
    ):
        if candidate:
            return str(candidate)
    return f"name:{_norm(p.get('name') or p.get('common_name') or p.get('species') or p.get('scientific_name'))}"


def feature_key(feature: dict[str, Any]) -> str:
    """Stable identity used by RAW upserts and published editorial merges."""
    return _feature_key(feature)

