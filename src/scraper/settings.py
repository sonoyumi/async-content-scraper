from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/scraper.db"

    notifier_bot_token: str = ""
    notifier_chat_id: str = ""

    max_concurrent_fetches: int = 5
    max_concurrent_playwright: int = 2
    default_poll_interval_sec: int = 900
    download_media: bool = False

    log_level: str = "INFO"
    user_agent: str = "Mozilla/5.0 (compatible; ScraperBot/0.1; +https://example.com/bot)"

    sources_config_path: str = "config/sources.example.yaml"
    media_dir: str = "data/media"

    consecutive_errors_backoff_threshold: int = 5
    consecutive_errors_backoff_multiplier: float = 2.0
    consecutive_errors_backoff_max_multiplier: float = 24.0

    graceful_shutdown_timeout_sec: float = 20.0
    heartbeat_file: str = "data/heartbeat"


settings = Settings()
