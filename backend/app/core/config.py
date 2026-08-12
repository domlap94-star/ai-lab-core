from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for AI Lab.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==========================================================
    # Application
    # ==========================================================

    app_name: str = "AI-Lab"
    environment: str = "development"
    debug: bool = False

    # ==========================================================
    # Database
    # ==========================================================

    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # ==========================================================
    # JWT
    # ==========================================================

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ==========================================================
    # Administrator
    # ==========================================================

    admin_username: str
    admin_email: str
    admin_password: str

    # ==========================================================
    # Integration authentication
    # ==========================================================

    n8n_ingest_api_key: str

    # ==========================================================
    # AI providers and internal services
    # ==========================================================

    ollama_url: str = "http://ollama:11434"
    openwebui_url: str = "http://open-webui:8080"

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # ==========================================================
    # Knowledge layer / embeddings
    # ==========================================================

    embedding_model: str = "qwen3-embedding:0.6b"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 32
    embedding_version: str = "v1"

    qdrant_document_chunks_collection: str = (
        "ai_lab_document_chunks"
    )

    n8n_url: str = "http://n8n:5678"

    # ==========================================================
    # Paths
    # ==========================================================

    data_dir: str = "/data"

    @computed_field
    @property
    def project_dir(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @computed_field
    @property
    def backend_dir(self) -> Path:
        return self.project_dir / "backend"

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:"
            f"{self.postgres_password}@"
            f"{self.postgres_host}:"
            f"{self.postgres_port}/"
            f"{self.postgres_db}"
        )


settings = Settings()