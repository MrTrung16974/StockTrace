"""Development configuration helpers."""

from __future__ import annotations

from stocktrace.infrastructure.config.settings import Environment, Settings


def load_dev_settings() -> Settings:
    """Load settings with development defaults."""
    return Settings(_env_file=None, environment=Environment.DEVELOPMENT, debug=True)
