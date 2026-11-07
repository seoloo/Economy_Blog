"""초안이 출처 문장을 그대로 옮겼는지 검사한다."""

from __future__ import annotations

from econblog.models import Article, PostContent


def find_copied_passages(content: PostContent, sources: list[Article], max_shared_chars: int) -> list[str]:
    """출처의 제목·요약과 max_shared_chars 글자 이상 연속으로 겹치는 구간마다 경고 문구를 반환한다."""
    raise NotImplementedError
