from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from econblog.config import Settings
from econblog.models import Chart, ChartSpec, MarketSnapshot, Series


class ChartBuilder(ABC):
    """ChartSpec 하나를 PNG 로 그린다. 필요한 데이터가 없으면 None 을 반환한다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def build(self, spec: ChartSpec, snapshot: MarketSnapshot, out_dir: Path) -> Chart | None: ...

    @staticmethod
    def collect_series(spec: ChartSpec, snapshot: MarketSnapshot) -> list[Series]:
        return [s for key in spec.series if (s := snapshot.get(key)) is not None]

    @staticmethod
    def source_note(series: list[Series]) -> str:
        names = {"yahoo": "Yahoo Finance", "fred": "FRED", "ecos": "한국은행 ECOS", "sample": "샘플 데이터"}
        providers = sorted({names.get(s.spec.provider, s.spec.provider) for s in series})
        return "자료: " + ", ".join(providers)
