import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from beanie import init_beanie
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient

from src.agent.graph import build_content_agent
from src.events.graph import build_event_import_graph
from src.api.error_handlers import register_error_handlers
from src.api.v1.content import router as content_router
from src.api.v1.events import router as events_router
from src.api.v1.photos import router as photos_router
from src.core.config import settings
from src.core.persistence import create_mongodb_checkpointer
from src.domain.documents import (
    ContentDocument,
    EventSourceCatalogStateDocument,
    EventSourceDocument,
    EventSourceReviewDocument,
    PhotoDocument,
)
from src.services.agent_service import AgentService
from src.services.canarias_publisher import CanariasPublisherService
from src.services.event_source_service import EventSourceService
from src.services.event_import_service import EventImportService
from src.services.photo_service import PhotoService
from src.services.photo_source import build_photo_source

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting canarias-cerca-editor-agent ...")
    motor_client: AsyncIOMotorClient = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
    )

    try:
        await init_beanie(
            database=motor_client[settings.mongodb_db_name],
            document_models=[
                ContentDocument,
                PhotoDocument,
                EventSourceDocument,
                EventSourceCatalogStateDocument,
                EventSourceReviewDocument,
            ],
        )

        with create_mongodb_checkpointer() as checkpointer:
            graph = build_content_agent(checkpointer=checkpointer)
            event_graph = build_event_import_graph(checkpointer=checkpointer)
            agent_service = AgentService(
                graph=graph,
                max_workers=settings.max_concurrent_agents,
            )
            app.state.agent_service = agent_service

            photo_source = build_photo_source(
                source_name=settings.photo_source,
                local_root=settings.photo_local_root,
                drive_root_folder_id=settings.google_drive_root_folder_id,
                google_service_account_file=settings.google_service_account_file,
            )
            app.state.photo_service = PhotoService(photo_source)
            app.state.canarias_publisher = CanariasPublisherService()
            event_source_service = EventSourceService()
            await event_source_service.ensure_seeded()
            app.state.event_source_service = event_source_service
            event_import_service = EventImportService(
                graph=event_graph,
                source_service=event_source_service,
                max_workers=min(settings.max_concurrent_agents, 2),
            )
            app.state.event_import_service = event_import_service

            logger.info(
                "Canarias Cerca editor agent ready (photo_source=%s)",
                settings.photo_source,
            )
            yield

            await agent_service.shutdown()
            await event_import_service.shutdown()
    finally:
        motor_client.close()
        logger.info("Canarias Cerca editor agent stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Canarias Cerca Editor Agent API",
        description=(
            "Human-in-the-loop agent pomagający przygotowywać i tłumaczyć treści "
            "dla Canarias Cerca. Finalny wynik to JSON gotowy do review/importu; "
            "finalny pakiet może być wysłany jako draft do editora Canarias Cerca. Photo Manager skanuje foldery/Drive i prowadzi kolejkę review zdjęć. Event Importer ma osobny lokalny LangGraph: crawl → clean → extract → validate → human_review."
        ),
        version="0.9.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    register_error_handlers(app)
    app.include_router(content_router)
    app.include_router(events_router)
    app.include_router(photos_router)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/", include_in_schema=False)
    async def editor_ui() -> FileResponse:
        return FileResponse("static/index.html")

    return app


app = create_app()


@app.get("/health", tags=["Health"])
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "canarias-cerca-editor-agent",
        "instance": os.environ.get("HOSTNAME", "unknown"),
        "env": settings.app_env,
        "photo_source": settings.photo_source,
        "editor_language": settings.editor_language,
        "content_languages": list(settings.content_language_codes),
        "canarias_publish_enabled": settings.canarias_publish_enabled,
    }
