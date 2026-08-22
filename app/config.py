from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:1.7b"
    notion_token: str
    notion_api_version: str = "2026-03-11"
    notion_inbox_data_source_id: str
    notion_finances_data_source_id: str
    notion_wishlist_data_source_id: str
    notion_places_data_source_id: str
    notion_calendar_data_source_id: str
    notion_routine_data_source_id: str
    partner_name: str = "Carol"
    app_timezone: str = "America/Sao_Paulo"
    worker_poll_seconds: int = 10
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

settings = Settings()
