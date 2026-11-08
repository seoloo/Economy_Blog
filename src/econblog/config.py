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

    series_title: str = "미국증시·코스피 시황"   # 제목 맨 앞 연재 머리말 (검색 키워드)
    glance: list[str] = Field(default_factory=list)          # '오늘 시장 한눈에' 상자
    global_table: list[str] = Field(default_factory=list)    # 해외 시장 표
    korea_table: list[str] = Field(default_factory=list)     # 국내 시장 표


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


class InstagramSettings(BaseModel):
    """인스타 카드뉴스. enabled 면 시황 글과 같은 실행에서 카드를 만들어 메일로 보낸다.

    publish 가 true 이고 계정 토큰이 있으면 인스타에 바로 게시한다. 처음에는 메일로만 받아 확인한다.
    """

    enabled: bool = False
    publish: bool = False
    render_images: bool = True     # 카드 JPEG 을 Chrome 으로 찍는다 (끄면 HTML 만 만든다)
    photos: bool = True            # Pixabay 배경 사진 (PIXABAY_API_KEY 필요, 없으면 단색 배경)
    review: bool = True            # 카드 글을 쓴 뒤 Claude 교열 단계를 한 번 더 거친다
    graph_version: str = "v23.0"
    accounts: list[CardAccount] = Field(default_factory=list)
    # 카드에 나오면 안 되는 모호한 표현 (언어별). 나오면 경고를 붙인다.
    vague_phrases: dict[str, list[str]] = Field(default_factory=dict)


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
