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
    label_en: str = ""  # 영어 계정(인스타 카드)에서 쓰는 이름
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
    position: Literal["cover", "lead", "body"] = "body"  # 본문 위치: 맨 위 대표 이미지 / 요약 상자 아래 / 차트 섹션


class Chart(BaseModel):
    key: str
    title: str
    path: Path
    alt_text: str
    source_note: str
    position: Literal["cover", "lead", "body"] = "body"
    url: str | None = None  # 공개 주소에 올렸으면 그 주소 (없으면 본문에 업로드 안내 상자)
    shared: bool = False  # 날짜와 상관없이 매번 같은 이미지(고정 썸네일). 공개 레포 shared/ 에 한 번만 올린다


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
    kind: Literal["daily"] = "daily"
    date: date
    content: PostContent
    charts: list[Chart] = Field(default_factory=list)
    quotes: dict[str, Quote] = Field(default_factory=dict)
    references: list[Article] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- 경제 공부 글 (오래 읽히는 개념 설명)


class GuideTopic(BaseModel):
    """config/guides.yaml 의 한 항목."""

    id: str
    keyword: str            # 검색 키워드이자 대표 이미지의 큰 글자 (예: 장단기 금리차)
    subtitle: str           # 대표 이미지 아래 줄 (예: 금리 역전은 왜 경기침체 신호일까)
    angle: str              # 글에서 꼭 다룰 내용
    series: list[str] = Field(default_factory=list)   # 본문에 '지금 수치'로 넣을 시리즈
    charts: list[ChartSpec] = Field(default_factory=list)


class GuideSection(BaseModel):
    heading: str = Field(description="소제목. 독자가 궁금해할 질문이나 핵심을 짧게.")
    paragraphs: list[str] = Field(description="문단 목록. 문단마다 1~3문장.")


class GuideQA(BaseModel):
    question: str = Field(description="독자가 실제로 검색할 법한 질문.")
    answer: str = Field(description="2~3문장 답변.")


class GuidePost(BaseModel):
    """경제 공부 글 본문. 필드 순서가 곧 LLM 이 쓰는 순서다."""

    title: str = Field(description="검색 키워드로 시작하는 제목 (40자 안팎).")
    lead: str = Field(description="도입부 2~3문장. 독자가 왜 이 글을 찾았을지 짚고, 무엇을 알 수 있는지 말한다.")
    summary_points: list[str] = Field(description="핵심 요약 3개. 각 한 문장.")
    sections: list[GuideSection] = Field(description="본문 소제목 4~6개.")
    now_comment: str = Field(description="'지금 수치' 데이터를 근거로 현재 상황을 해석하는 2~3문장.")
    faq: list[GuideQA] = Field(description="자주 묻는 질문 2~3개.")
    closing: str = Field(description="마무리 1~2문장.")
    tags: list[str] = Field(description="티스토리 태그 5~10개.")


class NowRow(BaseModel):
    """경제 공부 글의 '지금 수치' 한 줄. 수집한 데이터에서 계산한 문자열."""

    key: str
    label: str
    as_of: str
    value: str
    year_ago: str
    range: str


