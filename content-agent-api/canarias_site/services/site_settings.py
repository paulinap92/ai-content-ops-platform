"""Published site configuration; drafts and revisions never reach this API."""
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text

from canarias_site.models.studio import StudioDocument
from canarias_site.services.admin_editor import EXPLORE_RESOURCES, LIVE_RESOURCES
from canarias_site.services.content import VALID_SECTIONS
from canarias_site.utils.islands import VALID_ISLANDS

SECTIONS = {"explore": "Explore", "live": "Live", "calendar": "Calendario", "news": "Noticias", "datos": "Datos", "guide": "Guía"}
FEATURES = {
    "explore": list(EXPLORE_RESOURCES) + ["airports", "ports", "ferries", "titsa-stops", "titsa-routes", "tilp-routes"],
    "guide": sorted(VALID_SECTIONS),
    "live": list(LIVE_RESOURCES) + ["live-beaches"],
    "datos": ["tourism", "climate", "geology", "population", "economy", "housing", "environment"],
}
COPY_DEFAULTS = {
    "home.title": "Hola, somos las Islas Canarias.",
    "home.description": "Ocho islas, miles de lugares por descubrir. Te invitamos a explorarlas a tu ritmo. Elige una isla para empezar.",
    **{f"nav.{key}": value for key, value in SECTIONS.items()},
    "island.description": "",
    "datos.title": "La isla, en contexto.",
    "datos.description": "Series históricas, estadísticas oficiales y datos ambientales normalizados por Canarias Cerca.",
}
COPY_DEFAULTS.update(json.loads((Path(__file__).resolve().parents[1] / "studio" / "default_copy.json").read_text()))


class ScopeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    sections: dict[str, bool] = Field(default_factory=dict)
    features: dict[str, bool] = Field(default_factory=dict)
    copy_text: dict[str, str] = Field(default_factory=dict, alias="copy")

    @field_validator("sections")
    @classmethod
    def section_names(cls, value):
        if set(value) - SECTIONS.keys():
            raise ValueError("Unknown section")
        return value

    @field_validator("features")
    @classmethod
    def feature_names(cls, value):
        allowed = {f"{area}.{resource}" for area, resources in FEATURES.items() for resource in resources}
        if set(value) - allowed:
            raise ValueError("Unknown subsection")
        return value

    @field_validator("copy_text")
    @classmethod
    def copy_names(cls, value):
        allowed = set(COPY_DEFAULTS) | {f"feature.{area}.{resource}.title" for area, resources in FEATURES.items() for resource in resources}
        allowed |= {f"feature.{area}.{resource}.description" for area, resources in FEATURES.items() for resource in resources}
        if set(value) - allowed or any(len(v) > 5000 for v in value.values()):
            raise ValueError("Unknown text key or text longer than 5000 characters")
        return value


class SiteSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    global_scope: ScopeSettings = Field(default_factory=ScopeSettings, alias="global")
    islands: dict[str, ScopeSettings] = Field(default_factory=dict)

    @field_validator("islands")
    @classmethod
    def island_names(cls, value):
        if set(value) - set(VALID_ISLANDS):
            raise ValueError("Unknown island")
        return value


def normalize_settings(payload: dict) -> dict:
    # Strict booleans: strings such as 'false' are not an editorial toggle.
    for scope in [payload.get("global", {}), *payload.get("islands", {}).values()]:
        for key in ("sections", "features"):
            if any(type(v) is not bool for v in scope.get(key, {}).values()):
                raise ValueError("Visibility values must be booleans")
    return SiteSettings.model_validate(payload).model_dump(by_alias=True)


def empty_settings() -> dict:
    return {"global": {"sections": {}, "features": {}, "copy": {}}, "islands": {}}


def effective_settings(config: dict, island: str | None) -> dict:
    result = deepcopy(config.get("global", {}))
    local = config.get("islands", {}).get(island, {})
    for key in ("sections", "features", "copy"):
        result[key] = {**result.get(key, {}), **local.get(key, {})}
    return result


async def published_settings(session) -> dict[str, Any]:
    # The public API remains deployable before the optional Studio is enabled.
    if not await session.scalar(text("SELECT to_regclass('design.cc_studio_documents')")):
        return empty_settings()
    row = await session.scalar(select(StudioDocument).where(StudioDocument.kind == "settings"))
    return normalize_settings(row.published) if row and row.published is not None else empty_settings()
