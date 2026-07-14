"""Assessment of stock-related news published by official Vietnamese authorities."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from stocktrace.application.services.market_data import NewsArticle

OFFICIAL_POLICY_DOMAINS = (
    "chinhphu.vn",
    "ssc.gov.vn",
    "sbv.gov.vn",
    "mof.gov.vn",
    "moj.gov.vn",
    "hose.vn",
    "hnx.vn",
    "vnx.vn",
)
OFFICIAL_POLICY_SOURCE_NAMES = (
    "chính phủ",
    "ủy ban chứng khoán",
    "ngân hàng nhà nước",
    "bộ tài chính",
    "bộ tư pháp",
    "sở giao dịch chứng khoán thành phố hồ chí minh",
    "sở giao dịch chứng khoán hà nội",
    "sở giao dịch chứng khoán việt nam",
)

_SUPPORT_KEYWORDS = (
    "phê duyệt",
    "tháo gỡ",
    "ưu đãi",
    "gia hạn",
    "nới",
    "giảm lãi suất",
    "đầu tư công",
    "quy hoạch",
)
_RISK_KEYWORDS = (
    "xử phạt",
    "thanh tra",
    "đình chỉ",
    "thu hồi",
    "siết",
    "hạn chế",
    "tăng thuế",
    "điều tra",
)


@dataclass(frozen=True, slots=True)
class PolicyNewsImpact:
    """A cautious, explainable classification of an official policy article."""

    label: str
    reason: str


class PolicyNewsAnalyzer:
    """Classify official policy news without turning it into investment advice."""

    def analyze(self, article: NewsArticle) -> PolicyNewsImpact | None:
        """Return an impact label only when the article has an official source."""
        if not self._is_official_source(article):
            return None

        text = f"{article.title} {article.summary or ''}".lower()
        risk_keywords = [word for word in _RISK_KEYWORDS if word in text]
        support_keywords = [word for word in _SUPPORT_KEYWORDS if word in text]
        if risk_keywords:
            return PolicyNewsImpact(
                label="Chính sách: rủi ro cần theo dõi",
                reason=f"Phát hiện nội dung: {', '.join(risk_keywords[:2])}.",
            )
        if support_keywords:
            return PolicyNewsImpact(
                label="Chính sách: hỗ trợ tiềm năng",
                reason=f"Phát hiện nội dung: {', '.join(support_keywords[:2])}.",
            )
        return PolicyNewsImpact(
            label="Chính sách: cập nhật chính thức",
            reason="Chưa đủ căn cứ để kết luận tác động tích cực hoặc tiêu cực.",
        )

    @staticmethod
    def _is_official_source(article: NewsArticle) -> bool:
        source_text = article.source.lower()
        host = urlparse(article.url).netloc.lower().split(":", maxsplit=1)[0]
        return any(
            domain in source_text or host == domain or host.endswith(f".{domain}")
            for domain in OFFICIAL_POLICY_DOMAINS
        ) or any(name in source_text for name in OFFICIAL_POLICY_SOURCE_NAMES)
