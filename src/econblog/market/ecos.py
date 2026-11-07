"""한국은행 ECOS Open API. ECOS_API_KEY 필요.

series.yaml 의 id 는 통계표 코드, params.cycle 은 주기(D/M/Q/A), params.item 은 항목 코드.
"""

from __future__ import annotations

from datetime import date, datetime

import requests

from econblog.config import env
from econblog.market.base import MarketDataProvider
from econblog.models import Series, SeriesSpec

API_URL = "https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/10000/{stat}/{cycle}/{start}/{end}/{item}"
DATE_FORMATS = {"D": ("%Y%m%d", "%Y%m%d"), "M": ("%Y%m", "%Y%m"), "A": ("%Y", "%Y")}


def parse_rows(spec: SeriesSpec, payload: dict) -> Series:
    if "StatisticSearch" not in payload:
        result = payload.get("RESULT", {})
        raise ValueError(f"ECOS 오류 {result.get('CODE')}: {result.get('MESSAGE')}")
    fmt = DATE_FORMATS.get(spec.params.get("cycle", "D"), DATE_FORMATS["D"])[1]
    pairs = []
    for row in payload["StatisticSearch"].get("row", []):
        raw = row.get("DATA_VALUE")
        if raw in (None, "", "-"):
            continue
        pairs.append((datetime.strptime(row["TIME"], fmt).date(), float(raw)))
    pairs.sort()
    return Series(spec=spec, dates=[d for d, _ in pairs], values=[v for _, v in pairs])


class EcosProvider(MarketDataProvider):
    def __init__(self, settings):
        super().__init__(settings)
        self.api_key = env("ECOS_API_KEY")
        if not self.api_key:
            raise RuntimeError("ECOS_API_KEY 가 설정되지 않음")

    def fetch(self, spec: SeriesSpec, start: date, end: date) -> Series:
        cycle = spec.params.get("cycle", "D")
        fmt = DATE_FORMATS.get(cycle, DATE_FORMATS["D"])[0]
        url = API_URL.format(
            key=self.api_key,
            stat=spec.id,
            cycle=cycle,
            start=start.strftime(fmt),
            end=end.strftime(fmt),
            item=spec.params.get("item", ""),
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return parse_rows(spec, resp.json())
