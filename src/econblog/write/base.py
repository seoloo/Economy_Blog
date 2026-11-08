from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel

from econblog.config import CardAccount, Settings
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


class CardContext(BaseModel):
    """인스타 카드 글을 쓰는 데 필요한 재료. 같은 날 시황 글(post)을 함께 넘겨 내용이 어긋나지 않게 한다."""

    date: date
    account: CardAccount
    articles: list[ClassifiedArticle]
    snapshot: MarketSnapshot
    post: PostContent | None = None


class Writer(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def write(self, ctx: WriteContext) -> PostContent: ...
