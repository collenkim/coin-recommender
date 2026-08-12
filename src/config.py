from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="config/settings.yaml",
        yaml_file_encoding="utf-8",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Unit 1: data-pipeline ---
    db_path: str = "data/coin_recommender.db"
    top_n_candidates: int = 20
    recommendations_per_exchange: int = 5
    bootstrap_min_candles: int = 100
    backtest_lookback_days: int = 1825
    http_timeout_seconds: float = 10.0
    http_max_retries: int = 3
    upbit_request_delay_seconds: float = 0.1

    # --- Unit 3: api-service ---
    # Telegram has no generic "webhook URL" for outbound bot messages (unlike Discord) --
    # it requires a bot token + chat id via the Bot API (see notifier.py).
    telegram_bot_token: str | None = None  # secret, set via .env only (SECURITY-12)
    telegram_chat_id: str | None = None  # set via .env only
    discord_webhook_url: str | None = None  # secret, set via .env only
    slack_webhook_url: str | None = None  # secret, set via .env only (Slack Incoming Webhook URL)
    scheduler_misfire_grace_seconds: int = 300

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        # env/.env override settings.yaml (secrets never live in settings.yaml — SECURITY-12)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


settings = Settings()
