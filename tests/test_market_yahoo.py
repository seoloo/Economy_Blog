from datetime import date, datetime, timezone

import pandas as pd

from econblog.market.yahoo import YahooProvider
from econblog.models import SeriesSpec

SPEC = SeriesSpec(key="kospi", label="코스피", provider="yahoo", id="^KS11", unit="pt", category="index_kr")
DAILY = pd.DataFrame({"Close": [5383.80, 5059.69]},
                     index=pd.to_datetime(["2026-11-05", "2026-11-06"]).tz_localize("Asia/Seoul"))


def _fake_yf(monkeypatch, info):
    import yfinance

    class FakeTicker:
        def __init__(self, sym):
            self.info = info

        def history(self, **kw):
            return DAILY

    monkeypatch.setattr(yfinance, "Ticker", FakeTicker)


def _ts(y, m, d, h, mi):
    return int(datetime(y, m, d, h, mi, tzinfo=timezone.utc).timestamp())


def test_missing_daily_bar_is_filled_from_the_closing_quote(monkeypatch):
    # 11/9 일봉이 아직 없고, 시세 정보에는 11/9 장 마감 뒤 종가가 있다
    _fake_yf(monkeypatch, {"regularMarketPrice": 5018.85, "regularMarketTime": _ts(2026, 11, 9, 11, 5),
                           "marketState": "PRE", "exchangeTimezoneName": "Asia/Seoul"})
    s = YahooProvider(None).fetch(SPEC, date(2026, 11, 1), date(2026, 11, 10))
    assert s.last_date == date(2026, 11, 9) and s.last == 5018.85
    assert round(s.change_pct, 2) == -0.81


def test_quote_is_not_used_during_the_session_or_when_daily_is_current(monkeypatch):
    _fake_yf(monkeypatch, {"regularMarketPrice": 5000.0, "regularMarketTime": _ts(2026, 11, 9, 2, 0),
                           "marketState": "REGULAR", "exchangeTimezoneName": "Asia/Seoul"})
    assert YahooProvider(None).fetch(SPEC, date(2026, 11, 1), date(2026, 11, 10)).last_date == date(2026, 11, 6)
    _fake_yf(monkeypatch, {"regularMarketPrice": 5059.69, "regularMarketTime": _ts(2026, 11, 6, 11, 0),
                           "marketState": "CLOSED", "exchangeTimezoneName": "Asia/Seoul"})
    s = YahooProvider(None).fetch(SPEC, date(2026, 11, 1), date(2026, 11, 10))
    assert s.dates == [date(2026, 11, 5), date(2026, 11, 6)]
