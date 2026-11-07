from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from econblog.config import Settings
from econblog.models import Series, SeriesSpec


class MarketDataProvider(ABC):
    """시계열 하나를 가져온다. 결측치(None/NaN)는 제거하고 날짜 오름차순으로 반환한다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def fetch(self, spec: SeriesSpec, start: date, end: date) -> Series: ...
