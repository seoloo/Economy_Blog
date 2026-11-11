from datetime import date, datetime, timezone

import pandas as pd

from econblog.market.yahoo import YahooProvider
from econblog.models import SeriesSpec

SPEC = SeriesSpec(key="kospi", label="코스피", provider="yahoo", id="^KS11", unit="pt", category="index_kr")
DAILY = pd.DataFrame({"Close": [5383.80, 5059.69]},
                     index=pd.to_datetime(["2026-11-05", "2026-11-06"]).tz_localize("Asia/Seoul"))


def _daily(rows, tz="Asia/Seoul"):
    return pd.DataFrame({"Close": [v for _, v in rows]},
                        index=pd.to_datetime([d for d, _ in rows]).tz_localize(tz))


def _fake_yf(monkeypatch, info, daily=DAILY):
    import yfinance

    class FakeTicker:
        def __init__(self, sym):
            self.info = info

        def history(self, **kw):
            return daily

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


def test_intraday_bar_is_dropped_and_missing_previous_close_is_filled(monkeypatch):
    # 11/11 장중: 오늘 일봉(지금 가격)은 있는데 11/10 일봉이 아직 없다 → 11/10 종가 기준 등락률이어야 한다
    info = {"regularMarketPrice": 5259.39, "regularMarketPreviousClose": 5239.13,
            "regularMarketTime": _ts(2026, 11, 11, 1, 14), "marketState": "REGULAR",
            "exchangeTimezoneName": "Asia/Seoul"}
    _fake_yf(monkeypatch, info, _daily([("2026-11-06", 5059.69), ("2026-11-09", 5018.85), ("2026-11-11", 5259.39)]))
    s = YahooProvider(None).fetch(SPEC, date(2026, 11, 1), date(2026, 11, 11))
    assert s.last_date == date(2026, 11, 10) and s.last == 5239.13
    assert round(s.change_pct, 2) == 4.39

    # 11/10 일봉이 이미 있으면 오늘 일봉만 뺀다
    _fake_yf(monkeypatch, info, _daily([("2026-11-09", 5018.85), ("2026-11-10", 5239.13), ("2026-11-11", 5259.39)]))
    s = YahooProvider(None).fetch(SPEC, date(2026, 11, 1), date(2026, 11, 11))
    assert s.dates == [date(2026, 11, 9), date(2026, 11, 10)]


def test_holiday_before_the_session_does_not_add_a_flat_day(monkeypatch):
    # 11/9(월)이 휴장이었다면 11/10 장중의 전일 종가는 11/6 종가와 같다 → 11/9 를 지어내지 않는다
    info = {"regularMarketPrice": 5100.0, "regularMarketPreviousClose": 5059.69,
            "regularMarketTime": _ts(2026, 11, 10, 2, 0), "marketState": "REGULAR",
            "exchangeTimezoneName": "Asia/Seoul"}
    _fake_yf(monkeypatch, info, _daily([("2026-11-05", 5383.80), ("2026-11-06", 5059.69), ("2026-11-10", 5100.0)]))
    s = YahooProvider(None).fetch(SPEC, date(2026, 11, 1), date(2026, 11, 10))
    assert s.dates == [date(2026, 11, 5), date(2026, 11, 6)]


def test_round_the_clock_series_keep_todays_bar(monkeypatch):
    rows = [("2026-11-09", 1362.70), ("2026-11-10", 1343.84), ("2026-11-11", 1334.48)]
    info = {"regularMarketPrice": 1334.48, "regularMarketPreviousClose": 1342.34,
            "regularMarketTime": _ts(2026, 11, 11, 3, 0), "marketState": "REGULAR",
            "exchangeTimezoneName": "Europe/London"}
    fx = SeriesSpec(key="usdkrw", label="원/달러 환율", provider="yahoo", id="KRW=X", unit="원", category="fx")
    _fake_yf(monkeypatch, info, _daily(rows, "Europe/London"))
    assert YahooProvider(None).fetch(fx, date(2026, 11, 1), date(2026, 11, 11)).last == 1334.48

    # 비트코인: 오늘 일봉은 두고, 비어 있는 어제 일봉만 전일 종가로 채운다
    btc = SeriesSpec(key="btc", label="비트코인", provider="yahoo", id="BTC-USD", unit="달러", category="crypto")
    info = {"regularMarketPrice": 73734.91, "regularMarketPreviousClose": 73708.88,
            "regularMarketTime": _ts(2026, 11, 11, 3, 0), "marketState": "REGULAR", "exchangeTimezoneName": "UTC"}
    _fake_yf(monkeypatch, info, _daily([("2026-11-09", 75223.15), ("2026-11-11", 73734.91)], "UTC"))
    s = YahooProvider(None).fetch(btc, date(2026, 11, 1), date(2026, 11, 11))
    assert s.dates[-2:] == [date(2026, 11, 10), date(2026, 11, 11)]
    assert round(s.change_pct, 2) == 0.04
