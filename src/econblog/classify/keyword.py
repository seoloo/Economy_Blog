"""API 키 없이 동작하는 키워드 기반 분류기 (Laya 대체용)."""

from __future__ import annotations

from datetime import datetime, timezone

from econblog.classify.base import Classifier
from econblog.models import Article, ClassifiedArticle

# settings.yaml 의 topics 설명(한국어)에 더해 영어 기사용 키워드를 보강한다.
EXTRA_KEYWORDS: dict[str, list[str]] = {
    "rates": ["fed", "fomc", "rate", "yield", "treasury", "bond", "powell", "ecb", "boj", "한은", "금통위", "국채"],
    "fx": ["dollar", "currency", "yen", "won", "forex", "환율", "달러"],
    "equity": ["stock", "s&p", "nasdaq", "dow", "rally", "selloff", "코스피", "코스닥", "증시", "주가"],
    "tech": ["chip", "semiconductor", "nvidia", "ai ", "apple", "microsoft", "삼성전자", "sk하이닉스", "반도체"],
    "macro": ["inflation", "cpi", "pce", "jobs", "payroll", "gdp", "unemployment", "recession", "물가", "고용", "성장률"],
    "trade": ["tariff", "trade", "china", "sanction", "관세", "수출", "수입", "무역"],
    "energy": ["oil", "crude", "opec", "gold", "commodit", "유가", "원유", "금값"],
    "realestate": ["housing", "mortgage", "home sales", "real estate", "아파트", "부동산", "주택", "전세"],
    "earnings": ["earnings", "revenue", "guidance", "profit", "quarter", "실적", "영업이익", "매출"],
    "crypto": ["bitcoin", "crypto", "ether", "비트코인", "가상자산", "코인"],
}

# 시황 글에서 비중이 큰 키워드. 등장하면 중요도를 올린다.
HIGH_IMPACT = [
    "fed", "fomc", "cpi", "inflation", "jobs report", "payroll", "rate cut", "rate hike", "recession",
    "기준금리", "금통위", "연준", "물가", "환율", "코스피", "외국인", "관세",
]
KIND_BASE = {"official": 0.6, "news": 0.45, "blog": 0.4}


class KeywordClassifier(Classifier):
    def _keywords(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for topic, desc in self.topics.items():
            words = [w.strip().lower() for w in desc.split(",") if w.strip()]
            result[topic] = words + EXTRA_KEYWORDS.get(topic, [])
        return result

    def classify(self, articles: list[Article]) -> list[ClassifiedArticle]:
        keywords = self._keywords()
        now = datetime.now(timezone.utc)
        out: list[ClassifiedArticle] = []
        for a in articles:
            text = f"{a.title} {a.summary}".lower()
            scores = {t: sum(text.count(w) for w in ws) for t, ws in keywords.items() if t != "other"}
            best = max(scores, key=scores.get) if scores and max(scores.values()) > 0 else "other"

            importance = KIND_BASE.get(a.kind, 0.4)
            importance += min(0.3, 0.1 * sum(1 for w in HIGH_IMPACT if w in text))
            if best == "other":
                importance -= 0.15
            if a.published:
                age_h = (now - a.published).total_seconds() / 3600
                importance += 0.1 if age_h < 12 else 0.0
            out.append(ClassifiedArticle(article=a, topic=best, importance=max(0.0, min(1.0, importance))))
        return out
