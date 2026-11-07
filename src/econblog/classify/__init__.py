"""기사 분류·중복 제거·선별 단계."""

from __future__ import annotations

import logging

from econblog import registry
from econblog.classify.dedupe import mark_duplicates, select_top
from econblog.config import Settings
from econblog.models import Article, ClassifiedArticle

log = logging.getLogger(__name__)

CLASSIFIERS: dict[str, str] = {
    "laya": "econblog.classify.laya:LayaClassifier",
    "keyword": "econblog.classify.keyword:KeywordClassifier",
}


def classify_and_select(
    settings: Settings, articles: list[Article], offline: bool = False
) -> list[ClassifiedArticle]:
    """분류 → 중복 표시 → 지역별 상위 N개 선별."""
    cfg = settings.classify
    name = cfg.fallback if offline else cfg.provider
    try:
        classified = registry.load(CLASSIFIERS, name)(settings).classify(articles)
    except Exception as e:  # noqa: BLE001
        if name == cfg.fallback:
            raise
        log.warning("분류기 '%s' 실패, '%s'로 대체: %s", name, cfg.fallback, e)
        classified = registry.load(CLASSIFIERS, cfg.fallback)(settings).classify(articles)

    mark_duplicates(classified, cfg.dedupe_threshold)
    return select_top(classified, cfg.top_n_per_region)
