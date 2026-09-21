from typing import TypedDict


class AgentState(TypedDict, total=False):
    """Stan agenta-redaktora Canarias Cerca."""

    # Input od redaktora / przyszłego UI
    topic: str
    source_text: str
    source_url: str
    island_hint: str
    content_type_hint: str

    # Research
    research_data: str

    # Curate — propozycja treści do review przez człowieka
    outline: str

    # Human review
    human_decision: str  # "approve" | "revise"
    human_feedback: str

    # Write — finalny pakiet JSON jako tekst
    draft: str

    # Export
    file_path: str

    # Meta
    revision_count: int
    status: str  # researching|planning|awaiting_review|writing|exporting|ready|error
    error_message: str
