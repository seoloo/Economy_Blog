"""제목 유사도 기반 중복 제거와 지역별 상위 기사 선별."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher

from econblog.models import ClassifiedArticle

MAX_PER_TOPIC = 3  # 한 지역 안에서 같은 주제 기사가 독식하지 않도록 제한

_SUFFIX_RE = re.compile(r"\s+[-|–]\s+[^-|–]{1,30}$")  # "제목 - 언론사" 꼬리 제거
_BRACKET_RE = re.compile(r"[\[\(【<].{0,12}?[\]\)】>]")  # [속보], (종합) 등
_PUNCT_RE = re.compile(r"[^\w가-힣]+")


def normalize_title(title: str) -> str:
    t = _SUFFIX_RE.sub("", title)
    t = _BRACKET_RE.sub(" ", t)
    return _PUNCT_RE.sub("", t).lower()


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def mark_duplicates(items: list[ClassifiedArticle], threshold: float) -> None:
    """같은 사건을 다룬 기사 중 중요도가 가장 높은 하나만 남기고 나머지는 is_duplicate=True."""
    order = sorted(range(len(items)), key=lambda i: items[i].importance, reverse=True)
    kept: list[ClassifiedArticle] = []
    for i in order:
        item = items[i]
        if any(
            k.article.region == item.article.region
            and title_similarity(k.article.title, item.article.title) >= threshold
            for k in kept
        ):
            item.is_duplicate = True
        else:
            kept.append(item)


def select_top(items: list[ClassifiedArticle], n_per_region: int) -> list[ClassifiedArticle]:
    """중복이 아닌 기사 중 지역(kr/global)별 중요도 상위 n개. 주제당 최대 MAX_PER_TOPIC 개."""
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    ranked = sorted(
        (x for x in items if not x.is_duplicate),
        key=lambda x: (x.importance, x.article.published or oldest),
        reverse=True,
    )
    selected: list[ClassifiedArticle] = []
    for region in ("global", "kr"):
        per_topic: Counter[str] = Counter()
        picked = 0
        for x in ranked:
            if x.article.region != region or picked >= n_per_region:
                continue
            if per_topic[x.topic] >= MAX_PER_TOPIC:
                continue
            per_topic[x.topic] += 1
            selected.append(x)
            picked += 1
    return selected
