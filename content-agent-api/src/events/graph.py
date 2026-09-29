from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.events.nodes import clean, crawl, extract, human_review, publish, validate
from src.events.state import EventImportState


def build_event_import_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Local event import graph.

    START → crawl → clean → extract → validate → human_review → publish → END
                                                    │
                                                    └─ interrupt for editor review

    The publish node is intentionally a local JSON export only. Production DB
    writes remain a later explicit step.
    """

    builder: StateGraph = StateGraph(EventImportState)
    builder.add_node("crawl", crawl)
    builder.add_node("clean", clean)
    builder.add_node("extract", extract)
    builder.add_node("validate", validate)
    builder.add_node("human_review", human_review)
    builder.add_node("publish", publish)

    builder.add_edge(START, "crawl")
    builder.add_edge("crawl", "clean")
    builder.add_edge("clean", "extract")
    builder.add_edge("extract", "validate")
    builder.add_edge("validate", "human_review")
    builder.add_edge("publish", END)

    return builder.compile(checkpointer=checkpointer)
