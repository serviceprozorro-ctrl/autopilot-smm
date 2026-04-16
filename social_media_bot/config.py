import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    # Use dedicated env var for bot DB to avoid conflict with Replit's DATABASE_URL
    bot_database_url: str = os.getenv("BOT_DATABASE_URL", "sqlite+aiosqlite:///./social_media.db")
    api_host: str = "0.0.0.0"
    api_port: int = 3000
    secret_key: str = os.getenv("SESSION_SECRET", "change-me-in-production")
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
