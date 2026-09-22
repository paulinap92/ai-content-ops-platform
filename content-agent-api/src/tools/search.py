from langchain_tavily.tavily_search import TavilySearch

from src.core.config import settings


def search_web(topic: str) -> str:
    """Wyszukuje informacje w internecie przez Tavily."""

    if settings.tavily_api_key is None:
        raise ValueError(
            "Brak TAVILY_API_KEY. Wklej source_text albo dodaj TAVILY_API_KEY do .env."
        )

    tool = TavilySearch(
        tavily_api_key=settings.tavily_api_key.get_secret_value(),
        max_results=settings.max_search_results,
    )

    response: dict = tool.invoke({"query": topic})
    raw_results = response.get("results", [])

    if not raw_results:
        return "Brak wyników wyszukiwania"

    formatted: list[str] = []
    for i, result in enumerate(raw_results, 1):
        url = result.get("url", "brak URL")
        content = result.get("content", "brak treści")
        formatted.append(f"[{i}] {url}\n{content}")

    return "\n\n".join(formatted)
