"""단계 조립만 담당한다. 각 단계의 세부 로직은 해당 패키지에 둔다."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from econblog.charts import build_charts
from econblog.classify import classify_and_select
from econblog.collect import collect_all
from econblog.config import Settings
from econblog.deliver import deliver_all
from econblog.guard.copyright import find_copied_passages
from econblog.market import build_snapshot
from econblog.models import Draft, RenderedPost
from econblog.render.html import render_post
from econblog.write import write_post
from econblog.write.base import WriteContext

log = logging.getLogger(__name__)


def today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def run(
    settings: Settings,
    run_date: date | None = None,
    offline: bool = False,
    deliver_methods: list[str] | None = None,
) -> RenderedPost:
    run_date = run_date or today(settings)
    out_dir = settings.resolve_output_dir() / run_date.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("=== %s 실행 (offline=%s) → %s", run_date, offline, out_dir)

    # 1. 수집
    since = datetime.now(timezone.utc) - timedelta(hours=settings.collect.lookback_hours)
    articles = collect_all(settings, since, offline=offline)
    log.info("수집 합계 %d건", len(articles))

    # 2. 분류·선별
    selected = classify_and_select(settings, articles, offline=offline)
    log.info("선별 %d건", len(selected))

    # 3. 시장 데이터
    snapshot = build_snapshot(settings, run_date, offline=offline)
    log.info("시장 데이터 %d개 (실패 %d개)", len(snapshot.series), len(snapshot.errors))

    # 4. 차트
    charts = build_charts(settings, snapshot, out_dir / "charts")
    log.info("차트 %d개", len(charts))

    # 5. 초안
    ctx = WriteContext(date=run_date, articles=selected, snapshot=snapshot, charts=charts)
    content, warnings = write_post(settings, ctx, offline=offline)

    # 6. 저작권 검사
    references = [c.article for c in selected]
    warnings += find_copied_passages(content, references, settings.guard.max_shared_chars)
    if snapshot.errors:
        warnings.append("데이터 수집 실패: " + ", ".join(sorted(snapshot.errors)))

    # 7. 렌더링·전달
    draft = Draft(date=run_date, content=content, charts=charts, quotes=snapshot.quotes(),
                  references=references, warnings=warnings)
    post = render_post(settings, draft, out_dir)
    for line in deliver_all(settings, post, deliver_methods):
        log.info("전달: %s", line)
    if warnings:
        log.warning("검토 필요 %d건: %s", len(warnings), " | ".join(warnings))
    return post
