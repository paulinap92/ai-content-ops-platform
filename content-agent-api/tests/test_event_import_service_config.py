from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from src.events.source_catalog import EVENT_SOURCE_BY_ID
from src.services.event_import_service import EventImportService


class FakeGraph:
    def __init__(self) -> None:
        self.invoke_config: dict[str, Any] | None = None
        self.input_state: dict[str, Any] | None = None
        self.state_config: dict[str, Any] | None = None

    def invoke(self, input_state: dict[str, Any], config: dict[str, Any]) -> None:
        self.input_state = input_state
        self.invoke_config = config

    def get_state(self, config: dict[str, Any]) -> SimpleNamespace:
        self.state_config = config
        return SimpleNamespace(
            values={
                "events": [],
                "stats": {},
                "status": "awaiting_review",
            },
            next=("human_review",),
        )


class FakeSourceService:
    async def get_definition(self, source_id: str):
        return EVENT_SOURCE_BY_ID[source_id]


def test_event_preview_uses_top_level_checkpoint_namespace() -> None:
    graph = FakeGraph()
    service = EventImportService(  # type: ignore[arg-type]
        graph=graph,
        source_service=FakeSourceService(),
    )
    try:
        result = asyncio.run(service.preview("la-laguna-agenda", limit=1))
        assert result["active_node"] == "human_review"
        assert graph.invoke_config is not None
        configurable = graph.invoke_config["configurable"]
        assert configurable["thread_id"].startswith("event-la-laguna-agenda-")
        assert "checkpoint_ns" not in configurable
        assert graph.state_config == graph.invoke_config
        assert graph.input_state is not None
        assert graph.input_state["source_config"]["source_id"] == "la-laguna-agenda"
    finally:
        asyncio.run(service.shutdown())
