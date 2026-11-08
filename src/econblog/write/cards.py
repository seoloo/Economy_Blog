"""인스타 카드뉴스 글 작성. 시황 글과 같이 Claude 를 쓰고, 실패하거나 오프라인이면 데이터로 뼈대만 만든다."""

from __future__ import annotations

import logging

from econblog import registry
from econblog.config import Settings
from econblog.market import moves
from econblog.models import CardCheck, CardCopy, CardEvent, CardStory
from econblog.write.base import CardContext
from econblog.write.prompting import (
    cards_review_system_prompt,
    cards_review_user_prompt,
    cards_system_prompt,
    cards_user_prompt,
)

log = logging.getLogger(__name__)

CARD_WRITERS: dict[str, str] = {
    "claude": "econblog.write.cards:ClaudeCardWriter",
    "template": "econblog.write.cards:TemplateCardWriter",
}


class ClaudeCardWriter:
    def __init__(self, settings: Settings):
        from econblog.write.claude import make_client

        self.settings = settings
        self.client = make_client()

    def write(self, ctx: CardContext) -> CardCopy:
        from econblog.write.claude import structured_call

        draft = structured_call(self.client, self.settings, cards_system_prompt(self.settings, ctx),
                                cards_user_prompt(self.settings, ctx), CardCopy)
        if not self.settings.instagram.review:
            return draft
        # 교열: 같은 자료를 보여 주고 숫자·모호한 표현·근거 없는 일정을 고친 최종본을 받는다
        try:
            return structured_call(self.client, self.settings, cards_review_system_prompt(self.settings, ctx),
                                   cards_review_user_prompt(self.settings, ctx, draft), CardCopy)
        except Exception as e:  # noqa: BLE001
            log.warning("카드 교열 실패, 초안을 그대로 씁니다: %s", e)
            return draft


def _two_lines(text: str) -> list[str]:
    words = text.split()
    if len(words) < 2:
        return [text, ""]
    half = len(text) / 2
    acc, cut = 0, 1
    for i, w in enumerate(words[:-1], 1):
        acc += len(w) + 1
        if acc >= half:
            cut = i
            break
    return [" ".join(words[:cut]), " ".join(words[cut:])]


class TemplateCardWriter:
    """LLM 없이 데이터와 시황 글로 뼈대만 만든다 (dry run·장애 대비). 그대로 게시하지 않는다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def write(self, ctx: CardContext) -> CardCopy:
        lang = ctx.account.lang
        snap = ctx.snapshot
        chips = moves.by_keys(snap, ctx.account.chips)
        cover = [f"{moves.name(s, lang)} {moves.signed_pct(s)}" for s in chips[:2]] or ["", ""]
        sectors = moves.ranked(snap, "us_sector")
        stocks = moves.ranked(snap, "us_stock")
        top_sector = f"{moves.name(sectors[0], lang)} {moves.signed_pct(sectors[0])}" if sectors else ""
        top_stock = f"{moves.name(stocks[0], lang)} {moves.signed_pct(stocks[0])}" if stocks else ""
        if lang == "ko":
            post = ctx.post
            issues = post.issues[:2] if post else []
            stories = [CardStory(headline=_two_lines(i.title), paragraphs=i.paragraphs[:2],
                                 why=i.paragraphs[-1] if len(i.paragraphs) > 2 else "", photo_query="stock market")
                       for i in issues]
            events = [CardEvent(when="이번 주", title=w[:20], detail=w, tag="일정") for w in (post.watch_points[:4] if post else [])]
            return CardCopy(
                cover_lines=cover, cover_photo_query="stock market", board_note=post.summary_line if post else "",
                stories=stories, sector_title=f"업종 1위 {top_sector}", movers_title=f"{top_stock}",
                asia_note="", events=events,
                checklist=[CardCheck(key=s.spec.key, title=moves.name(s, lang), detail="다음 거래일에도 이어지는지") for s in chips],
                caption="\n\n".join([post.title, post.summary_line] if post else []),
                hashtags=post.tags if post else ["미국증시", "코스피"],
            )
        stories = [
            CardStory(headline=["Sectors", "at the close"],
                      paragraphs=[f"The best sector was **{top_sector}**.", f"The top mega cap was **{top_stock}**."],
                      why="Draft only. Written without the language model.", photo_query="new york stock exchange"),
        ]
        return CardCopy(
            cover_lines=cover, cover_photo_query="new york stock exchange", board_note="Draft written from data only.",
            stories=stories, sector_title=f"Leader: {top_sector}", movers_title=f"Top: {top_stock}",
            asia_note="Draft written from data only.", events=[],
            korea_story=CardStory(
                headline=["Korea", "at the close"],
                paragraphs=[" ".join(f"{moves.name(s, lang)} {moves.signed_pct(s)}."
                                     for s in moves.by_keys(ctx.snapshot, ["kospi", "kosdaq", "usdkrw"]))],
                why="Draft only. Written without the language model.", photo_query="seoul skyline night"),
            checklist=[CardCheck(key=s.spec.key, title=moves.name(s, lang), detail="whether the move holds") for s in chips],
            caption="Draft written from data only.", hashtags=["stockmarket", "stocks"],
        )


def write_cards(settings: Settings, ctx: CardContext, offline: bool = False) -> tuple[CardCopy, list[str]]:
    cfg = settings.write
    name = cfg.fallback if offline else cfg.provider
    try:
        return registry.load(CARD_WRITERS, name)(settings).write(ctx), []
    except Exception as e:  # noqa: BLE001
        if name == cfg.fallback:
            raise
        log.warning("카드 작성기 '%s' 실패, '%s'로 대체: %s", name, cfg.fallback, e)
        return registry.load(CARD_WRITERS, cfg.fallback)(settings).write(ctx), [f"LLM 작성 실패로 뼈대 카드를 만들었습니다: {e}"]
