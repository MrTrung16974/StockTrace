"""Typed production-grade configuration."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import AliasChoices, BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AppSettings(BaseModel):
    """Application metadata."""

    name: str = "StockTrace"
    version: str = "0.1.0"


class ApiSettings(BaseModel):
    """HTTP API settings."""

    host: str = "0.0.0.0"  # noqa: S104
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8000"])


class DatabaseSettings(BaseModel):
    """Database settings for SQLAlchemy async engines."""

    url: str = "sqlite+aiosqlite:///./data/stocktrace.db"
    echo: bool = False
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)

    @property
    def is_sqlite(self) -> bool:
        """Return whether the configured database is SQLite."""
        return self.url.startswith("sqlite")


class RedisSettings(BaseModel):
    """Redis cache settings."""

    url: str = "redis://localhost:6379/0"
    enabled: bool = True
    default_ttl_seconds: int = Field(default=300, ge=1)


class CacheSettings(BaseModel):
    """Market data cache TTL settings."""

    quote_ttl_seconds: int = Field(default=30, ge=1)
    news_ttl_seconds: int = Field(default=300, ge=1)


class AISettings(BaseModel):
    """AI analysis and translation settings."""

    enabled: bool = False
    provider: str = "openai"
    api_key: SecretStr | None = None
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    max_tokens: int = Field(default=1024, ge=256, le=4096)
    temperature: float = Field(default=0.3, ge=0, le=1)
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    cache_ttl_seconds: int = Field(default=1800, ge=60)
    translate_news: bool = True

    @property
    def has_api_key(self) -> bool:
        """Return whether an API key is configured."""
        return self.api_key is not None and self.api_key.get_secret_value().strip() != ""

    @property
    def resolved_base_url(self) -> str:
        """Return the configured or provider-default API base URL."""
        if self.base_url:
            return self.base_url.rstrip("/")
        defaults = {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
        }
        return defaults.get(self.provider.lower(), "https://api.openai.com/v1")


class TelegramSettings(BaseModel):
    """Telegram bot settings."""

    bot_token: SecretStr | None = None
    chat_id: str | None = None
    allowed_user_ids: list[int] = Field(default_factory=list)
    polling_enabled: bool = True
    drop_pending_updates: bool = True


class SecuritySettings(BaseModel):
    """Security and request protection settings."""

    api_key: SecretStr | None = None
    rate_limit_per_minute: int = Field(default=120, ge=1)
    api_key_header: str = "X-API-Key"
    public_paths: list[str] = Field(
        default_factory=lambda: [
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/health/live",
            "/health/ready",
            "/api/v1/stocks",
        ],
    )


class ProvidersSettings(BaseModel):
    """External provider execution policy."""

    request_timeout_seconds: float = Field(default=10.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1)
    circuit_breaker_reset_seconds: int = Field(default=60, ge=1)


class SchedulerSettings(BaseModel):
    """Scheduled Telegram job settings."""

    enabled: bool = True
    timezone: str = "Asia/Ho_Chi_Minh"
    watchlist_symbols: list[str] = Field(default_factory=list)
    disabled_symbols: list[str] = Field(default_factory=list)
    price_enabled: bool = True
    news_enabled: bool = True
    news_digest_hours: list[int] = Field(default_factory=lambda: [8, 12, 16, 20])
    price_alert_interval_minutes: int = Field(default=5, ge=1)
    news_digest_limit: int = Field(default=5, ge=1, le=20)
    news_symbol_delay_seconds: float = Field(default=0.5, ge=0)
    analysis_enabled: bool = False
    analysis_symbols: list[str] = Field(default_factory=list)
    morning_report_hour: int = Field(default=8, ge=0, le=23)
    evening_report_hour: int = Field(default=20, ge=0, le=23)

    @field_validator("watchlist_symbols", mode="before")
    @classmethod
    def parse_watchlist_symbols(cls, value: object) -> object:
        """Allow comma-separated watchlists in addition to JSON lists."""
        if isinstance(value, str):
            return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
        return value

    @field_validator("disabled_symbols", mode="before")
    @classmethod
    def parse_disabled_symbols(cls, value: object) -> object:
        """Allow comma-separated disabled symbols in addition to JSON lists."""
        if isinstance(value, str):
            return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
        return value

    @field_validator("analysis_symbols", mode="before")
    @classmethod
    def parse_analysis_symbols(cls, value: object) -> object:
        """Allow comma-separated analysis symbols in addition to JSON lists."""
        if isinstance(value, str):
            return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
        return value


class LoggingSettings(BaseModel):
    """Structured logging settings."""

    level: str = "INFO"
    json_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("json_enabled", "json"),
    )

    @field_validator("level")
    @classmethod
    def normalize_level(cls, value: str) -> str:
        """Normalize logging level names."""
        return value.upper()


class Settings(BaseSettings):
    """Root settings object loaded from env and dotenv."""

    model_config = SettingsConfigDict(
        env_prefix="STOCKTRACE_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    app: AppSettings = Field(default_factory=AppSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    providers: ProvidersSettings = Field(default_factory=ProvidersSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    ai: AISettings = Field(default_factory=AISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        """Require critical secrets in production."""
        if self.environment != Environment.PRODUCTION:
            return self

        missing: list[str] = []
        if self.telegram.bot_token is None:
            missing.append("STOCKTRACE_TELEGRAM__BOT_TOKEN")
        if self.telegram.chat_id is None:
            missing.append("STOCKTRACE_TELEGRAM__CHAT_ID")
        if self.security.api_key is None:
            missing.append("STOCKTRACE_SECURITY__API_KEY")
        if not self.telegram.allowed_user_ids:
            missing.append("STOCKTRACE_TELEGRAM__ALLOWED_USER_IDS")
        if missing:
            joined = ", ".join(missing)
            msg = f"Missing production secrets: {joined}"
            raise ValueError(msg)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache process settings."""
    return Settings()
