from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    google_api_key: str
    demo_mode: bool = True
    demo_operator_email: str = "demo@relay.example"
    demo_operator_password: str = "DemoPass123!"
    frontend_origin: str = "http://localhost:3000"
    gemini_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    semantic_threshold: float = 0.95
    cache_ttl_seconds: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
