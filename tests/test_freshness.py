from datetime import date

from econblog.guard.freshness import find_stale_series
from econblog.models import MarketSnapshot, Series, SeriesSpec


def _s(key, label, category, last):
    spec = SeriesSpec(key=key, label=label, provider="yahoo", id=key, unit="pt", category=category)
    return Series(spec=spec, dates=[date(2026, 11, 5), last], values=[1.0, 2.0])


def test_index_stuck_behind_its_own_market_is_flagged():
    # 11/10 아침: 코스피 일봉만 11/6, 삼성전자는 11/9
    snap = MarketSnapshot(as_of=date(2026, 11, 10), series={
        "kospi": _s("kospi", "코스피", "index_kr", date(2026, 11, 6)),
        "st_samsung": _s("st_samsung", "삼성전자", "kr_stock", date(2026, 11, 9)),
        "sp500": _s("sp500", "S&P 500", "index_global", date(2026, 11, 9)),
        "st_aapl": _s("st_aapl", "애플", "us_stock", date(2026, 11, 9)),
        "nikkei": _s("nikkei", "닛케이225", "index_global", date(2026, 11, 6)),   # 다른 시장 휴일은 비교하지 않음
    })
    [w] = find_stale_series(snap)
    assert "한국" in w and "코스피 11/6" in w and "11/9" in w


def test_whole_market_holiday_is_not_flagged():
    snap = MarketSnapshot(as_of=date(2026, 11, 27), series={
        "sp500": _s("sp500", "S&P 500", "index_global", date(2026, 11, 25)),
        "st_aapl": _s("st_aapl", "애플", "us_stock", date(2026, 11, 25)),
        "kospi": _s("kospi", "코스피", "index_kr", date(2026, 11, 26)),
        "st_samsung": _s("st_samsung", "삼성전자", "kr_stock", date(2026, 11, 26)),
    })
    assert find_stale_series(snap) == []
