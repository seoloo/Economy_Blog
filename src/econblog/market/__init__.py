"""시장 데이터 수집 단계."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from econblog import registry
from econblog.config import Settings
from econblog.models import MarketSnapshot

log = logging.getLogger(__name__)

PROVIDERS: dict[str, str] = {
    "yahoo": "econblog.market.yahoo:YahooProvider",
    "fred": "econblog.market.fred:FredProvider",
    "treasury": "econblog.market.treasury:TreasuryProvider",
    "ecos": "econblog.market.ecos:EcosProvider",
    "sample": "econblog.market.sample:SampleProvider",
}


def build_snapshot(
    settings: Settings,
    as_of: date,
    offline: bool = False,
    keys: list[str] | None = None,
    lookback_days: int | None = None,
) -> MarketSnapshot:
    """series.yaml 의 시리즈를 가져온다 (keys 가 있으면 그것만). 개별 실패는 snapshot.errors 에 기록한다."""
    start = as_of - timedelta(days=lookback_days or settings.market.lookback_days)
    snapshot = MarketSnapshot(as_of=as_of)
    instances: dict[str, object] = {}
    specs = [s for s in settings.series if keys is None or s.key in keys]
    for spec in specs:
        name = "sample" if offline else spec.provider
        try:
            if name not in instances:
                instances[name] = registry.load(PROVIDERS, name)(settings)
            fetch_spec = spec.model_copy(update={"provider": "sample"}) if offline else spec
            series = instances[name].fetch(fetch_spec, start, as_of)
            if not series.values:
                raise ValueError("데이터 없음")
            snapshot.series[spec.key] = series
        except Exception as e:  # noqa: BLE001
            log.warning("시장 데이터 실패 %s(%s): %s", spec.key, name, e)
            snapshot.errors[spec.key] = str(e)
    return snapshot
