"""Telegram delivery helper tests."""

from __future__ import annotations

from stocktrace.infrastructure.telegram.delivery import (
    split_telegram_message,
    strip_html_tags,
)

TEST_MESSAGE_LIMIT = 1200
EXPECTED_LONG_LINE_PARTS = 3


def test_split_telegram_message_keeps_short_text() -> None:
    text = "short message"
    assert split_telegram_message(text) == [text]


def test_split_telegram_message_splits_on_line_boundaries() -> None:
    lines = [f"line-{index}" for index in range(500)]
    text = "\n".join(lines)
    parts = split_telegram_message(text, limit=TEST_MESSAGE_LIMIT)
    assert len(parts) > 1
    assert "".join(parts) == text
    for part in parts:
        assert len(part) <= TEST_MESSAGE_LIMIT


def test_split_telegram_message_splits_one_oversized_line() -> None:
    text = "x" * 2500

    parts = split_telegram_message(text, limit=TEST_MESSAGE_LIMIT)

    assert len(parts) == EXPECTED_LONG_LINE_PARTS
    assert "".join(parts) == text
    assert all(len(part) <= TEST_MESSAGE_LIMIT for part in parts)


def test_strip_html_tags_removes_markup() -> None:
    text = '📊 <b>BÁO CÁO</b>\n<a href="https://x.com">Title</a>'
    plain = strip_html_tags(text)
    assert "<b>" not in plain
    assert "BÁO CÁO" in plain
    assert "Title" in plain
