"""뉴스·블로그 수집 단계."""

from __future__ import annotations

import logging
from datetime import datetime

from econblog import registry
from econblog.config import Settings
from econblog.models import Article

log = logging.getLogger(__name__)

COLLECTORS: dict[str, str] = {
    "rss": "econblog.collect.rss:RssCollector",
    "sample": "econblog.collect.sample:SampleCollector",
}


def collect_all(settings: Settings, since: datetime, offline: bool = False) -> list[Article]:
    """모든 소스를 수집한다. 소스 하나가 실패해도 나머지는 계속 진행한다."""
    if offline:
        collector = registry.load(COLLECTORS, "sample")(settings)
        return collector.collect_samples()

    instances: dict[str, object] = {}
    articles: list[Article] = []
    for source in settings.sources:
        try:
            if source.collector not in instances:
                instances[source.collector] = registry.load(COLLECTORS, source.collector)(settings)
            found = instances[source.collector].collect(source, since)
            log.info("수집 %-24s %3d건", source.id, len(found))
            articles.extend(found)
        except Exception as e:  # noqa: BLE001 - 소스별 실패는 격리한다
            log.warning("수집 실패 %s: %s", source.id, e)
    return articles
