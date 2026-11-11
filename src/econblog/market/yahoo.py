"""yfinance(비공식 Yahoo Finance) 기반 지수·환율·원자재 시세. API 키 불필요."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from econblog.market.base import MarketDataProvider
from econblog.models import Series, SeriesSpec


# 하루 종일 거래돼 '장중'이 따로 없는 시리즈. 오늘 일봉을 그대로 쓴다.
ROUND_THE_CLOCK = ("fx", "commodity", "crypto")
# 시세 정보의 전일 종가가 일봉 종가와 다른 기준(정산가 등)이라 빈 일봉을 채우는 데 쓰지 않는 시리즈
NO_PREV_FILL = ("fx", "commodity")


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
        _settle(yf.Ticker(spec.id), spec.category, dates, values, end)
        return Series(spec=spec, dates=dates, values=values)


def _settle(ticker, category: str, dates: list[date], values: list[float], end: date) -> None:
    """일봉을 '끝난 거래일의 종가'만 남도록 시세 정보로 바로잡는다. 조회가 실패하면 일봉만 쓴다.

    - 장이 끝난 뒤: 일봉이 하루 늦게 올라올 때가 있다 (예: 11/9 코스피·닛케이 일봉이 다음 날 아침까지
      비어 있었음). 시세 정보(regularMarketPrice)에 더 최근 종가가 있으면 그 날짜로 붙인다.
    - 장중: 오늘 일봉은 종가가 아니라 지금 가격이므로 뺀다. 이때 전날 일봉이 아직 비어 있으면
      (예: 11/11 오전 코스피 11/10 일봉) 이틀 치가 하루 등락으로 계산되므로 전일 종가로 채운다."""
    try:
        info = ticker.info or {}
        ts = info.get("regularMarketTime")
        if ts is None:
            return
        tz = ZoneInfo(info.get("exchangeTimezoneName") or "UTC")
        day = datetime.fromtimestamp(int(ts), tz).date()
        price = _number(info.get("regularMarketPrice"))
        prev = _number(info.get("regularMarketPreviousClose") or info.get("previousClose"))
        in_session = info.get("marketState") == "REGULAR"
    except Exception:  # noqa: BLE001
        return
    if not in_session:
        if price is not None and dates and dates[-1] < day <= end:
            dates.append(day)
            values.append(price)
        return

    today: tuple[date, float] | None = None
    if dates and dates[-1] >= day:
        today = (dates.pop(), values.pop())
    before = day - timedelta(days=1)
    if category != "crypto":
        while before.weekday() >= 5:
            before -= timedelta(days=1)
    # 직전 거래일이 휴장이었으면 전일 종가가 마지막 일봉과 같다. 그때는 채우지 않는다.
    if (category not in NO_PREV_FILL and prev is not None and dates and dates[-1] < before <= end
            and abs(values[-1] / prev - 1) > 1e-4):
        dates.append(before)
        values.append(prev)
    if today and category in ROUND_THE_CLOCK:
        dates.append(today[0])
        values.append(today[1])


def _number(v) -> float | None:
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) or v <= 0 else v
