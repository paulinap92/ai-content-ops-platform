from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from beanie import PydanticObjectId, SortDirection

from src.domain.documents import PhotoDocument
from src.domain.schemas import (
    PhotoDecisionResponse,
    PhotoDetailResponse,
    PhotoListItemResponse,
    PhotoScanResponse,
    PhotoUpdateRequest,
)
from src.services.exceptions import BusinessRuleException, NotFoundException
from src.services.photo_source import PhotoSource, SourcePhoto

logger = logging.getLogger(__name__)

ISLANDS = {
    "tenerife": "Tenerife",
    "gran canaria": "Gran Canaria",
    "lanzarote": "Lanzarote",
    "fuerteventura": "Fuerteventura",
    "la palma": "La Palma",
    "la gomera": "La Gomera",
    "el hierro": "El Hierro",
    "la graciosa": "La Graciosa",
}


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return cleaned or "photo"


def _humanize_folder(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


def _infer_from_folder(folder_path: str) -> tuple[str, str]:
    parts = [part.strip() for part in folder_path.replace("\\", "/").split("/") if part.strip()]
    if not parts:
        return "", ""

    island = ""
    island_index: int | None = None
    for index, part in enumerate(parts):
        normalized = part.replace("_", " ").replace("-", " ").strip().lower()
        if normalized in ISLANDS:
            island = ISLANDS[normalized]
            island_index = index
            break

    municipality = ""
    if island_index is not None and island_index + 1 < len(parts):
        municipality = _humanize_folder(parts[island_index + 1])
    elif len(parts) >= 2:
        island = _humanize_folder(parts[0])
        municipality = _humanize_folder(parts[1])
    elif len(parts) == 1:
        island = _humanize_folder(parts[0])

    return island, municipality


class PhotoService:
    def __init__(self, source: PhotoSource) -> None:
        self.source = source
        self._scan_lock = asyncio.Lock()

    async def scan(self) -> PhotoScanResponse:
        if self._scan_lock.locked():
            raise BusinessRuleException("Photo scan is already running.")

        async with self._scan_lock:
            photos = await asyncio.to_thread(self.source.list_images)
            created = 0
            existing = 0
            now = datetime.now(timezone.utc)

            for item in photos:
                source_key = self._source_key(item.source_file_id)
                doc = await PhotoDocument.find_one(PhotoDocument.source_key == source_key)
                if doc:
                    doc.folder_path = item.folder_path
                    doc.current_name = item.name
                    doc.mime_type = item.mime_type
                    doc.size = item.size
                    doc.web_view_link = item.web_view_link
                    doc.last_scanned_at = now
                    await doc.save_changes()
                    existing += 1
                    continue

                island, municipality = _infer_from_folder(item.folder_path)
                suggested = self._suggest_filename(
                    original_name=item.name,
                    island=island,
                    municipality=municipality,
                    place="",
                    unique_token=hashlib.sha1(item.source_file_id.encode("utf-8")).hexdigest()[:6],
                )
                doc = PhotoDocument(
                    source=self.source.name,
                    source_key=source_key,
                    source_file_id=item.source_file_id,
                    original_name=item.name,
                    current_name=item.name,
                    mime_type=item.mime_type,
                    size=item.size,
                    folder_path=item.folder_path,
                    island=island,
                    municipality=municipality,
                    suggested_filename=suggested,
                    web_view_link=item.web_view_link,
                    status="new",
                    last_scanned_at=now,
                )
                await doc.insert()
                created += 1

            return PhotoScanResponse(
                source=self.source.name,
                found=len(photos),
                created=created,
                existing=existing,
            )

    async def list_photos(self, status: str | None = None) -> list[PhotoListItemResponse]:
        query = PhotoDocument.find(PhotoDocument.status == status) if status else PhotoDocument.find()
        docs = await query.sort([("created_at", SortDirection.DESCENDING)]).limit(500).to_list()
        return [self._list_response(doc) for doc in docs]

    async def get_photo(self, photo_id: str) -> PhotoDetailResponse:
        doc = await self._get_doc(photo_id)
        return self._detail_response(doc)

    async def update_photo(self, photo_id: str, payload: PhotoUpdateRequest) -> PhotoDetailResponse:
        doc = await self._get_doc(photo_id)
        if doc.status not in {"new", "review"}:
            raise BusinessRuleException(f"Cannot edit photo with status '{doc.status}'.")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            if value is None:
                continue
            setattr(doc, key, value.strip() if isinstance(value, str) else value)

        if not payload.suggested_filename:
            doc.suggested_filename = self._suggest_filename(
                original_name=doc.current_name,
                island=doc.island,
                municipality=doc.municipality,
                place=doc.place,
                unique_token=hashlib.sha1(doc.source_file_id.encode("utf-8")).hexdigest()[:6],
            )
        doc.status = "review"
        doc.updated_at = datetime.now(timezone.utc)
        await doc.save_changes()
        return self._detail_response(doc)

    async def decide(self, photo_id: str, action: str) -> PhotoDecisionResponse:
        doc = await self._get_doc(photo_id)
        if doc.status in {"approved", "skipped"}:
            raise BusinessRuleException(f"Photo already has terminal status '{doc.status}'.")

        if action == "skip":
            doc.status = "skipped"
            doc.updated_at = datetime.now(timezone.utc)
            await doc.save_changes()
            return PhotoDecisionResponse(photo_id=str(doc.id), action=action, status=doc.status, filename=doc.current_name)

        if action != "approve":
            raise BusinessRuleException("Unsupported action. Use approve or skip.")

        new_name = (doc.suggested_filename or "").strip()
        if not new_name:
            new_name = self._suggest_filename(
                original_name=doc.current_name,
                island=doc.island,
                municipality=doc.municipality,
                place=doc.place,
                unique_token=hashlib.sha1(doc.source_file_id.encode("utf-8")).hexdigest()[:6],
            )

        new_name = self._safe_filename(new_name, doc.current_name)
        renamed = await asyncio.to_thread(self.source.rename, doc.source_file_id, new_name)
        doc.source_file_id = renamed.source_file_id
        doc.source_key = self._source_key(renamed.source_file_id)
        doc.current_name = renamed.name
        doc.mime_type = renamed.mime_type or doc.mime_type
        doc.size = renamed.size if renamed.size is not None else doc.size
        doc.web_view_link = renamed.web_view_link or doc.web_view_link
        doc.status = "approved"
        doc.approved_at = datetime.now(timezone.utc)
        doc.updated_at = doc.approved_at
        await doc.save_changes()

        return PhotoDecisionResponse(
            photo_id=str(doc.id),
            action=action,
            status=doc.status,
            filename=doc.current_name,
        )

    async def read_preview(self, photo_id: str) -> tuple[bytes, str]:
        doc = await self._get_doc(photo_id)
        return await asyncio.to_thread(self.source.read_bytes, doc.source_file_id)

    async def delete_photo_metadata(self, photo_id: str) -> None:
        doc = await self._get_doc(photo_id)
        await doc.delete()

    async def _get_doc(self, photo_id: str) -> PhotoDocument:
        try:
            object_id = PydanticObjectId(photo_id)
            doc = await PhotoDocument.get(object_id)
        except Exception:
            doc = None
        if not doc:
            raise NotFoundException(f"Photo '{photo_id}' not found.")
        return doc

    def _source_key(self, source_file_id: str) -> str:
        return f"{self.source.name}:{source_file_id}"

    @staticmethod
    def _safe_filename(requested: str, current_name: str) -> str:
        current_suffix = Path(current_name).suffix.lower() or ".jpg"
        requested = requested.replace("\\", "-").replace("/", "-").strip()
        requested_path = Path(requested)
        suffix = requested_path.suffix.lower() or current_suffix
        stem = requested_path.stem if requested_path.suffix else requested
        return f"{_slug(stem)}{suffix}"

    @staticmethod
    def _suggest_filename(
        original_name: str,
        island: str,
        municipality: str,
        place: str,
        unique_token: str,
    ) -> str:
        suffix = Path(original_name).suffix.lower() or ".jpg"
        base_parts = [part for part in [island, municipality, place] if part.strip()]
        base = _slug("-".join(base_parts)) if base_parts else "canarias-photo"
        return f"{base}-{unique_token}{suffix}"

    @staticmethod
    def _list_response(doc: PhotoDocument) -> PhotoListItemResponse:
        return PhotoListItemResponse(
            photo_id=str(doc.id),
            status=doc.status,
            current_name=doc.current_name,
            folder_path=doc.folder_path,
            island=doc.island,
            municipality=doc.municipality,
            place=doc.place,
            category=doc.category,
            created_at=doc.created_at,
        )

    @staticmethod
    def _detail_response(doc: PhotoDocument) -> PhotoDetailResponse:
        return PhotoDetailResponse(
            photo_id=str(doc.id),
            source=doc.source,
            status=doc.status,
            original_name=doc.original_name,
            current_name=doc.current_name,
            folder_path=doc.folder_path,
            mime_type=doc.mime_type,
            size=doc.size,
            island=doc.island,
            municipality=doc.municipality,
            place=doc.place,
            category=doc.category,
            alt_es=doc.alt_es,
            tags=doc.tags,
            suggested_filename=doc.suggested_filename,
            web_view_link=doc.web_view_link,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
