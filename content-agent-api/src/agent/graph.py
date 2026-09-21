from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes import curate, human_review, publish, research, write
from src.agent.state import AgentState


def build_content_agent(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """
    Ten sam kształt grafu co w kursie:

    START → research → curate → human_review → write → publish → END
                           ↑          │
                           └──────────┘  revise

    Dla Canarias Cerca:
    research = fakty/źródła
    curate = propozycja treści do review
    write = finalny pakiet ES/EN/PL
    publish = eksport JSON (nie publikacja produkcyjna)
    """

    builder: StateGraph = StateGraph(AgentState)

    builder.add_node("research", research)
    builder.add_node("curate", curate)
    builder.add_node("human_review", human_review)
    builder.add_node("write", write)
    builder.add_node("publish", publish)

    builder.add_edge(START, "research")
    builder.add_edge("research", "curate")
    builder.add_edge("curate", "human_review")
    builder.add_edge("write", "publish")
    builder.add_edge("publish", END)

    return builder.compile(checkpointer=checkpointer)
