import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:8672@localhost:5432/documentflow"
    )
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_QUEUE_NAME: str = "document_processing_queue"

    # Worker Crash Recovery & Lease Configuration
    WORKER_LEASE_DURATION_SECONDS: int = 60
    WORKER_HEARTBEAT_INTERVAL_SECONDS: int = 15
    WORKER_MAX_EXECUTION_TIME_SECONDS: int = 300
    WORKER_RECOVERY_INTERVAL_SECONDS: int = 30

    # Transactional Outbox Configuration
    OUTBOX_DISPATCH_INTERVAL_SECONDS: float = 5.0
    OUTBOX_BATCH_SIZE: int = 50
    OUTBOX_MAX_RETRIES: int = 5
    OUTBOX_BASE_BACKOFF_SECONDS: float = 2.0
    OUTBOX_MAX_BACKOFF_SECONDS: float = 60.0

    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".env"
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
