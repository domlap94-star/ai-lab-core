from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI-Lab"
    app_version: str = "1.0.0"
    api_version: int = 1
    minimum_app_version: str = "1.0.0"
    latest_app_version: str = "1.0.0"

    environment: str = "development"
    debug: bool = False

    cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    admin_username: str
    admin_email: str
    admin_password: str

    n8n_ingest_api_key: str

    ollama_url: str = "http://ollama:11434"
    openwebui_url: str = "http://open-webui:8080"

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    embedding_model: str = "qwen3-embedding:0.6b"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 32
    embedding_version: str = "v1"

    qdrant_document_chunks_collection: str = (
        "ai_lab_document_chunks"
    )

    n8n_url: str = "http://n8n:5678"
    mail_send_webhook_url: str | None = None
    mail_send_webhook_secret: str | None = None
    mail_send_timeout_seconds: float = 45.0
    mail_reconcile_webhook_url: str | None = None
    mail_reconcile_webhook_secret: str | None = None
    mail_reconcile_timeout_seconds: float = 120.0

    openai_api_key: str | None = None
    openai_client_reconstruction_model: str = "gpt-5.6"

    data_dir: str = "/data"
    vision_supervisor_url: str = "http://host.docker.internal:8787"
    vision_automation_enabled: bool = False

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

    @computed_field
    @property
    def cors_origin_list(self) -> list[str]:
        return [
            value.strip()
            for value in self.cors_origins.split(",")
            if value.strip()
        ]


settings = Settings()
