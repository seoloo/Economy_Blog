from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel

from econblog.config import Settings
from econblog.models import Chart, ClassifiedArticle, GuideTopic, MarketSnapshot, PostContent


class WriteContext(BaseModel):
    """Writer 가 글을 쓰는 데 필요한 재료 전부."""

    date: date
    articles: list[ClassifiedArticle]
    snapshot: MarketSnapshot
    charts: list[Chart]


class GuideContext(BaseModel):
    """경제 공부 글을 쓰는 데 필요한 재료."""

    date: date
    topic: GuideTopic
    snapshot: MarketSnapshot
    charts: list[Chart]


class Writer(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def write(self, ctx: WriteContext) -> PostContent: ...
