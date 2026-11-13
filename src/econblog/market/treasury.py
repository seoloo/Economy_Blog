"""미 재무부 일별 국채 금리(Daily Treasury Par Yield Curve). API 키 불필요.

FRED 의 DGS10·DGS2 는 같은 자료를 하루 이틀 늦게 올린다 (2026-11-12~14 사흘 연속 전날 값이 들어감).
재무부 파일은 당일 장 마감 뒤 바로 올라오므로 이쪽을 먼저 쓰고, 실패하면 params.fred 의 FRED 시리즈로 받는다.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime

import requests

from econblog.market.base import MarketDataProvider
from econblog.models import Series, SeriesSpec

log = logging.getLogger(__name__)

CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
)


def parse_csv(spec: SeriesSpec, text: str) -> Series:
    """재무부 CSV 에서 spec.id 열(예: "10 Yr")만 뽑는다. 빈 칸은 건너뛰고 날짜 오름차순으로 돌려준다."""
    rows: dict[date, float] = {}
    for row in csv.DictReader(io.StringIO(text)):
        raw = (row.get(spec.id) or "").strip()
        if not raw or raw.upper() == "N/A":
            continue
        day = datetime.strptime(row["Date"], "%m/%d/%Y").date()
        rows[day] = float(raw)
    days = sorted(rows)
    return Series(spec=spec, dates=days, values=[rows[d] for d in days])


class TreasuryProvider(MarketDataProvider):
    def fetch(self, spec: SeriesSpec, start: date, end: date) -> Series:
        try:
            return self._fetch_treasury(spec, start, end)
        except Exception as e:  # noqa: BLE001
            fred_id = spec.params.get("fred")
            if not fred_id:
                raise
            log.warning("재무부 금리 실패 %s, FRED %s 로 대신 받음: %s", spec.key, fred_id, e)
            from econblog.market.fred import FredProvider

            series = FredProvider(self.settings).fetch(spec.model_copy(update={"id": fred_id}), start, end)
            return series.model_copy(update={"spec": spec.model_copy(update={"provider": "fred"})})

    def _fetch_treasury(self, spec: SeriesSpec, start: date, end: date) -> Series:
        dates: list[date] = []
        values: list[float] = []
        for year in range(start.year, end.year + 1):
            resp = requests.get(
                CSV_URL.format(year=year),
                params={"type": "daily_treasury_yield_curve", "field_tdr_date_value": str(year), "_format": "csv"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            resp.raise_for_status()
            part = parse_csv(spec, resp.text)
            for d, v in zip(part.dates, part.values):
                if start <= d <= end:
                    dates.append(d)
                    values.append(v)
        if not values:
            raise ValueError(f"재무부 {spec.id} 데이터 없음")
        return Series(spec=spec, dates=dates, values=values)
