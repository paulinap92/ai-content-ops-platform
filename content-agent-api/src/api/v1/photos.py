from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from src.api.dependencies import PhotoServiceDep
from src.domain.schemas import (
    PhotoDecisionRequest,
    PhotoDecisionResponse,
    PhotoDetailResponse,
    PhotoFolderItemResponse,
    PhotoListItemResponse,
    PhotoScanResponse,
    PhotoUpdateRequest,
)

router = APIRouter(prefix="/api/v1/photos", tags=["Canarias Cerca Photos"])

PhotoIdPath = Annotated[str, Path(description="MongoDB id zdjęcia")]


@router.post(
    "/scan",
    response_model=PhotoScanResponse,
    summary="Przeskanuj źródło zdjęć",
    description=(
        "Skanuje skonfigurowany PHOTO_SOURCE (local lub drive), wykrywa obrazy i dopisuje "
        "nowe elementy do kolejki review. Wyspa/gmina są inferowane z folderów."
    ),
)
async def scan_photos(service: PhotoServiceDep) -> PhotoScanResponse:
    return await service.scan()


@router.get("", response_model=list[PhotoListItemResponse], summary="Lista zdjęć")
async def list_photos(
    service: PhotoServiceDep,
    photo_status: str | None = Query(default=None, alias="status"),
    folder: str | None = Query(default=None, description="Folder path; includes all descendants"),
) -> list[PhotoListItemResponse]:
    return await service.list_photos(status=photo_status, folder=folder)


@router.get("/folders", response_model=list[PhotoFolderItemResponse], summary="Drzewo folderów zdjęć")
async def list_photo_folders(
    service: PhotoServiceDep,
    photo_status: str | None = Query(default=None, alias="status"),
) -> list[PhotoFolderItemResponse]:
    return await service.list_folders(status=photo_status)


@router.get("/{photo_id}", response_model=PhotoDetailResponse, summary="Szczegóły zdjęcia")
async def get_photo(photo_id: PhotoIdPath, service: PhotoServiceDep) -> PhotoDetailResponse:
    return await service.get_photo(photo_id)


@router.patch("/{photo_id}", response_model=PhotoDetailResponse, summary="Popraw metadata zdjęcia")
async def update_photo(
    photo_id: PhotoIdPath,
    payload: PhotoUpdateRequest,
    service: PhotoServiceDep,
) -> PhotoDetailResponse:
    return await service.update_photo(photo_id, payload)


@router.post(
    "/{photo_id}/decision",
    response_model=PhotoDecisionResponse,
    summary="Approve albo skip",
)
async def decide_photo(
    photo_id: PhotoIdPath,
    payload: PhotoDecisionRequest,
    service: PhotoServiceDep,
) -> PhotoDecisionResponse:
    return await service.decide(photo_id, payload.action)


@router.get("/{photo_id}/preview", summary="Podgląd zdjęcia")
async def preview_photo(photo_id: PhotoIdPath, service: PhotoServiceDep) -> Response:
    data, mime_type = await service.read_preview(photo_id)
    return Response(content=data, media_type=mime_type, headers={"Cache-Control": "private, max-age=60"})


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Usuń metadata z kolejki")
async def delete_photo(photo_id: PhotoIdPath, service: PhotoServiceDep) -> None:
    await service.delete_photo_metadata(photo_id)
