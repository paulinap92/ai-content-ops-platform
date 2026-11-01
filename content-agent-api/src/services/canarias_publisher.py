import json
from pathlib import Path
from typing import Any

from canarias_site.services import studio
from canarias_site.services.studio_auth import session_scope

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
        pass

    async def publish_file(
        self,
        *,
        file_path: str,
        request: CanariasPublishRequest,
        site_target: dict | None = None,
    ) -> CanariasPublishResponse:
        if not settings.canarias_publish_enabled:
            raise BusinessRuleException(
                "SITE_DATABASE_URL is not configured in the standalone editor."
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

        import hashlib
        empty_hash = hashlib.sha256(b"null").hexdigest()
        identity = {"kind": "guide", "island": package.island,
                    "resource": request.section, "record_key": "new:" + package.slug}
        base_fingerprint = empty_hash
        async with session_scope() as session:
            if site_target:
                identity = studio.validate_identity(site_target["identity"])
                if identity["kind"] != "guide":
                    raise BusinessRuleException("AI poprawia istniejące artykuły Guide. Pozostałe rodzaje treści edytuj w formularzu strony.")
                previous = site_target["payload"]
                item = {**previous, **{k: item[k] for k in ("name", "description", "short_description", "translations")}}
                result = await studio.save_draft(session, identity, item, site_target["version"], site_target["base_fingerprint"])
                return CanariasPublishResponse(status="sent_as_draft", island=identity["island"], section=identity["resource"], slug=item["slug"], language=request.language, backend_response=result)
            listing = await studio.list_records(session, "guide", package.island, request.section, package.slug)
            existing = next((r for r in listing["items"] if r.get("draft", {}).get("slug") == package.slug), None)
            if existing:
                if existing.get("id"):
                    return CanariasPublishResponse(status="already_in_studio", island=package.island,
                        section=request.section, slug=package.slug, language=request.language,
                        backend_response={"id": existing["id"], "message": "Istniejąca wersja robocza została zachowana. Otwórz ją w edytorze."})
                identity, base_fingerprint = existing["identity"], existing["base_fingerprint"]
            backend_response = await studio.save_draft(session, identity, item, 0, base_fingerprint)

        return CanariasPublishResponse(
            status="sent_as_draft",
            island=package.island,
            section=request.section,
            slug=package.slug,
            language=request.language,
            backend_response=backend_response,
        )

