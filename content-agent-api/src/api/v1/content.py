import os
from typing import Annotated

from fastapi import APIRouter, Path, status
from fastapi.responses import FileResponse

from src.api.dependencies import AgentServiceDep
from src.domain.schemas import (
    ContentCreateRequest,
    ContentCreatedResponse,
    ContentDecisionRequest,
    ContentDecisionResponse,
    ContentListItemResponse,
    ContentStatusResponse,
)
from src.services.exceptions import AgentException

router = APIRouter(prefix="/api/v1/content", tags=["Canarias Cerca Content"])

ThreadIdPath = Annotated[str, Path(description="UUID draftu zwrócony przez POST /api/v1/content")]


@router.post(
    "",
    response_model=ContentCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Utwórz nowy draft Canarias Cerca",
    description="Graf startuje w tle. Polluj GET /{thread_id}, aby śledzić postęp.",
)
async def create_content(
        payload: ContentCreateRequest,
        service: AgentServiceDep,
) -> ContentCreatedResponse:
    return await service.create_content(
        topic=payload.topic,
        source_text=payload.source_text,
        source_url=payload.source_url,
        island_hint=payload.island_hint,
        content_type_hint=payload.content_type_hint,
    )


@router.get(
    "",
    response_model=list[ContentListItemResponse],
    summary="Lista draftów",
)
async def list_content(service: AgentServiceDep) -> list[ContentListItemResponse]:
    return await service.list_content()


@router.get(
    "/{thread_id}",
    response_model=ContentStatusResponse,
    summary="Status draftu",
    description=(
        "Gdy status='awaiting_review', outline zawiera propozycję do zatwierdzenia. "
        "Gdy status='ready', file_path wskazuje na finalny JSON."
    ),
)
async def get_content(
        thread_id: ThreadIdPath,
        service: AgentServiceDep,
) -> ContentStatusResponse:
    return await service.get_content(thread_id=thread_id)


@router.post(
    "/{thread_id}/decision",
    response_model=ContentDecisionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Zatwierdź albo popraw propozycję",
)
async def make_decision(
        thread_id: ThreadIdPath,
        payload: ContentDecisionRequest,
        service: AgentServiceDep,
) -> ContentDecisionResponse:
    return await service.make_decision(
        thread_id=thread_id,
        action=payload.action,
        feedback=payload.feedback,
        search_query=payload.search_query,
    )


@router.get(
    "/{thread_id}/file",
    summary="Pobierz gotowy JSON",
    description="Dostępne tylko gdy status='ready'",
    response_class=FileResponse,
)
async def download_content(
        thread_id: ThreadIdPath,
        service: AgentServiceDep,
) -> FileResponse:
    file_path = await service.get_file_path(thread_id=thread_id)

    if not os.path.exists(file_path):
        raise AgentException(
            f"File not found on disk: {file_path}. Check if output volume is mounted correctly."
        )

    return FileResponse(
        path=file_path,
        media_type="application/json",
        filename=os.path.basename(file_path),
    )


@router.delete(
    "/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Usuń metadata draftu",
)
async def delete_content(
        thread_id: ThreadIdPath,
        service: AgentServiceDep,
) -> None:
    await service.delete_content(thread_id=thread_id)
