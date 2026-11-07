"""제목 유사도 기반 중복 제거와 지역별 상위 기사 선별."""

from __future__ import annotations

from econblog.models import ClassifiedArticle


def mark_duplicates(items: list[ClassifiedArticle], threshold: float) -> None:
    """같은 사건을 다룬 기사 중 중요도가 가장 높은 하나만 남기고 나머지는 is_duplicate=True."""
    raise NotImplementedError


def select_top(items: list[ClassifiedArticle], n_per_region: int) -> list[ClassifiedArticle]:
    """중복이 아닌 기사 중 지역(kr/global)별 중요도 상위 n개."""
    raise NotImplementedError
