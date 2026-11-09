"""yfinance(비공식 Yahoo Finance) 기반 지수·환율·원자재 시세. API 키 불필요."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

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
        _add_latest_close(yf.Ticker(spec.id), dates, values, end)
        return Series(spec=spec, dates=dates, values=values)


def _add_latest_close(ticker, dates: list[date], values: list[float], end: date) -> None:
    """일봉이 하루 늦게 올라올 때가 있다 (예: 11/9 코스피·닛케이 일봉이 다음 날 아침까지 비어 있었음).
    장이 끝난 뒤의 시세 정보(regularMarketPrice)에 더 최근 종가가 있으면 그 날짜로 붙인다.
    장중이면 아직 종가가 아니므로 붙이지 않는다. 조회가 실패하면 일봉만 쓴다."""
    try:
        info = ticker.info or {}
        price, ts = info.get("regularMarketPrice"), info.get("regularMarketTime")
        if price is None or ts is None or info.get("marketState") == "REGULAR":
            return
        tz = ZoneInfo(info.get("exchangeTimezoneName") or "UTC")
        day = datetime.fromtimestamp(int(ts), tz).date()
    except Exception:  # noqa: BLE001
        return
    if dates and dates[-1] < day <= end and not math.isnan(float(price)):
        dates.append(day)
        values.append(float(price))
