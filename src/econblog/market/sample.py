"""--dry-run 용 가상 시계열. 실행할 때마다 같은 값이 나오도록 시드를 고정한다."""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

from econblog.market.base import MarketDataProvider
from econblog.models import Series, SeriesSpec

BASE_LEVELS = {
    "kospi": 2600, "kosdaq": 750, "sp500": 6000, "nasdaq": 19500, "dow": 44000, "nikkei": 39000, "vix": 18,
    "usdkrw": 1380, "dxy": 104, "wti": 70, "gold": 2700,
    "us10y": 4.3, "us2y": 3.9, "kr3y": 2.6, "kr_base_rate": 2.5,
}


class SampleProvider(MarketDataProvider):
    def fetch(self, spec: SeriesSpec, start: date, end: date) -> Series:
        seed = int(hashlib.sha256(spec.key.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        level = BASE_LEVELS.get(spec.key, 100.0)
        is_rate = spec.category == "rates"
        dates: list[date] = []
        values: list[float] = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                level += rng.gauss(0, 0.03) if is_rate else level * rng.gauss(0, 0.009)
                dates.append(d)
                values.append(round(level, 4))
            d += timedelta(days=1)
        return Series(spec=spec, dates=dates, values=values)
