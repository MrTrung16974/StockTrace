"""Production configuration helpers."""

from __future__ import annotations

from stocktrace.infrastructure.config.settings import Environment, Settings


def load_prod_settings() -> Settings:
    """Load settings with production validation enabled."""
    return Settings(_env_file=None, environment=Environment.PRODUCTION, debug=False)
