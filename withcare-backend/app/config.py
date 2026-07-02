from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gcp_project_id: str
    gemini_location: str = "us-central1"
    gemini_model: str = "gemini-2.5-flash"
    firestore_database: str = "(default)"
    google_application_credentials: str = "service-account.json"
    google_calendar_mcp_url: str = ""
    google_maps_api_key: str = ""
    google_oauth_client_id: str = ""   # Web OAuth client ID for "Sign in with Google"
    environment: str = "development"
    log_level: str = "INFO"
    max_agent_turns: int = 5


settings = Settings()
