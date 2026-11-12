"""설정 로딩. YAML(config/)은 동작 방식, 환경변수(.env / Secrets)는 비밀값을 담는다."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from econblog.models import ChartSpec, GuideTopic, IntroPost, SeriesSpec, Source

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class CollectSettings(BaseModel):
    lookback_hours: int = 30
    max_per_source: int = 30
    timeout_sec: int = 15
    user_agent: str = "EconomyBlogBot/0.1 (+https://github.com/seoloo/Economy_Blog)"


class ClassifySettings(BaseModel):
    provider: str = "laya"
    fallback: str = "keyword"
    laya_model: str | None = "multilingual"
    laya_min_confidence: float = 0.3
    laya_weight: float = 0.7
    topics: dict[str, str] = Field(default_factory=dict)
    top_n_per_region: int = 8
    dedupe_threshold: float = 0.55


class MarketSettings(BaseModel):
    lookback_days: int = 200


class WriteSettings(BaseModel):
    provider: str = "claude"
    fallback: str = "template"
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    max_tokens: int = 16000


class PostSettings(BaseModel):
    """글 구성. 표와 요약 상자의 수치는 LLM 이 아니라 시장 데이터에서 바로 만든다."""

    series_title: str = "미국증시·코스피 시황"   # 제목 뒤쪽 연재 머리말 (검색 키워드)
    glance: list[str] = Field(default_factory=list)          # '오늘 시장 한눈에' 상자
    global_table: list[str] = Field(default_factory=list)    # 해외 시장 표
    korea_table: list[str] = Field(default_factory=list)     # 국내 시장 표
    blog_rss: str = ""            # 우리 블로그 RSS. 글 끝 '최근에 올라온 글' 링크를 여기서 가져온다
    recent_posts: int = 3


class PublishSettings(BaseModel):
    """차트 PNG 를 올릴 공개 레포. 비어 있거나 CHARTS_REPO_TOKEN 이 없으면 올리지 않는다."""

    repo: str = ""        # 예: seoloo/econblog-assets
    branch: str = "main"
    base_url: str = ""    # 예: https://seoloo.github.io/econblog-assets (GitHub Pages)


class GuideSettings(BaseModel):
    """경제 공부 글. 주제는 config/guides.yaml 순서대로 쓴다.

    자동 실행일(weekdays)마다 다음 주제로 넘어간다. 상태를 저장하지 않으려고
    start_date 부터 오늘까지 지난 실행일 수로 주제 번호를 계산한다.
    수동으로 몇 편을 먼저 만들었다면 start_index 를 그만큼 올린다.
    """

    weekdays: list[int] = Field(default_factory=lambda: [2, 5])  # 0=월 ... 6=일 (KST)
    start_date: date | None = None
    start_index: int = 0
    lookback_days: int = 1900   # 장기 차트용 데이터 기간 (약 5년)


class GuardSettings(BaseModel):
    max_shared_chars: int = 40
    # AI 가 쓴 티가 나는 표현과 글 한 편에서 허용하는 횟수. 넘으면 경고한다.
    ai_phrases: dict[str, int] = Field(default_factory=dict)


class CardAccount(BaseModel):
    """인스타 계정 하나. 카드 구성과 게시용 비밀값 이름을 담는다."""

    key: str                       # 출력 폴더·파일 이름에 쓰는 짧은 이름 (kr, en)
    lang: Literal["ko", "en"]
    brand: str                     # 카드 왼쪽 위와 마지막 장에 들어가는 이름
    brand_dot: str = ""            # 이름 뒤에 붙는 색깔 점 (그냥모아.)
    token_env: str                 # 액세스 토큰 환경변수 이름 (GitHub Secrets)
    user_env: str                  # 인스타 계정 숫자 ID 환경변수 이름
    slides: list[str]              # 카드 순서: cover, board, story, sectors, movers, check, events, closing
    chips: list[str] = Field(default_factory=list)   # 표지 숫자 칩 (series key)
    board: list[str] = Field(default_factory=list)   # 숫자판 (series key, 10개)
    check: list[str] = Field(default_factory=list)   # 아시아·한국 체크 (series key)
    reels: bool = True               # false 면 이 계정은 릴스를 만들지도 올리지도 않는다 (캐러셀만)
    # 마지막 장 맨 아래 노란 띠 (블로그 안내). 비우면 띠를 넣지 않는다. 문구는 사람이 정한 것만 쓴다
    blog_line: str = ""
    blog_line_tail: str = ""         # 띠 오른쪽 작은 글자 (예: 프로필 링크 ↗)


class MusicTrack(BaseModel):
    """릴스 배경 음악 한 곡. 상업적 사용이 허용되고 Content ID 에 등록되지 않은 무료 음원만 쓴다."""

    title: str
    artist: str
    page: str                      # 라이선스를 확인한 곡 페이지
    url: str                       # 실행할 때마다 내려받는 MP3 주소 (레포에 음원 파일을 올리지 않는다)


class ReelSettings(BaseModel):
    """카드를 이어 붙인 세로 영상(릴스). 캐러셀과 같은 날 같이 올린다."""

    enabled: bool = True
    share_to_feed: bool = False    # false 면 릴스 탭·추천에만 나오고 프로필 격자와 피드에는 안 나온다
    music: list[MusicTrack] = Field(default_factory=list)   # 날짜마다 돌아가며 쓴다


class InstagramSettings(BaseModel):
    """인스타 카드뉴스. enabled 면 시황 글과 같은 실행에서 카드를 만들어 메일로 보낸다.

    publish 가 true 이고 계정 토큰이 있으면 인스타에 바로 게시한다. 처음에는 메일로만 받아 확인한다.
    """

    enabled: bool = False
    publish: bool = False
    render_images: bool = True     # 카드 JPEG 을 Chrome 으로 찍는다 (끄면 HTML 만 만든다)
    photos: bool = True            # Pixabay 배경 사진 (PIXABAY_API_KEY 필요, 없으면 단색 배경)
    review: bool = True            # 카드 글을 쓴 뒤 Claude 교열 단계를 한 번 더 거친다
    disclaimer: bool = False       # 캡션 끝·마지막 카드 아래 "투자 권유 아님" 문구 (블로그 글은 상관없이 항상 넣는다)
    # 자동 게시하는 요일 (0=월). 월요일 아침엔 토요일 이후 새로 열린 장이 없어 같은 숫자가 두 번 올라가므로 뺀다
    publish_weekdays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    graph_version: str = "v23.0"
    accounts: list[CardAccount] = Field(default_factory=list)
    reels: ReelSettings = Field(default_factory=ReelSettings)
    # 카드에 나오면 안 되는 모호한 표현 (언어별). 나오면 경고를 붙인다.
    vague_phrases: dict[str, list[str]] = Field(default_factory=dict)
    # 개인에 대한 의혹·소문처럼 사람이 확인해야 하는 표현 (언어별). 나오면 경고를 붙여 자동 게시를 멈춘다.
    sensitive_phrases: dict[str, list[str]] = Field(default_factory=dict)

    def reels_on(self, account: CardAccount) -> bool:
        """이 계정에 릴스를 만들고 올리는지. 전체 스위치와 계정별 스위치가 둘 다 켜져야 한다."""
        return self.reels.enabled and account.reels


class DeliverSettings(BaseModel):
    methods: list[str] = Field(default_factory=lambda: ["local"])


class Settings(BaseModel):
    timezone: str = "Asia/Seoul"
    output_dir: Path = Path("output")
    blog_name: str = "그냥모아"
    thumbnails: dict[str, str] = Field(default_factory=dict)  # 글 종류(daily·guide)별 고정 대표 이미지 경로
    collect: CollectSettings = Field(default_factory=CollectSettings)
    classify: ClassifySettings = Field(default_factory=ClassifySettings)
    market: MarketSettings = Field(default_factory=MarketSettings)
    charts: list[ChartSpec] = Field(default_factory=list)
    write: WriteSettings = Field(default_factory=WriteSettings)
    post: PostSettings = Field(default_factory=PostSettings)
    publish: PublishSettings = Field(default_factory=PublishSettings)
    guide: GuideSettings = Field(default_factory=GuideSettings)
    guard: GuardSettings = Field(default_factory=GuardSettings)
    deliver: DeliverSettings = Field(default_factory=DeliverSettings)
    instagram: InstagramSettings = Field(default_factory=InstagramSettings)

    sources: list[Source] = Field(default_factory=list)
    series: list[SeriesSpec] = Field(default_factory=list)
    guides: list[GuideTopic] = Field(default_factory=list)
    root: Path = PROJECT_ROOT

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def samples_dir(self) -> Path:
        return self.root / "samples"

    def thumbnail_path(self, kind: str) -> Path | None:
        rel = self.thumbnails.get(kind)
        if not rel:
            return None
        p = Path(rel)
        return p if p.is_absolute() else self.root / p

    def resolve_output_dir(self) -> Path:
        p = self.output_dir
        return p if p.is_absolute() else self.root / p


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(root: Path | None = None) -> Settings:
    root = root or PROJECT_ROOT
    load_dotenv(root / ".env")
    cfg = root / "config"
    data = _read_yaml(cfg / "settings.yaml")
    data["sources"] = _read_yaml(cfg / "sources.yaml").get("sources", [])
    data["series"] = _read_yaml(cfg / "series.yaml").get("series", [])
    guides = cfg / "guides.yaml"
    data["guides"] = _read_yaml(guides).get("guides", []) if guides.exists() else []
    data["root"] = root
    return Settings.model_validate(data)


def load_intro(settings: Settings, account: str) -> IntroPost:
    """config/intro.yaml 에서 계정 소개 게시물 글을 읽는다."""
    data = _read_yaml(settings.root / "config" / "intro.yaml")
    if account not in data:
        raise KeyError(f"config/intro.yaml 에 '{account}' 계정 소개 글이 없음")
    return IntroPost.model_validate(data[account])


def env(name: str) -> str | None:
    """비어 있는 값은 None 으로 취급한다 (GitHub Secrets 미등록 시 빈 문자열이 들어옴)."""
    value = os.environ.get(name, "").strip()
    return value or None