class GuideDraft(BaseModel):
    kind: Literal["guide"] = "guide"
    date: date
    topic: GuideTopic
    content: GuidePost
    charts: list[Chart] = Field(default_factory=list)
    now_rows: list[NowRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RenderedPost(BaseModel):
    draft: Draft | GuideDraft
    html: str
    preview_html: str
    output_dir: Path


# ---------------------------------------------------------------- 인스타 카드뉴스 (LLM 출력 스키마)


class CardStory(BaseModel):
    headline: list[str] = Field(description="카드 제목 두 줄. 한국어는 줄마다 12자 안팎, 영어는 20자 안팎.")
    paragraphs: list[str] = Field(
        description="본문 두 문단. 한국어는 문단마다 70~100자, 영어는 25~35단어. 넘치면 카드에서 글자가 작아진다. "
                    "가장 중요한 수치나 구절 1~2곳만 **굵게**.")
    why: str = Field(description="'왜 중요할까' 상자에 들어갈 한 문장. 한국어 50자 안팎, 영어 20단어 안팎.")
    photo_query: str = Field(
        description="배경 사진 검색어. 영어 2~3단어로 사물·장소를 쓴다 (예: circuit board, server room, oil refinery, "
                    "stock market screen, new york skyline). wafer·chips 처럼 음식으로도 읽히는 단어와 사람이 나올 검색어는 피한다.")


class CardEvent(BaseModel):
    when: str = Field(description="날짜. 예: 11/12(수), Wed 11/12. 기사에 날짜가 없으면 '이번 주' 또는 'This week'.")
    title: str = Field(description="일정 이름. 짧게.")
    detail: str = Field(description="왜 볼 만한지 한 줄.")
    tag: str = Field(description="분류 한 단어. 예: 지표, 실적, 금리 / Data, Earnings, Fed")


class CardCheck(BaseModel):
    key: str = Field(description="시장 데이터 표 맨 앞 [대괄호] 안의 key. 예: usdkrw, kospi, st_hynix")
    title: str = Field(description="항목 이름과 기준. 형식: [이름] [기준 숫자]. 한국어 14자, 영어 24자 안팎.")
    detail: str = Field(description="그 기준에서 볼 점 한 줄. 한국어 '~하는지'로 끝나는 20자 안팎, 영어 'whether …' 8단어 안팎.")


class CardCopy(BaseModel):
    """인스타 카드뉴스 한 묶음의 글. 숫자 카드(숫자판·업종·대형주)는 데이터로 그리고 여기에는 글만 담는다."""

    cover_lines: list[str] = Field(
        description="표지 제목 두 줄. 오늘 시장을 가장 잘 보여 주는 숫자를 넣는다. 줄마다 한국어 10자 안팎, 영어 18자 안팎.")
    cover_photo_query: str = Field(description="표지 배경 사진 검색어. 영어 2~3단어.")
    board_note: str = Field(description="숫자판 장 제목 아래 한 줄 요약. 한국어 30자 안팎, 영어 12단어 안팎.")
    stories: list[CardStory] = Field(description="이슈 카드 두 장. 오늘 시장을 움직인 재료 순서대로.")
    sector_title: str = Field(description="미국 업종 히트맵 장 제목. 한국어 12자, 영어 25자 안팎.")
    movers_title: str = Field(description="미국 대형주 등락 장 제목. 한국어 12자, 영어 25자 안팎.")
    asia_note: str = Field(description="아시아·한국 체크 장 아래 상자에 들어갈 한두 문장. 그 장이 없는 계정은 빈 문자열.")
    summary: list[str] = Field(
        default_factory=list,
        description="요약 장(summary)에 들어갈 그날 요약 세 줄. 그 장이 없는 계정은 빈 목록. 영어는 줄마다 12~18단어.")
    events: list[CardEvent] = Field(description="앞으로 볼 일정 0~5개. 기사나 블로그 글에 나온 일정만. 없으면 빈 목록.")
    checklist: list[CardCheck] = Field(
        description="마지막 장 체크리스트 3개. 다음 거래일에 확인할 지수·환율·종목과 기준. 시장 데이터 표에 있는 항목만.")
    caption: str = Field(
        description="게시물 캡션 본문(해시태그 제외). 첫 줄 제목, 번호 붙인 요약 3개, 다음에 볼 것. 한국어 600~900자, 영어 120~180단어.")
    hashtags: list[str] = Field(description="해시태그 8~12개. # 없이 띄어쓰기 없는 단어로.")


class CardSet(BaseModel):
    """한 계정의 하루치 카드뉴스. 게시·메일 단계로 넘긴다."""

    account: str                     # settings.instagram.accounts 의 key
    brand: str
    lang: str
    date: date
    text: CardCopy
    images: list[Path] = Field(default_factory=list)   # 카드 JPEG (게시 순서)
    caption: str = ""                # 캡션 + 해시태그 + 출처 (게시용 완성본)
    urls: list[str] = Field(default_factory=list)       # 공개 주소에 올린 카드 주소
    media_id: str | None = None      # 인스타에 게시했으면 그 게시물 ID
    warnings: list[str] = Field(default_factory=list)
    output_dir: Path


class IntroSlide(BaseModel):
    """계정 소개 게시물 한 장 (config/intro.yaml). kind: cover, text, shots, end."""

    kind: Literal["cover", "text", "shots", "end"]
    kicker: str = ""
    title: str = ""
    lines: list[str] = Field(default_factory=list)    # 표지 제목 두 줄
    paras: list[str] = Field(default_factory=list)    # 본문 문단 (**굵게** 가능)
    shots: list[int] = Field(default_factory=list)    # 예시로 보여 줄 카드 번호 (1부터)
    box_label: str = ""                               # text 장 아래 짙은 상자 (예: 올라오는 날)
    box: str = ""


class IntroPost(BaseModel):
    """프로필 맨 위에 고정해 두는 계정 소개 게시물. 사람이 쓴 글을 그대로 쓰고 LLM 을 거치지 않는다."""

    caption: str                     # {example_date} 자리에 예시 카드 날짜가 들어간다
    hashtags: list[str] = Field(default_factory=list)
    slides: list[IntroSlide]
