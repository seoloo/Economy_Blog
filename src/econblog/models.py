"""파이프라인 단계 사이에서 주고받는 데이터 계약.

각 단계는 여기 정의된 모델만 입력/출력으로 사용한다. 필드를 추가하는 것은 괜찮지만
기존 필드의 의미나 이름을 바꾸면 모든 단계가 영향을 받으므로 피한다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Region = Literal["kr", "global"]
SourceKind = Literal["news", "blog", "official"]


# ---------------------------------------------------------------- 수집 / 분류


class Source(BaseModel):
    """config/sources.yaml 의 한 항목."""

    id: str
    name: str
    url: str
    region: Region
    kind: SourceKind = "news"
    lang: str = "ko"
    collector: str = "rss"


class Article(BaseModel):
    """수집한 기사 한 건. 원문 본문은 저장하지 않고 제목·요약·링크만 담는다."""

    source_id: str
    source_name: str
    region: Region
    kind: SourceKind
    lang: str
    title: str
    url: str
    summary: str = ""
    published: datetime | None = None


class ClassifiedArticle(BaseModel):
    article: Article
    topic: str
    importance: float = Field(ge=0.0, le=1.0)
    is_duplicate: bool = False


# ---------------------------------------------------------------- 시장 데이터


class SeriesSpec(BaseModel):
    """config/series.yaml 의 한 항목."""

    key: str
    label: str
    provider: str
    id: str
    unit: str = ""
    category: str = ""
    params: dict[str, str] = Field(default_factory=dict)


class Series(BaseModel):
    spec: SeriesSpec
    dates: list[date]
    values: list[float]

    @property
    def last(self) -> float | None:
        return self.values[-1] if self.values else None

    @property
    def prev(self) -> float | None:
        return self.values[-2] if len(self.values) >= 2 else None

    @property
    def last_date(self) -> date | None:
        return self.dates[-1] if self.dates else None

    @property
    def change(self) -> float | None:
        if self.last is None or self.prev is None:
            return None
        return self.last - self.prev

    @property
    def change_pct(self) -> float | None:
        if self.change is None or not self.prev:
            return None
        return self.change / self.prev * 100

    def last_days(self, days: int) -> "Series":
        """마지막 날짜 기준 최근 days 일(달력 기준) 구간."""
        if not self.dates:
            return self
        cutoff = self.dates[-1] - timedelta(days=days)
        pairs = [(d, v) for d, v in zip(self.dates, self.values) if d >= cutoff]
        return Series(spec=self.spec, dates=[d for d, _ in pairs], values=[v for _, v in pairs])


class MarketSnapshot(BaseModel):
    as_of: date
    series: dict[str, Series] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)

    def get(self, key: str) -> Series | None:
        return self.series.get(key)


# ---------------------------------------------------------------- 차트


class ChartSpec(BaseModel):
    """settings.yaml 의 charts 항목."""

    key: str
    type: str
    title: str
    series: list[str]
    days: int = 90
    note: str = ""


class Chart(BaseModel):
    key: str
    title: str
    path: Path
    alt_text: str
    source_note: str


# ---------------------------------------------------------------- 초안 (LLM 출력 스키마)


class Issue(BaseModel):
    title: str = Field(description="이슈 제목. 기사 제목을 그대로 쓰지 말고 직접 요약한다.")
    paragraphs: list[str] = Field(description="이슈 설명과 분석. 2~4개 문단.")
    reference_urls: list[str] = Field(description="참고한 기사 URL. 입력으로 받은 URL만 사용한다.")


class PostContent(BaseModel):
    """글쓴이(Writer)가 만들어야 하는 본문 구조. 레이아웃은 templates/ 가 담당한다."""

    title: str = Field(description="SEO를 고려한 글 제목. 날짜와 핵심 이슈를 포함한다.")
    lead: str = Field(description="오늘 시장을 2~3문장으로 요약한 도입부.")
    global_market: list[str] = Field(description="해외 시장 시황 문단 목록.")
    korea_market: list[str] = Field(description="국내 시장 시황 문단 목록.")
    issues: list[Issue] = Field(description="오늘의 주요 이슈 3~5개.")
    watch_points: list[str] = Field(description="앞으로 확인할 일정·지표 체크포인트.")
    tags: list[str] = Field(description="티스토리 태그 5~10개.")


class Draft(BaseModel):
    date: date
    content: PostContent
    charts: list[Chart] = Field(default_factory=list)
    references: list[Article] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RenderedPost(BaseModel):
    draft: Draft
    html: str
    preview_html: str
    output_dir: Path
