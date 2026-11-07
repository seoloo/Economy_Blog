"""초안이 출처 문장을 그대로 옮겼는지 검사한다.

출처의 제목·요약(수집한 범위)과 초안의 각 문단을 비교해, 공백을 무시하고
max_shared_chars 글자 이상 연속으로 같은 구간이 있으면 경고한다.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from econblog.models import Article, PostContent

_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text.replace("**", "")).strip().lower()


def post_texts(content: PostContent) -> list[str]:
    """글에 들어가는 모든 문장 덩어리 (제목·문단·목록·이슈)."""
    texts = [
        content.title, content.lead, content.summary_line, *content.global_market, *content.korea_market,
        *content.korea_checkpoints, *content.watch_points, content.closing,
    ]
    for issue in content.issues:
        texts += [issue.title, *issue.paragraphs]
    return [t for t in texts if t]


def longest_shared(a: str, b: str) -> str:
    sm = SequenceMatcher(None, a, b, autojunk=False)
    m = sm.find_longest_match(0, len(a), 0, len(b))
    return a[m.a : m.a + m.size]


def find_copied_passages(content: PostContent, sources: list[Article], max_shared_chars: int) -> list[str]:
    """출처의 제목·요약과 max_shared_chars 글자 이상 연속으로 겹치는 구간마다 경고 문구를 반환한다."""
    warnings: list[str] = []
    source_texts = [(s, _norm(f"{s.title} {s.summary}")) for s in sources]
    for para in post_texts(content):
        p = _norm(para)
        for src, text in source_texts:
            shared = longest_shared(p, text).strip()
            if len(shared) >= max_shared_chars:
                warnings.append(f"출처 문장과 {len(shared)}자 일치 ({src.source_name}): \"{shared[:60]}…\"")
                break
    return warnings
