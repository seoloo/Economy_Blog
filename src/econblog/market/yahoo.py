"""yfinance(비공식 Yahoo Finance) 기반 지수·환율·원자재 시세. API 키 불필요."""

from __future__ import annotations

import math
from datetime import date, timedelta

from econblog.market.base import MarketDataProvider
from econblog.models import Series, SeriesSpec


class YahooProvider(MarketDataProvider):
    def fetch(self, spec: SeriesSpec, start: date, end: date) -> Series:
        import yfinance as yf  # 무거운 의존성이라 실제 사용할 때만 import

        df = yf.Ticker(spec.id).history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat())
        if df is None or df.empty or "Close" not in df:
            raise ValueError(f"{spec.id} 데이터 없음")
        dates: list[date] = []
        values: list[float] = []
        for ts, v in df["Close"].items():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            dates.append(ts.date())
            values.append(float(v))
        return Series(spec=spec, dates=dates, values=values)
