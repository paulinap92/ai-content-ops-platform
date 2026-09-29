from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from src.api.dependencies import EventImportServiceDep, EventSourceServiceDep
from src.domain.schemas import (
    EventPreviewRequest,
    EventPreviewResponse,
    EventSourceConfigUpdateRequest,
    EventSourceCreateRequest,
    EventSourceResponse,
    EventSourceReviewRequest,
)

router = APIRouter(prefix="/api/v1/events", tags=["Canarias Cerca Events"])

SourceIdPath = Annotated[str, Path(min_length=2, max_length=120)]


@router.get(
    "/sources",
    response_model=list[EventSourceResponse],
    summary="Lista lokalnie zarządzanych źródeł wydarzeń i statusu analizy",
)
async def list_event_sources(
    service: EventSourceServiceDep,
) -> list[EventSourceResponse]:
    return await service.list_sources()




@router.post(
    "/sources",
    response_model=EventSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaj oficjalny link źródła wydarzeń",
)
async def create_event_source(
    payload: EventSourceCreateRequest,
    service: EventSourceServiceDep,
) -> EventSourceResponse:
    return await service.create_source(payload)


@router.patch(
    "/sources/{source_id}/config",
    response_model=EventSourceResponse,
    summary="Edytuj link i podstawowe dane źródła",
)
async def update_event_source_config(
    source_id: SourceIdPath,
    payload: EventSourceConfigUpdateRequest,
    service: EventSourceServiceDep,
) -> EventSourceResponse:
    return await service.update_config(source_id, payload)


@router.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Usuń źródło wydarzeń z lokalnego katalogu",
)
async def delete_event_source(
    source_id: SourceIdPath,
    service: EventSourceServiceDep,
) -> Response:
    await service.delete_source(source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/sources/{source_id}",
    response_model=EventSourceResponse,
    summary="Zapisz analizę źródła wydarzeń",
)
async def update_event_source_review(
    source_id: SourceIdPath,
    payload: EventSourceReviewRequest,
    service: EventSourceServiceDep,
) -> EventSourceResponse:
    return await service.update_review(source_id=source_id, payload=payload)


@router.post(
    "/sources/{source_id}/preview",
    response_model=EventPreviewResponse,
    summary="Run the local EventImportGraph and pause at human review",
)
async def preview_source_events(
    source_id: SourceIdPath,
    payload: EventPreviewRequest,
    service: EventImportServiceDep,
) -> EventPreviewResponse:
    result = await service.preview(source_id=source_id, limit=payload.limit)
    return EventPreviewResponse.model_validate(result)
