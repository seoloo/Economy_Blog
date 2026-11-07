"""설정 로딩. YAML(config/)은 동작 방식, 환경변수(.env / Secrets)는 비밀값을 담는다."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from econblog.models import ChartSpec, SeriesSpec, Source

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


class GuardSettings(BaseModel):
    max_shared_chars: int = 40
    # AI 가 쓴 티가 나는 표현과 글 한 편에서 허용하는 횟수. 넘으면 경고한다.
    ai_phrases: dict[str, int] = Field(default_factory=dict)


class DeliverSettings(BaseModel):
    methods: list[str] = Field(default_factory=lambda: ["local"])


class Settings(BaseModel):
    timezone: str = "Asia/Seoul"
    output_dir: Path = Path("output")
    blog_name: str = "그냥모아"
    collect: CollectSettings = Field(default_factory=CollectSettings)
    classify: ClassifySettings = Field(default_factory=ClassifySettings)
    market: MarketSettings = Field(default_factory=MarketSettings)
    charts: list[ChartSpec] = Field(default_factory=list)
    write: WriteSettings = Field(default_factory=WriteSettings)
    post: PostSettings = Field(default_factory=PostSettings)
    publish: PublishSettings = Field(default_factory=PublishSettings)
    guard: GuardSettings = Field(default_factory=GuardSettings)
    deliver: DeliverSettings = Field(default_factory=DeliverSettings)

    sources: list[Source] = Field(default_factory=list)
    series: list[SeriesSpec] = Field(default_factory=list)
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
    data["root"] = root
    return Settings.model_validate(data)


def env(name: str) -> str | None:
    """비어 있는 값은 None 으로 취급한다 (GitHub Secrets 미등록 시 빈 문자열이 들어옴)."""
    value = os.environ.get(name, "").strip()
    return value or None
