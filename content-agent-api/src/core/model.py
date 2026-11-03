from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.services.exceptions import APIException


def create_model(temperature: float | None = None) -> BaseChatModel:
    """Tworzy model wybranego providera na podstawie MODEL_PROVIDER."""

    temp = (
        temperature
        if temperature is not None
        else settings.model_temperature_analytical
    )

    match settings.model_provider.lower():
        case "openai":
            if settings.openai_api_key is None:
                raise APIException("AI jest niedostępne: brakuje OPENAI_API_KEY w konfiguracji serwera. Ręczne dodawanie treści działa bez AI.",503,"ai_not_configured")
            return ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model_name,
                temperature=temp,
                timeout=120.0,
                max_retries=2,
            )

        case "anthropic":
            if settings.anthropic_api_key is None:
                raise APIException("AI jest niedostępne: brakuje ANTHROPIC_API_KEY w konfiguracji serwera. Ręczne dodawanie treści działa bez AI.",503,"ai_not_configured")
            return ChatAnthropic(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model_name,
                temperature=temp,
                timeout=120.0,
                stop=None,
            )

        case _:
            raise ValueError(
                f"Nieobsługiwany provider: '{settings.model_provider}'. "
                "Ustaw MODEL_PROVIDER=openai lub MODEL_PROVIDER=anthropic."
            )

