from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ContentType = Literal["place", "event", "news", "route", "guide", "other"]


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    url: str = ""


class LocalizedPublicContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    summary: str = ""
    body_markdown: str = Field(min_length=1)


class FinalContentPackage(BaseModel):
    """Transport package produced by the agent before publishing to any CMS/database."""

    model_config = ConfigDict(extra="ignore")

    type: ContentType
    island: str = Field(min_length=1)
    category: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    public_content: dict[str, LocalizedPublicContent]
    editor_notes: list[str] = Field(default_factory=list)
    status: str | None = None
    generated_at: datetime | None = None

    @field_validator("category")
    @classmethod
    def _category_must_be_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = normalized.replace("_", "").isalnum() and " " not in normalized and "-" not in normalized
        if not allowed:
            raise ValueError("category must be a stable snake_case slug, e.g. natural_pools")
        return normalized

    @field_validator("slug")
    @classmethod
    def _slug_must_be_kebab_case(cls, value: str) -> str:
        normalized = value.strip().lower()
        parts = normalized.split("-")
        if not normalized or any(not part.isalnum() for part in parts):
            raise ValueError("slug must use lowercase letters, numbers and hyphens only")
        return normalized


def validate_content_package(
    payload: dict,
    expected_languages: tuple[str, ...],
) -> FinalContentPackage:
    package = FinalContentPackage.model_validate(payload)
    missing = [lang for lang in expected_languages if lang not in package.public_content]
    if missing:
        raise ValueError(
            "Final JSON is missing configured public_content languages: " + ", ".join(missing)
        )
    return package
