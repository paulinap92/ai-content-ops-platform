from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from src.services.event_source_service import EventSourceService


class EventImportService:
    """Runs the local EventImportGraph until the human-review interrupt."""

    def __init__(
        self, graph: CompiledStateGraph, source_service: EventSourceService, max_workers: int = 2
    ) -> None:
        self._graph = graph
        self._source_service = source_service
        self._executor = ThreadPoolExecutor(max_workers=max(1, min(max_workers, 4)))

    async def preview(self, source_id: str, limit: int = 10) -> dict[str, Any]:
        source = await self._source_service.get_definition(source_id)

        limit = max(1, min(int(limit), 30))
        run_id = f"event-{source_id}-{uuid.uuid4().hex[:10]}"
        # This EventImportGraph is compiled and invoked as its own top-level graph.
        # Do NOT set checkpoint_ns here: LangGraph interprets a non-empty namespace
        # as a nested subgraph path when get_state() is called. That caused
        # `ValueError: Subgraph event_import not found` after a successful import.
        config: RunnableConfig = {
            "configurable": {
                "thread_id": run_id,
            }
        }
        input_state = {
            "source_id": source_id,
            "source_config": asdict(source),
            "limit": limit,
            "run_id": run_id,
            "status": "crawling",
        }

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            lambda: self._graph.invoke(input_state, config),
        )
        snapshot = await loop.run_in_executor(
            self._executor,
            self._graph.get_state,
            config,
        )
        values = dict(snapshot.values or {})
        events = values.get("events", []) or []
        stats = values.get("stats", {}) or {}
        active_node = snapshot.next[0] if snapshot.next else "end"

        return {
            "run_id": run_id,
            "source_id": source.source_id,
            "source_name": source.name,
            "island": source.island,
            "source_url": source.url,
            "count": len(events),
            "status": values.get("status", "unknown"),
            "active_node": active_node,
            "stats": stats,
            "events": events,
            "note": (
                "Local EventImportGraph preview. The graph is paused at human_review; "
                "nothing was written to Railway/PostgreSQL."
            ),
        }

    async def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
