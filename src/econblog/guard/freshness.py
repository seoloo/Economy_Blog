"""시장 데이터 날짜 교차 검사.

같은 시장의 값끼리 마지막 날짜를 맞춰 본다. 예: 2026-11-10 아침에 코스피 일봉만 11/6 에 멈춰 있고
삼성전자·SK하이닉스는 11/9 값이 있었다. 이런 날은 지수가 지난 값인데도 "11/9 종가"로 찍히므로
경고를 붙여 사람이 확인하게 한다 (인스타 자동 게시도 멈춘다).
휴일처럼 시장 전체가 쉬는 날은 같은 시장 값이 모두 같이 멈추므로 경고가 나오지 않는다.
"""

from __future__ import annotations

from econblog.models import MarketSnapshot

# 시장별로 같이 움직여야 하는 시리즈 (category 기준, 지수는 key 로 추가)
MARKETS = {
    "한국": {"categories": {"index_kr", "kr_stock"}, "keys": set()},
    "미국": {"categories": {"us_stock", "us_sector"}, "keys": {"sp500", "nasdaq", "dow", "sox", "rut", "vix"}},
}


def find_stale_series(snapshot: MarketSnapshot) -> list[str]:
    warnings = []
    for market, rule in MARKETS.items():
        group = [s for k, s in snapshot.series.items()
                 if s.last_date and (s.spec.category in rule["categories"] or k in rule["keys"])]
        if len(group) < 2:
            continue
        newest = max(s.last_date for s in group)
        stale = [s for s in group if s.last_date < newest]
        if stale:
            names = ", ".join(f"{s.spec.label} {s.last_date.month}/{s.last_date.day}" for s in stale)
            warnings.append(f"데이터 날짜 확인 필요({market}): {names} 기준인데 같은 시장 다른 값은 "
                            f"{newest.month}/{newest.day} 종가입니다")
    return warnings
