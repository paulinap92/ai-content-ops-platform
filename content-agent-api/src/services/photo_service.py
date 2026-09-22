from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from beanie import PydanticObjectId, SortDirection

from src.domain.documents import PhotoDocument
from src.domain.photo_structure import parse_photo_folder
from src.domain.schemas import (
    PhotoDecisionResponse,
    PhotoDetailResponse,
    PhotoFolderItemResponse,
    PhotoListItemResponse,
    PhotoScanResponse,
    PhotoUpdateRequest,
)
from src.services.exceptions import BusinessRuleException, NotFoundException
from src.services.photo_source import PhotoSource

logger = logging.getLogger(__name__)


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return cleaned or "photo"


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
                metadata = parse_photo_folder(item.folder_path)
                doc = await PhotoDocument.find_one(PhotoDocument.source_key == source_key)

                if doc:
                    doc.folder_path = item.folder_path
                    doc.current_name = item.name
                    doc.mime_type = item.mime_type
                    doc.size = item.size
                    doc.web_view_link = item.web_view_link
                    doc.last_scanned_at = now

                    # Folder structure is deterministic. Fill only missing editorial fields so a
                    # later manual correction in the editor is never destroyed by another scan.
                    if not doc.island:
                        doc.island = metadata.island
                    if not doc.site_area:
                        doc.site_area = metadata.site_area
                    if not doc.site_section:
                        doc.site_section = metadata.site_section
                    if not doc.municipality:
                        doc.municipality = metadata.municipality
                    if not doc.place:
                        doc.place = metadata.place
                    if not doc.category and metadata.site_section:
                        doc.category = metadata.site_section

                    await doc.save_changes()
                    existing += 1
                    continue

                suggested = self._suggest_filename(
                    original_name=item.name,
                    island=metadata.island,
                    municipality=metadata.municipality,
                    place=metadata.place,
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
                    island=metadata.island,
                    site_area=metadata.site_area,
                    site_section=metadata.site_section,
                    municipality=metadata.municipality,
                    place=metadata.place,
                    category=metadata.site_section,
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

    async def list_photos(
        self,
        status: str | None = None,
        folder: str | None = None,
    ) -> list[PhotoListItemResponse]:
        query_filter: dict[str, object] = {}
        if status:
            query_filter["status"] = status
        if folder:
            normalized = folder.strip("/\\")
            query_filter["folder_path"] = {
                "$regex": rf"^{re.escape(normalized)}(?:/|$)",
                "$options": "i",
            }

        query = PhotoDocument.find(query_filter) if query_filter else PhotoDocument.find()
        docs = await query.sort([("folder_path", SortDirection.ASCENDING), ("current_name", SortDirection.ASCENDING)]).limit(1000).to_list()
        return [self._list_response(doc) for doc in docs]

    async def list_folders(self, status: str | None = None) -> list[PhotoFolderItemResponse]:
        query = PhotoDocument.find(PhotoDocument.status == status) if status else PhotoDocument.find()
        docs = await query.limit(5000).to_list()

        direct_counts: Counter[str] = Counter()
        total_counts: Counter[str] = Counter()

        for doc in docs:
            path = (doc.folder_path or "").strip("/\\")
            direct_counts[path] += 1
            if not path:
                continue
            parts = [part for part in path.replace("\\", "/").split("/") if part]
            for index in range(1, len(parts) + 1):
                total_counts["/".join(parts[:index])] += 1

        # Root represents the whole library. Folder nodes include intermediate directories even
        # when images only exist deeper in the tree.
        result = [
            PhotoFolderItemResponse(
                path="",
                direct_count=direct_counts.get("", 0),
                total_count=len(docs),
            )
        ]
        all_paths = sorted(set(direct_counts) | set(total_counts), key=lambda value: (value.count("/"), value.casefold()))
        for path in all_paths:
            if not path:
                continue
            result.append(
                PhotoFolderItemResponse(
                    path=path,
                    direct_count=direct_counts.get(path, 0),
                    total_count=total_counts.get(path, direct_counts.get(path, 0)),
                )
            )
        return result

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
            return PhotoDecisionResponse(
                photo_id=str(doc.id),
                action=action,
                status=doc.status,
                filename=doc.current_name,
            )

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
            site_area=doc.site_area,
            site_section=doc.site_section,
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
            site_area=doc.site_area,
            site_section=doc.site_section,
            municipality=doc.municipality,
            place=doc.place,
            category=doc.category,
            alt_texts=doc.alt_texts,
            tags=doc.tags,
            suggested_filename=doc.suggested_filename,
            web_view_link=doc.web_view_link,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
