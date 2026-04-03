from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://appuser:apppassword@localhost:5432/tokyo_apartments"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Scraping behaviour
    scrape_concurrency: int = 2        # parallel browser contexts
    scrape_page_timeout: int = 30000   # ms
    scrape_result_ttl: int = 21600     # seconds (6h)
    proxy_url: str | None = None       # e.g. http://user:pass@host:port

    # Optional integrations (set later)
    firecrawl_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
