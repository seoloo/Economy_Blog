"""FRED API (세인트루이스 연은). 미국 금리 등. FRED_API_KEY 필요."""

from __future__ import annotations

from datetime import date

import requests

from econblog.config import env
from econblog.market.base import MarketDataProvider
from econblog.models import Series, SeriesSpec

API_URL = "https://api.stlouisfed.org/fred/series/observations"


def parse_observations(spec: SeriesSpec, payload: dict) -> Series:
    dates: list[date] = []
    values: list[float] = []
    for row in payload.get("observations", []):
        if row.get("value") in (None, "", "."):  # FRED 는 휴장일을 "." 로 표기
            continue
        dates.append(date.fromisoformat(row["date"]))
        values.append(float(row["value"]))
    return Series(spec=spec, dates=dates, values=values)


class FredProvider(MarketDataProvider):
    def __init__(self, settings):
        super().__init__(settings)
        self.api_key = env("FRED_API_KEY")
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY 가 설정되지 않음")

    def fetch(self, spec: SeriesSpec, start: date, end: date) -> Series:
        resp = requests.get(
            API_URL,
            params={
                "series_id": spec.id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": start.isoformat(),
                "observation_end": end.isoformat(),
            },
            timeout=30,
        )
        resp.raise_for_status()
        return parse_observations(spec, resp.json())
