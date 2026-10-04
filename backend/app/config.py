import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:8672@localhost:5432/documentflow"
    )
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".env"
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
