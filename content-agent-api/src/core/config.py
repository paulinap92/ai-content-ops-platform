from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    # App
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    max_concurrent_agents: int = 4

    # Editorial behaviour
    editor_language: str = "pl"
    content_languages: str = "es,en,pl"

    # LLM
    model_provider: str = "openai"
    model_temperature_analytical: float = 0.2
    model_temperature_creative: float = 0.5

    # OpenAI / Anthropic — tylko klucz wybranego providera jest faktycznie potrzebny.
    openai_api_key: SecretStr | None = None
    openai_model_name: str = "gpt-5.6"
    anthropic_api_key: SecretStr | None = None
    anthropic_model_name: str = "claude-sonnet-4-5"

    # Tavily — opcjonalne, jeśli zawsze podajesz source_text.
    tavily_api_key: SecretStr | None = None

    # MongoDB
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db_name: str = "canarias_cerca_editor"

    # Agent
    output_dir: str = "./output"
    max_revisions: int = 5
    max_search_results: int = 8

    # Canarias Cerca integration.
    # Lokalnie najwygodniej uruchomić Content Studio na :8000, a Canarias backend na :8001.
    canarias_api_url: str = ""
    canarias_editor_token: SecretStr | None = None

    # Photo manager
    photo_source: str = "local"  # local | drive
    photo_local_root: str = "./photo_inbox"
    google_drive_root_folder_id: str | None = None
    google_service_account_file: str | None = None

    @field_validator("editor_language")
    @classmethod
    def _normalize_editor_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("EDITOR_LANGUAGE cannot be empty")
        return normalized

    @field_validator("content_languages")
    @classmethod
    def _validate_content_languages(cls, value: str) -> str:
        codes = [code.strip().lower() for code in value.split(",") if code.strip()]
        if not codes:
            raise ValueError("CONTENT_LANGUAGES must contain at least one language code")
        if len(set(codes)) != len(codes):
            raise ValueError("CONTENT_LANGUAGES cannot contain duplicate language codes")
        return ",".join(codes)

    @property
    def content_language_codes(self) -> tuple[str, ...]:
        return tuple(self.content_languages.split(","))

    @property
    def canarias_publish_enabled(self) -> bool:
        return bool(self.canarias_api_url.strip())


settings = Settings()
