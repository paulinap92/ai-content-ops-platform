import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command, interrupt

from src.agent.prompts import (
    CURATE_HUMAN_PROMPT,
    CURATE_REVISION_SECTION,
    CURATE_SYSTEM_PROMPT,
    RESEARCH_FEEDBACK_PROMPT,
    RESEARCH_HUMAN_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
    WRITE_HUMAN_PROMPT,
    WRITE_SYSTEM_PROMPT,
)
from src.agent.state import AgentState
from src.core.config import settings
from src.core.model import create_model
from src.tools.search import search_web

logger = logging.getLogger(__name__)


def research(state: AgentState) -> dict:
    """Buduje factual brief z wklejonego źródła albo z wyszukiwania Tavily."""

    topic = state.get("topic", "").strip()
    if not topic:
        raise ValueError("Brak tematu (topic) w stanie agenta.")

    source_text = state.get("source_text", "").strip()
    island_hint = state.get("island_hint", "").strip()
    content_type_hint = state.get("content_type_hint", "").strip()
    source_url = state.get("source_url", "").strip()

    if source_text:
        source_material = source_text
        logger.info("[research] Używam materiału wklejonego przez redaktora")
    else:
        query = " ".join(part for part in [topic, island_hint, "Canarias"] if part)
        logger.info("[research] Brak source_text — wyszukuję: '%s'", query)
        source_material = search_web(query)

    model = create_model(settings.model_temperature_analytical)
    response = model.invoke([
        SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
        HumanMessage(content=RESEARCH_HUMAN_PROMPT.format(
            topic=topic,
            island_hint=island_hint or "brak",
            content_type_hint=content_type_hint or "brak",
            source_url=source_url or "brak",
            source_material=source_material,
        )),
    ])

    return {
        "research_data": str(response.content),
        "status": "planning",
        "revision_count": 0,
    }


def curate(state: AgentState) -> dict:
    """Tworzy propozycję treści Canarias Cerca do review przez człowieka."""

    revision_count = state.get("revision_count", 0)
    feedback_section = ""
    if revision_count > 0:
        feedback_section = CURATE_REVISION_SECTION.format(
            revision_count=revision_count,
            human_feedback=state.get("human_feedback", ""),
        )

    model = create_model(settings.model_temperature_analytical)
    response = model.invoke([
        SystemMessage(content=CURATE_SYSTEM_PROMPT),
        HumanMessage(content=CURATE_HUMAN_PROMPT.format(
            topic=state.get("topic", ""),
            source_url=state.get("source_url", "") or "brak",
            island_hint=state.get("island_hint", "") or "brak",
            content_type_hint=state.get("content_type_hint", "") or "brak",
            research_data=state.get("research_data", ""),
            feedback_section=feedback_section,
        )),
    ])

    return {
        "outline": str(response.content),
        "status": "awaiting_review",
    }


def human_review(state: AgentState) -> Command:
    """Zatrzymuje graf i czeka na approve/revise redaktora."""

    revision_count = state.get("revision_count", 0)
    decision: dict[str, str] = interrupt({
        "type": "review_content_proposal",
        "outline": state.get("outline", ""),
        "revision_count": revision_count,
        "message": "Zatwierdź propozycję (approve) albo odeślij ją do poprawy (revise).",
    })

    action = decision.get("action", "approve")
    feedback = decision.get("feedback", "")
    search_query = decision.get("search_query", "")

    if action == "approve":
        return Command(
            update={
                "human_decision": "approve",
                "human_feedback": "",
                "status": "writing",
            },
            goto="write",
        )

    additional_research = ""
    if search_query:
        results = search_web(search_query)
        model = create_model(settings.model_temperature_analytical)
        response = model.invoke([
            SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
            HumanMessage(content=RESEARCH_FEEDBACK_PROMPT.format(
                feedback=feedback,
                search_results=results,
            )),
        ])
        additional_research = str(response.content)

    new_count = revision_count + 1
    if new_count >= settings.max_revisions:
        logger.warning("[human_review] Limit rewizji osiągnięty — przechodzę do finalnego draftu")
        return Command(
            update={
                "human_decision": "approve",
                "human_feedback": f"Auto-approved po {settings.max_revisions} rewizjach.",
                "status": "writing",
            },
            goto="write",
        )

    updated_research = state.get("research_data", "")
    if additional_research:
        updated_research += (
            f"\n\n--- DODATKOWY RESEARCH (rewizja #{new_count}) ---\n"
            f"Zapytanie: {search_query}\n\n{additional_research}"
        )

    return Command(
        update={
            "human_decision": "revise",
            "human_feedback": feedback,
            "revision_count": new_count,
            "status": "planning",
            "research_data": updated_research,
        },
        goto="curate",
    )


def write(state: AgentState) -> dict:
    """Generuje finalny, trójjęzyczny pakiet JSON dla Canarias Cerca."""

    model = create_model(settings.model_temperature_creative)
    response = model.invoke([
        SystemMessage(content=WRITE_SYSTEM_PROMPT),
        HumanMessage(content=WRITE_HUMAN_PROMPT.format(
            topic=state.get("topic", ""),
            source_url=state.get("source_url", ""),
            island_hint=state.get("island_hint", "") or "brak",
            content_type_hint=state.get("content_type_hint", "") or "brak",
            outline=state.get("outline", ""),
            research_data=state.get("research_data", ""),
        )),
    ])

    return {
        "draft": str(response.content),
        "status": "exporting",
    }


def _clean_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def publish(state: AgentState) -> dict:
    """
    Eksportuje finalny draft do JSON.

    Nazwa node'a zostaje `publish`, żeby graf był prawie 1:1 jak w kursie.
    WAŻNE: ten krok NIE publikuje niczego do produkcyjnej bazy Canarias Cerca.
    """

    raw_draft = state.get("draft", "")
    if not raw_draft:
        raise ValueError("Brak finalnego draftu w stanie agenta.")

    try:
        payload = json.loads(_clean_json_text(raw_draft))
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM nie zwrócił poprawnego JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Finalny JSON musi być obiektem.")

    languages = payload.get("languages")
    if not isinstance(languages, dict) or not all(lang in languages for lang in ("es", "en", "pl")):
        raise ValueError("Finalny JSON musi zawierać languages.es, languages.en i languages.pl.")

    payload["source_url"] = payload.get("source_url") or state.get("source_url", "")
    payload["status"] = "ready_for_editor"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()

    topic = state.get("topic", "content")
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower().strip())[:60].strip("-") or "content"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{slug}.json"

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / filename

    with file_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    logger.info("[publish] JSON gotowy do review/importu: %s", file_path)

    return {
        "file_path": str(file_path),
        "status": "ready",
    }
