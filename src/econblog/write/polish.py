"""말투 검사에 걸린 문장만 다시 쓴다.

settings.yaml guard.ai_phrases 의 허용 횟수를 넘은 표현이 있으면, 그 표현이 든 문장만 뽑아 LLM 에게 고쳐 달라고 한다.
글 전체를 다시 쓰게 하지 않고 문장 단위로 바꿔 끼우므로 나머지 글은 글자 하나 바뀌지 않는다.
고친 문장의 숫자가 원래와 다르거나 금지 표현이 또 들어 있으면 그 문장은 원래대로 둔다 (경고는 그대로 남는다).
API 키가 없거나(오프라인) 실패하면 원본을 그대로 돌려준다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TypeVar

from econblog.config import Settings
from econblog.guard.copyright import post_texts
from econblog.guard.style import over_limit
from econblog.models import GuidePost, PostContent, SentenceFix, StyleFixes
from econblog.write.naver import NUM

log = logging.getLogger(__name__)
T = TypeVar("T", PostContent, GuidePost)

# 문장 끝: 마침표·물음표·느낌표 뒤 공백. 소수점(4.39%) 뒤에는 공백이 없어서 문장 끝으로 보지 않는다.
SENTENCE_END = re.compile(r"(?<=[.?!])\s+")


@dataclass
class Target:
    sentence: str        # 고칠 문장
    paragraph: str       # 그 문장이 들어 있는 문단 (앞뒤 맥락)
    phrases: list[str]   # 이 문장에서 걸린 표현


def find_targets(content: T, limits: dict[str, int]) -> list[Target]:
    """허용 횟수를 넘긴 표현이 든 문장. 허용 횟수만큼은 앞에서부터 남겨 둔다."""
    over = over_limit(content, limits)
    left = {phrase: allowed for phrase, (_, allowed) in over.items()}
    targets: list[Target] = []
    seen: set[str] = set()
    for para in post_texts(content):
        for sentence in SENTENCE_END.split(para):
            bad = []
            for phrase in over:
                n = sentence.count(phrase)
                if n and left[phrase] >= n:
                    left[phrase] -= n
                elif n:
                    bad.append(phrase)
            if bad and sentence not in seen:
                seen.add(sentence)
                targets.append(Target(sentence=sentence, paragraph=para, phrases=bad))
    return targets


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUM.findall(text)}


def apply_fixes(content: T, targets: list[Target], fixes: list[SentenceFix], limits: dict[str, int]) -> tuple[T, int]:
    """고친 문장을 원래 자리에 바꿔 끼운다. (새 글, 바꾼 문장 수)를 돌려준다."""
    banned = [phrase for phrase, allowed in limits.items() if allowed == 0]
    swaps: dict[str, str] = {}
    for fix in fixes:
        if not 1 <= fix.number <= len(targets):
            continue
        target = targets[fix.number - 1]
        new = fix.text.strip()
        if not new or new == target.sentence:
            continue
        if any(p in new for p in banned) or any(p in new for p in target.phrases):
            continue   # 고친 문장에 금지 표현이 또 있음
        if _numbers(new) != _numbers(target.sentence):
            continue   # 숫자가 생기거나 빠짐
        swaps[target.sentence] = new
    if not swaps:
        return content, 0
    return type(content).model_validate(_swap(content.model_dump(), swaps)), len(swaps)


def _swap(value, swaps: dict[str, str]):
    if isinstance(value, str):
        for old, new in swaps.items():
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_swap(v, swaps) for v in value]
    if isinstance(value, dict):
        return {k: _swap(v, swaps) for k, v in value.items()}
    return value


def polish(settings: Settings, content: T, offline: bool = False) -> T:
    """말투 검사에 걸린 문장을 한 번 고쳐 쓴다. 고치지 못한 문장은 그대로 두고, 뒤의 검사가 경고로 남긴다."""
    if offline or settings.write.provider != "claude":
        return content
    limits = settings.guard.ai_phrases
    targets = find_targets(content, limits)
    if not targets:
        return content
    from econblog.write.claude import make_client, structured_call
    from econblog.write.prompting import _env, guide_system_prompt, system_prompt

    system = guide_system_prompt(settings) if isinstance(content, GuidePost) else system_prompt(settings)
    user = _env(settings).get_template("style_fix.md.j2").render(targets=targets)
    try:
        result = structured_call(make_client(), settings, system, user, StyleFixes)
    except Exception as e:  # noqa: BLE001
        log.warning("말투 고쳐 쓰기 실패: %s", e)
        return content
    fixed, count = apply_fixes(content, targets, result.fixes, limits)
    log.info("말투 고쳐 쓰기: 걸린 문장 %d개 중 %d개 교체", len(targets), count)
    return fixed
