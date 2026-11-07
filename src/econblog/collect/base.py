from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from econblog.config import Settings
from econblog.models import Article, Source


class Collector(ABC):
    """소스 하나에서 기사 목록을 가져온다. 본문 전체는 가져오지 않는다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def collect(self, source: Source, since: datetime) -> list[Article]:
        """since 이후 발행된 기사를 최신순으로 최대 max_per_source 개 반환한다."""
