"""네이버 블로그판: 티스토리판과 같은 사실을 다른 문장으로 다시 쓴다.

같은 글을 두 블로그에 그대로 올리면 네이버 검색에서 중복 문서로 밀려날 수 있어서 문장만 바꾼다.
숫자·표·구성은 그대로 두고, 다시 쓴 글이 원본과 너무 겹치거나 원본에 없는 숫자가 생기면 경고를 붙인다.
API 키가 없거나(오프라인) 실패하면 None 을 돌려주고, 네이버판은 티스토리판과 같은 글로 나간다.
"""

from __future__ import annotations

import logging
import re
from typing import TypeVar

from econblog.config import Settings
from econblog.guard.copyright import _norm, longest_shared, post_texts
from econblog.models import GuidePost, PostContent

log = logging.getLogger(__name__)
T = TypeVar("T", PostContent, GuidePost)

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
MAX_SHARED = 40   # 원본과 이만큼(글자) 넘게 똑같이 이어지면 경고


def rewrite_for_naver(settings: Settings, content: T, offline: bool = False) -> tuple[T | None, list[str]]:
    if offline or settings.write.provider != "claude":
        return None, []
    from econblog.write.claude import make_client, structured_call
    from econblog.write.prompting import _env, guide_system_prompt, system_prompt

    system = guide_system_prompt(settings) if isinstance(content, GuidePost) else system_prompt(settings)
    user = _env(settings).get_template("naver_rewrite.md.j2").render(
        original=content.model_dump_json(indent=1))
    try:
        naver = structured_call(make_client(), settings, system, user, type(content))
    except Exception as e:  # noqa: BLE001
        log.warning("네이버판 다시 쓰기 실패: %s", e)
        return None, [f"네이버판 다시 쓰기 실패로 티스토리판과 같은 글을 넣었습니다: {e}"]
    return naver, check_naver(content, naver)


def check_naver(original: T, naver: T) -> list[str]:
    """네이버판 교차 검사: 원본에 없는 숫자가 생겼는지, 원본 문장과 너무 겹치는지."""
    warnings = []
    orig_texts = post_texts(original)
    orig_nums = {n.replace(",", "") for t in orig_texts for n in NUM.findall(t)}
    extra = sorted({n for t in post_texts(naver) for n in NUM.findall(t) if n.replace(",", "") not in orig_nums})
    if extra:
        warnings.append("네이버판에 원본에 없는 숫자: " + ", ".join(extra[:8]))
    whole = _norm(" ".join(orig_texts))
    tables = {_norm(cell) for cell in _table_cells(original)}
    overlaps = 0
    for t in post_texts(naver):
        n = _norm(t)
        if n in tables:
            continue
        if len(longest_shared(n, whole).strip()) > MAX_SHARED:
            overlaps += 1
    if overlaps:
        warnings.append(f"네이버판 문장 {overlaps}곳이 티스토리판과 {MAX_SHARED}자 넘게 같음 (중복 문서로 볼 수 있음)")
    return warnings


def _table_cells(content) -> list[str]:
    if isinstance(content, GuidePost):
        return [cell for sec in content.sections if sec.table for row in sec.table.rows for cell in row]
    return []
