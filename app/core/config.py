from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "sqlite:///./data/trading_assistant.sqlite3"
    tradingview_webhook_secret: str = "change-me"

    kakao_channel_provider_url: str = ""
    kakao_channel_api_key: str = ""
    kakao_channel_sender_key: str = ""
    kakao_channel_id: str = ""
    kakao_channel_recipient_phone: str = ""
    kakao_channel_template_code: str = "TRADING_SIGNAL"
    enable_kakao_notifications: bool = False

    discord_webhook_url: str = ""
    discord_username: str = "Trading Assistant"
    enable_discord_notifications: bool = False
    enable_outcome_tracking: bool = True
    outcome_tracker_interval_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
