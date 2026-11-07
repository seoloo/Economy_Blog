"""차트 생성 단계. 새 차트 종류는 BUILDERS 에 등록하고 settings.yaml 의 charts 에 추가한다."""

from __future__ import annotations

import logging
from pathlib import Path

from econblog import registry
from econblog.config import Settings
from econblog.models import Chart, MarketSnapshot

log = logging.getLogger(__name__)

BUILDERS: dict[str, str] = {
    "change_bar": "econblog.charts.builders:ChangeBarChart",
    "line": "econblog.charts.builders:LineChart",
    "spread": "econblog.charts.builders:SpreadChart",
    "cover": "econblog.charts.cover:CoverChart",
}


def build_charts(settings: Settings, snapshot: MarketSnapshot, out_dir: Path) -> list[Chart]:
    out_dir.mkdir(parents=True, exist_ok=True)
    charts: list[Chart] = []
    for spec in settings.charts:
        try:
            chart = registry.load(BUILDERS, spec.type)(settings).build(spec, snapshot, out_dir)
        except Exception as e:  # noqa: BLE001
            log.warning("차트 실패 %s: %s", spec.key, e)
            continue
        if chart is None:
            log.warning("차트 건너뜀 %s: 데이터 부족", spec.key)
            continue
        chart.position = spec.position
        charts.append(chart)
    return charts
