import re
from typing import Any

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ContentEditorError(ValueError):
    pass


def _validate_item(item: dict[str, Any]) -> dict[str, Any]:
    clean = dict(item)
    slug = str(clean.get("slug") or "").strip()

    if not slug or not SLUG_RE.fullmatch(slug):
        raise ContentEditorError(
            "slug must use lowercase letters, numbers and hyphens only"
        )

    name = str(clean.get("name") or clean.get("title") or "").strip()
    if not name:
        raise ContentEditorError("name or title is required")

    clean["slug"] = slug
    if clean.get("order") not in (None, ""):
        try:
            clean["order"] = int(clean["order"])
        except (TypeError, ValueError) as exc:
            raise ContentEditorError("order must be an integer") from exc

    for key in ("latitude", "longitude"):
        if clean.get(key) in (None, ""):
            clean.pop(key, None)
            continue
        try:
            clean[key] = float(clean[key])
        except (TypeError, ValueError) as exc:
            raise ContentEditorError(f"{key} must be numeric") from exc

    if "tags" in clean and not isinstance(clean["tags"], list):
        raise ContentEditorError("tags must be an array")

    return clean

