import json
from pathlib import Path
from typing import Any

import httpx

from src.core.config import settings
from src.domain.content_package import FinalContentPackage, validate_content_package
from src.domain.schemas import CanariasPublishRequest, CanariasPublishResponse
from src.services.exceptions import AgentException, BusinessRuleException


def build_canarias_item(
    package: FinalContentPackage,
    *,
    language: str,
    featured: bool,
    order: int | None,
) -> dict[str, Any]:
    localized = package.public_content.get(language)
    if localized is None:
        raise BusinessRuleException(
            f"Language '{language}' is not available in this content package."
        )

    first_source_url = next((source.url for source in package.sources if source.url), "")

    item: dict[str, Any] = {
        "slug": package.slug,
        "name": localized.title,
        "type": package.type,
        "category": package.category,
        "short_description": localized.summary,
        "description": localized.body_markdown,
        "language": language,
        "tags": package.tags,
        "featured": featured,
        # Preserve the full package so today's JSON storage does not throw away
        # multilingual content that will later map naturally to SQL translation rows.
        "translations": {
            code: content.model_dump()
            for code, content in package.public_content.items()
        },
        "sources": [source.model_dump() for source in package.sources],
        "editor_notes": package.editor_notes,
        "content_ops_status": "draft",
    }

    if first_source_url:
        item["source_url"] = first_source_url
    if order is not None:
        item["order"] = order

    return item


class CanariasPublisherService:
    def __init__(self) -> None:
        self.base_url = settings.canarias_api_url.rstrip("/")

    async def publish_file(
        self,
        *,
        file_path: str,
        request: CanariasPublishRequest,
    ) -> CanariasPublishResponse:
        if not settings.canarias_publish_enabled:
            raise BusinessRuleException(
                "CANARIAS_API_URL is not configured. Add it to .env before publishing."
            )

        path = Path(file_path)
        if not path.exists():
            raise AgentException(f"Final content file does not exist: {file_path}")

        try:
            raw_payload = json.loads(path.read_text(encoding="utf-8"))
            package = validate_content_package(
                raw_payload,
                expected_languages=settings.content_language_codes,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise AgentException(f"Cannot load final content package: {exc}") from exc

        item = build_canarias_item(
            package,
            language=request.language,
            featured=request.featured,
            order=request.order,
        )

        headers: dict[str, str] = {}
        if settings.canarias_editor_token is not None:
            headers["Authorization"] = (
                f"Bearer {settings.canarias_editor_token.get_secret_value()}"
            )

        url = f"{self.base_url}/api/editor/content"
        params = {
            "island": package.island,
            "section": request.section,
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(
                    url,
                    params=params,
                    json=item,
                    headers=headers,
                )
        except httpx.RequestError as exc:
            raise AgentException(
                f"Cannot reach Canarias Cerca backend at {self.base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail") or response.text
            except ValueError:
                detail = response.text
            raise AgentException(
                f"Canarias Cerca rejected the draft ({response.status_code}): {detail}"
            )

        try:
            backend_response = response.json()
        except ValueError:
            backend_response = {"raw": response.text}

        return CanariasPublishResponse(
            status="sent_as_draft",
            island=package.island,
            section=request.section,
            slug=package.slug,
            language=request.language,
            backend_response=backend_response,
        )
