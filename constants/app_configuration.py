from typing import Optional
from pydantic import HttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables"""

    # MongoDB Configuration
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "testing"
    mongo_collection: str = "translations"
    mongo_timeout_ms: int = 5000

    # Cache Configuration
    cache_ttl_seconds: int = 300

    # Proxy Configuration
    default_proxy_url: Optional[HttpUrl] = None
    default_timeout: float = 20.0
    max_timeout: float = 300.0
    verify_ssl: bool = False

    # Application Configuration
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    app_reload: bool = True
    log_level: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_prefix": "TRANSLATIONS_",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton instance
settings = Settings()