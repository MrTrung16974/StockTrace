"""Typed production-grade configuration."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from stocktrace.domain.entities.auto_trade import AutoTradePilotPolicy


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
    """AI analysis and translation settings — Google Gemini provider."""

    enabled: bool = False
    # Always "gemini" — kept as a field for forward compatibility
    provider: str = "gemini"
    api_key: SecretStr | None = None
    # Stable fast model; older 2.0 aliases have been retired by Gemini.
    model: str = "gemini-3.6-flash"
    # Backward-compatible first fallback, primarily for old deployments.
    fallback_model: str | None = "gemini-3.5-flash"
    # Extra alternatives used only when Gemini reports model retirement or quota exhaustion.
    fallback_models: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.1-pro-preview",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
        ],
    )
    max_tokens: int = Field(default=2048, ge=256, le=8192)
    temperature: float = Field(default=0.3, ge=0, le=2)
    request_timeout_seconds: float = Field(default=60.0, gt=0)
    cache_ttl_seconds: int = Field(default=1800, ge=60)
    market_cache_ttl_seconds: int = Field(default=1800, ge=60)
    report_cache_ttl_seconds: int = Field(default=300, ge=60)
    translate_news: bool = True

    @field_validator("fallback_models", mode="before")
    @classmethod
    def parse_fallback_models(cls, value: object) -> object:
        """Allow a comma-separated model chain in environment configuration."""
        if isinstance(value, str):
            return [model.strip() for model in value.split(",") if model.strip()]
        return value

    @property
    def has_api_key(self) -> bool:
        """Return whether a Gemini API key is configured."""
        return self.api_key is not None and self.api_key.get_secret_value().strip() != ""


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
    ca_bundle_path: str | None = None
    max_retries: int = Field(default=3, ge=0)
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1)
    circuit_breaker_reset_seconds: int = Field(default=60, ge=1)


class SchedulerSettings(BaseModel):
    """Scheduled Telegram job settings."""

    enabled: bool = True
    timezone: str = "Asia/Ho_Chi_Minh"
    watchlist_symbols: Annotated[list[str], NoDecode] = Field(default_factory=list)
    disabled_symbols: Annotated[list[str], NoDecode] = Field(default_factory=list)
    price_enabled: bool = True
    news_enabled: bool = True
    news_digest_hours: list[int] = Field(default_factory=lambda: [8, 12, 16, 20])
    price_alert_interval_minutes: int = Field(default=1, ge=1)
    price_change_threshold_percent: Decimal = Field(default=Decimal("0.1"), gt=0)
    price_alert_cooldown_minutes: int = Field(default=5, ge=0)
    suggestion_alert_enabled: bool = False
    suggestion_alert_interval_minutes: int = Field(default=5, ge=1)
    paper_confirmation_expiry_enabled: bool = False
    paper_confirmation_expiry_interval_minutes: int = Field(default=1, ge=1)
    news_digest_limit: int = Field(default=5, ge=1, le=20)
    news_symbol_delay_seconds: float = Field(default=0.5, ge=0)
    analysis_enabled: bool = False
    analysis_symbols: Annotated[list[str], NoDecode] = Field(default_factory=list)
    morning_report_hour: int = Field(default=8, ge=0, le=23)
    evening_report_hour: int = Field(default=20, ge=0, le=23)
    financial_daily_report_enabled: bool = True
    financial_daily_report_hour: int = Field(default=9, ge=0, le=23)
    market_analysis_enabled: bool = False
    market_daily_report_hour: int = Field(default=16, ge=0, le=23)
    market_morning_report_hour: int = Field(default=7, ge=0, le=23)
    market_evening_report_hour: int = Field(default=19, ge=0, le=23)
    trace_ingest_enabled: bool = True
    trace_ingest_hour: int = Field(default=7, ge=0, le=23)
    trace_ingest_limit: int = Field(default=20, ge=1, le=100)

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


class AutoTradeSettings(BaseModel):
    """Fail-closed limits for a separately approved auto-trading pilot."""

    enabled: bool = False
    allowed_symbols: Annotated[list[str], NoDecode] = Field(default_factory=list)
    max_notional_per_order: Decimal = Field(default=Decimal("1000000"), gt=0)
    max_notional_per_day: Decimal = Field(default=Decimal("2000000"), gt=0)
    max_orders_per_day: int = Field(default=1, ge=1)
    minimum_paper_observation_days: int = Field(default=30, ge=1)
    minimum_paper_completed_orders: int = Field(default=20, ge=1)
    policy_version: str = "auto-trade-pilot-v1"
    rollout_percentage: int = Field(default=0, ge=0, le=100)
    rollout_owner_ids: Annotated[list[str], NoDecode] = Field(default_factory=list)
    control_key: SecretStr | None = None
    control_key_header: str = "X-Auto-Trade-Control-Key"
    control_operator_id: str | None = None

    @field_validator("allowed_symbols", mode="before")
    @classmethod
    def parse_allowed_symbols(cls, value: object) -> object:
        """Allow a comma-separated pilot symbol allowlist in environment values."""
        if isinstance(value, str):
            return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
        return value

    @field_validator("rollout_owner_ids", mode="before")
    @classmethod
    def parse_rollout_owner_ids(cls, value: object) -> object:
        """Allow a comma-separated explicit owner rollout list."""
        if isinstance(value, str):
            return [owner_id.strip() for owner_id in value.split(",") if owner_id.strip()]
        return value

    @model_validator(mode="after")
    def validate_pilot_limits(self) -> AutoTradeSettings:
        """Keep configured limits internally coherent; approval remains a separate gate."""
        if self.max_notional_per_order > self.max_notional_per_day:
            raise ValueError("max_notional_per_order must not exceed max_notional_per_day.")
        if self.enabled and not self.allowed_symbols:
            raise ValueError(
                "enabled auto trading requires STOCKTRACE_AUTO_TRADE__ALLOWED_SYMBOLS.",
            )
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty.")
        if len(set(self.rollout_owner_ids)) != len(self.rollout_owner_ids):
            raise ValueError("rollout_owner_ids must not contain duplicates.")
        if self.control_key is not None and not (self.control_operator_id or "").strip():
            raise ValueError("control_operator_id is required when control_key is configured.")
        return self

    def to_pilot_policy(self) -> AutoTradePilotPolicy:
        """Map typed deployment limits into the pure deterministic pilot gate."""
        return AutoTradePilotPolicy(
            enabled=self.enabled,
            allowed_symbols=tuple(self.allowed_symbols),
            max_notional_per_order=self.max_notional_per_order,
            max_notional_per_day=self.max_notional_per_day,
            max_orders_per_day=self.max_orders_per_day,
            minimum_paper_observation=timedelta(days=self.minimum_paper_observation_days),
            minimum_paper_completed_orders=self.minimum_paper_completed_orders,
            policy_version=self.policy_version,
        )


class ObservabilitySettings(BaseModel):
    """Observability stack settings."""

    prometheus_enabled: bool = True
    prometheus_path: str = "/metrics"
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "stocktrace-api"


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
    auto_trade: AutoTradeSettings = Field(default_factory=AutoTradeSettings)
    ai: AISettings = Field(default_factory=AISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)


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
