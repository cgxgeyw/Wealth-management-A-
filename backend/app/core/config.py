from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "A-Share Trading Agent"
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "sqlite:///./data/app.db"
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="LLM_BASE_URL",
    )
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")
    llm_timeout_seconds: float = Field(default=45, validation_alias="LLM_TIMEOUT_SECONDS")
    embedding_api_key: str = Field(default="", validation_alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(
        default="http://198.18.0.1:1235",
        validation_alias="EMBEDDING_BASE_URL",
    )
    embedding_model: str = Field(
        default="text-embedding-qwen3-embedding-0.6b",
        validation_alias="EMBEDDING_MODEL",
    )
    embedding_timeout_seconds: float = Field(default=30, validation_alias="EMBEDDING_TIMEOUT_SECONDS")
    faiss_index_dir: str = Field(default="./data/faiss", validation_alias="FAISS_INDEX_DIR")
    faiss_enabled: bool = Field(default=False, validation_alias="FAISS_ENABLED")
    cors_origins_raw: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
