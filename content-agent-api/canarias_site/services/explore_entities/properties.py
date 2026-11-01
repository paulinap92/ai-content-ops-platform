"""Deterministic source/editorial precedence for every Explore API."""

from copy import deepcopy


def preferred_feature(rows, catalog, island=None):
    candidates = []
    for row in rows or []:
        if row.get("dataset_code") != catalog:
            continue
        payload = row.get("properties") or {}
        for record in payload.get("records", []):
            if not isinstance(record, dict) or not isinstance(record.get("properties"), dict):
                continue
            props = record["properties"]
            if island and props.get("island") not in (None, island):
                continue
            provider = row.get("provider", "")
            priority = (
                provider == "canarias-cerca-editorial",
                bool(props.get("editorial_override")),
                bool(props.get("cc_curated")),
                provider == "canarias-cerca-legacy",
            )
            candidates.append((priority, str(provider), str(props.get("id", "")), record))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    selected = deepcopy(candidates[0][3])
    # A second source can supply useful metadata absent from the preferred
    # source; null external fields must not erase an editorial description.
    for _, _, _, record in candidates[1:]:
        for key, value in record["properties"].items():
            if key in {"hidden", "editorial_override", "cc_curated", "geometry_override"}:
                continue
            if selected["properties"].get(key) in (None, "", [], {}) and value not in (
                None,
                "",
                [],
                {},
            ):
                selected["properties"][key] = deepcopy(value)
    return selected

