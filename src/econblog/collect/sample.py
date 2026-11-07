"""--dry-run 용 수집기. samples/articles.json 의 가상 기사를 돌려준다."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from econblog.collect.base import Collector
from econblog.models import Article, Source


class SampleCollector(Collector):
    def collect_samples(self) -> list[Article]:
        path = self.settings.samples_dir / "articles.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc)
        return [Article.model_validate({**row, "published": now}) for row in rows]

    def collect(self, source: Source, since: datetime) -> list[Article]:
        return [a for a in self.collect_samples() if a.source_id == source.id]
