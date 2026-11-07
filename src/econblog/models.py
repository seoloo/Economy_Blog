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

# 차트·표 하단 출처 표기에 쓰는 데이터 제공처 이름
PROVIDER_NAMES = {"yahoo": "Yahoo Finance", "fred": "FRED", "ecos": "한국은행 ECOS", "sample": "샘플 데이터"}


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


class Quote(BaseModel):
    """시리즈의 마지막 값과 전일 대비 변화. 본문 표와 '오늘 시장 한눈에' 상자에 쓴다."""

    key: str
    label: str
    unit: str
    category: str
    provider: str
    as_of: date
    last: float
    change: float | None = None
    change_pct: float | None = None


class MarketSnapshot(BaseModel):
    as_of: date
    series: dict[str, Series] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)

    def get(self, key: str) -> Series | None:
        return self.series.get(key)

    def quotes(self) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for key, s in self.series.items():
            if s.last is None or s.last_date is None:
                continue
            out[key] = Quote(
                key=key, label=s.spec.label, unit=s.spec.unit, category=s.spec.category,
                provider=s.spec.provider, as_of=s.last_date, last=s.last,
                change=s.change, change_pct=s.change_pct,
            )
        return out


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
    paragraphs: list[str] = Field(description="이슈 설명과 분석. 3~5개 문단, 문단마다 1~2문장.")
    reference_urls: list[str] = Field(description="참고한 기사 URL. 입력으로 받은 URL만 사용한다.")


class PostContent(BaseModel):
    """글쓴이(Writer)가 만들어야 하는 본문 구조. 레이아웃은 templates/ 가 담당한다.

    필드 순서가 곧 LLM 이 쓰는 순서이므로, 글의 흐름대로 둔다.
    """

    title: str = Field(description="글 제목. 작성 요청에 적힌 형식(연재 머리말 | 날짜 | 핵심 한 줄)을 그대로 따른다.")
    lead: str = Field(description="도입부 2~3문장. 첫 문장은 독자에게 오늘 무엇을 정리했는지 말하고, 이어서 핵심 흐름을 요약한다.")
    summary_line: str = Field(description="오늘 시장을 한 문장(40자 안팎)으로 요약. '오늘 시장 한눈에' 상자 맨 위에 들어간다.")
    global_market: list[str] = Field(description="해외 시장 시황 문단 목록. 문단마다 1~2문장.")
    korea_market: list[str] = Field(description="국내 시장 시황 문단 목록. 문단마다 1~2문장.")
    korea_checkpoints: list[str] = Field(description="해외 흐름이 오늘 한국 증시에 줄 수 있는 영향 2~4개. 항목마다 1~2문장.")
    issues: list[Issue] = Field(description="오늘의 주요 이슈 3~5개.")
    watch_points: list[str] = Field(description="앞으로 확인할 일정·지표 체크포인트.")
    closing: str = Field(description="마무리 1~2문장. 오늘 내용을 한 줄로 정리하고 독자에게 건네는 짧은 말로 끝낸다.")
    tags: list[str] = Field(description="티스토리 태그 5~10개. 본문 끝 해시태그로도 쓴다.")


class Draft(BaseModel):
    date: date
    content: PostContent
    charts: list[Chart] = Field(default_factory=list)
    quotes: dict[str, Quote] = Field(default_factory=dict)
    references: list[Article] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RenderedPost(BaseModel):
    draft: Draft
    html: str
    preview_html: str
    output_dir: Path
