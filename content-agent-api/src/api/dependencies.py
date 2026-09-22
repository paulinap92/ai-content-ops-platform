from typing import Annotated

from fastapi import Depends, Request

from src.services.agent_service import AgentService
from src.services.photo_service import PhotoService
from src.services.canarias_publisher import CanariasPublisherService


def get_agent_service(request: Request) -> AgentService:
    service: AgentService = request.app.state.agent_service
    return service


def get_canarias_publisher(request: Request) -> CanariasPublisherService:
    service: CanariasPublisherService = request.app.state.canarias_publisher
    return service


def get_photo_service(request: Request) -> PhotoService:
    service: PhotoService = request.app.state.photo_service
    return service


AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]
PhotoServiceDep = Annotated[PhotoService, Depends(get_photo_service)]
CanariasPublisherDep = Annotated[CanariasPublisherService, Depends(get_canarias_publisher)]
