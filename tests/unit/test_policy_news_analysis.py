"""Tests for official-policy news assessment."""

from stocktrace.application.services.market_data import NewsArticle
from stocktrace.application.services.policy_news_analysis import PolicyNewsAnalyzer


def _article(*, source: str, url: str, title: str) -> NewsArticle:
    return NewsArticle(
        ticker="MBB",
        title=title,
        summary=None,
        source=source,
        url=url,
    )


def test_policy_analyzer_marks_official_supportive_news() -> None:
    result = PolicyNewsAnalyzer().analyze(
        _article(
            source="Ngân hàng Nhà nước Việt Nam",
            url="https://news.google.com/rss/articles/example",
            title="Quyết định giảm lãi suất điều hành",
        ),
    )

    assert result is not None
    assert result.label == "Chính sách: hỗ trợ tiềm năng"
    assert "giảm lãi suất" in result.reason


def test_policy_analyzer_marks_official_risk_news() -> None:
    result = PolicyNewsAnalyzer().analyze(
        _article(
            source="ssc.gov.vn",
            url="https://ssc.gov.vn/xu-phat",
            title="Quyết định xử phạt vi phạm hành chính",
        ),
    )

    assert result is not None
    assert result.label == "Chính sách: rủi ro cần theo dõi"


def test_policy_analyzer_ignores_unofficial_sources() -> None:
    result = PolicyNewsAnalyzer().analyze(
        _article(
            source="CafeF",
            url="https://cafef.vn/mbb.htm",
            title="MBB được phê duyệt kế hoạch mới",
        ),
    )

    assert result is None
