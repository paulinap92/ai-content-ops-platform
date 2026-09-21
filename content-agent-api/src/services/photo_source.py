from __future__ import annotations

import io
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from google.auth import default as google_auth_default
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

IMAGE_MIME_PREFIX = "image/"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


@dataclass(slots=True)
class SourcePhoto:
    source_file_id: str
    name: str
    mime_type: str
    folder_path: str
    size: int | None = None
    web_view_link: str | None = None


class PhotoSource(Protocol):
    name: str

    def list_images(self) -> list[SourcePhoto]: ...

    def read_bytes(self, source_file_id: str) -> tuple[bytes, str]: ...

    def rename(self, source_file_id: str, new_name: str) -> SourcePhoto: ...


class LocalPhotoSource:
    """Local filesystem implementation used for quick development/testing."""

    name = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_images(self) -> list[SourcePhoto]:
        result: list[SourcePhoto] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            rel = path.relative_to(self.root)
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            result.append(
                SourcePhoto(
                    source_file_id=rel.as_posix(),
                    name=path.name,
                    mime_type=mime_type,
                    folder_path=rel.parent.as_posix() if rel.parent.as_posix() != "." else "",
                    size=path.stat().st_size,
                )
            )
        return sorted(result, key=lambda item: (item.folder_path.lower(), item.name.lower()))

    def _resolve(self, source_file_id: str) -> Path:
        candidate = (self.root / source_file_id).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError("Invalid local photo path")
        return candidate

    def read_bytes(self, source_file_id: str) -> tuple[bytes, str]:
        path = self._resolve(source_file_id)
        return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    def rename(self, source_file_id: str, new_name: str) -> SourcePhoto:
        current = self._resolve(source_file_id)
        target = current.with_name(new_name)
        if target.exists() and target != current:
            raise FileExistsError(f"Target already exists: {target.name}")
        current.rename(target)
        rel = target.relative_to(self.root)
        return SourcePhoto(
            source_file_id=rel.as_posix(),
            name=target.name,
            mime_type=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            folder_path=rel.parent.as_posix() if rel.parent.as_posix() != "." else "",
            size=target.stat().st_size,
        )


class GoogleDrivePhotoSource:
    """
    Google Drive implementation.

    The configured root folder must be shared with the service account used by the app.
    File IDs are stable across rename/move operations, which makes Drive ideal for this workflow.
    """

    name = "drive"

    def __init__(self, root_folder_id: str, service_account_file: str | None = None) -> None:
        if not root_folder_id:
            raise ValueError("GOOGLE_DRIVE_ROOT_FOLDER_ID is required when PHOTO_SOURCE=drive")

        if service_account_file:
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=[DRIVE_SCOPE],
            )
        else:
            credentials, _ = google_auth_default(scopes=[DRIVE_SCOPE])

        self.root_folder_id = root_folder_id
        self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def _children(self, folder_id: str) -> list[dict]:
        items: list[dict] = []
        page_token: str | None = None
        while True:
            response = (
                self.service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    spaces="drive",
                    fields="nextPageToken, files(id,name,mimeType,size,webViewLink)",
                    pageToken=page_token,
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            items.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return items

    def list_images(self) -> list[SourcePhoto]:
        result: list[SourcePhoto] = []

        def walk(folder_id: str, parts: list[str]) -> None:
            for item in self._children(folder_id):
                mime_type = item.get("mimeType", "")
                if mime_type == "application/vnd.google-apps.folder":
                    walk(item["id"], [*parts, item["name"]])
                    continue
                if not mime_type.startswith(IMAGE_MIME_PREFIX):
                    continue
                result.append(
                    SourcePhoto(
                        source_file_id=item["id"],
                        name=item["name"],
                        mime_type=mime_type,
                        folder_path="/".join(parts),
                        size=int(item["size"]) if item.get("size") else None,
                        web_view_link=item.get("webViewLink"),
                    )
                )

        walk(self.root_folder_id, [])
        return sorted(result, key=lambda item: (item.folder_path.lower(), item.name.lower()))

    def read_bytes(self, source_file_id: str) -> tuple[bytes, str]:
        metadata = (
            self.service.files()
            .get(fileId=source_file_id, fields="name,mimeType", supportsAllDrives=True)
            .execute()
        )
        request = self.service.files().get_media(fileId=source_file_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue(), metadata.get("mimeType") or "application/octet-stream"

    def rename(self, source_file_id: str, new_name: str) -> SourcePhoto:
        updated = (
            self.service.files()
            .update(
                fileId=source_file_id,
                body={"name": new_name},
                fields="id,name,mimeType,size,webViewLink,parents",
                supportsAllDrives=True,
            )
            .execute()
        )
        return SourcePhoto(
            source_file_id=updated["id"],
            name=updated["name"],
            mime_type=updated.get("mimeType", "application/octet-stream"),
            folder_path="",  # path remains stored from the scan; Drive API does not return parent names here
            size=int(updated["size"]) if updated.get("size") else None,
            web_view_link=updated.get("webViewLink"),
        )


def build_photo_source(
    source_name: str,
    local_root: str,
    drive_root_folder_id: str | None,
    google_service_account_file: str | None,
) -> PhotoSource:
    source = source_name.strip().lower()
    if source == "drive":
        return GoogleDrivePhotoSource(
            root_folder_id=drive_root_folder_id or "",
            service_account_file=google_service_account_file,
        )
    if source == "local":
        return LocalPhotoSource(local_root)
    raise ValueError(f"Unsupported PHOTO_SOURCE='{source_name}'. Use 'local' or 'drive'.")
