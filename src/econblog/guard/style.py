"""AI 가 쓴 티가 나는 표현이 너무 자주 나오는지 검사한다.

settings.yaml guard.ai_phrases 에 표현과 허용 횟수를 둔다. 넘으면 경고로 남겨 사람이 다듬게 한다.
"""

from __future__ import annotations

from econblog.guard.copyright import post_texts
from econblog.models import CardCopy, GuidePost, PostContent


def find_ai_phrases(content: PostContent | GuidePost | CardCopy, limits: dict[str, int]) -> list[str]:
    text = "\n".join(post_texts(content))
    over = []
    for phrase, allowed in limits.items():
        count = text.count(phrase)
        if count > allowed:
            over.append(f"「{phrase}」 {count}회(허용 {allowed})")
    return ["AI 말투 표현이 많음: " + ", ".join(over)] if over else []


def find_vague_phrases(content: CardCopy, phrases: list[str]) -> list[str]:
    """카드 글에 모호한 표현(도시 이름으로 시장 부르기, 비유, 막연한 예측)이 있으면 경고한다."""
    text = " ".join(post_texts(content)).lower()
    found = [p for p in phrases if p.lower() in text]
    return ["카드 문장이 모호함: " + ", ".join(f"「{p}」" for p in found)] if found else []

