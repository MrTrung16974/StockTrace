"""Telegram delivery helper tests."""

from __future__ import annotations

from stocktrace.infrastructure.telegram.delivery import (
    split_telegram_message,
    strip_html_tags,
)


def test_split_telegram_message_keeps_short_text() -> None:
    text = "short message"
    assert split_telegram_message(text) == [text]


def test_split_telegram_message_splits_on_line_boundaries() -> None:
    lines = [f"line-{index}" for index in range(500)]
    text = "\n".join(lines)
    parts = split_telegram_message(text, limit=1200)
    assert len(parts) > 1
    assert "\n".join(parts) == text
    for part in parts:
        assert len(part) <= 1200


def test_strip_html_tags_removes_markup() -> None:
    text = '📊 <b>BÁO CÁO</b>\n<a href="https://x.com">Title</a>'
    plain = strip_html_tags(text)
    assert "<b>" not in plain
    assert "BÁO CÁO" in plain
    assert "Title" in plain
