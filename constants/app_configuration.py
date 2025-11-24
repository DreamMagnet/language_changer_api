from typing import Optional
from pydantic import HttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables"""

    # MongoDB Configuration
    mongo_uri: str
    mongo_db: str
    mongo_collection: str
    mongo_timeout_ms: int

    # Cache Configuration
    cache_ttl_seconds: int

    # Proxy Configuration
    default_proxy_url: Optional[HttpUrl] = None
    default_timeout: float
    max_timeout: float
    verify_ssl: bool

    # Authentication Configuration
    login_token: str

    # Application Configuration
    app_host: str
    app_port: int
    app_reload: bool
    log_level: str

    model_config = {
        "env_file": ".env",
        "env_prefix": "TRANSLATIONS_",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton instance
settings = Settings()