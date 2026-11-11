"""경제 공부 글(오래 읽히는 개념 설명) 작성. 시황 글과 같은 방식으로 Claude 를 쓰고, 실패하면 뼈대 초안으로 대체한다."""

from __future__ import annotations

import logging

from econblog import registry
from econblog.config import Settings
from econblog.models import GuideMyth, GuidePost, GuideSection, GuideTable
from econblog.write.base import GuideContext
from econblog.write.prompting import guide_rows, guide_system_prompt, guide_user_prompt

log = logging.getLogger(__name__)

GUIDE_WRITERS: dict[str, str] = {
    "claude": "econblog.write.guide:ClaudeGuideWriter",
    "template": "econblog.write.guide:TemplateGuideWriter",
}


class ClaudeGuideWriter:
    def __init__(self, settings: Settings):
        from econblog.write.claude import make_client

        self.settings = settings
        self.client = make_client()

    def write(self, ctx: GuideContext) -> GuidePost:
        from econblog.write.claude import structured_call

        return structured_call(self.client, self.settings, guide_system_prompt(self.settings),
                               guide_user_prompt(self.settings, ctx), GuidePost)


class TemplateGuideWriter:
    """LLM 없이 주제 정보와 데이터로 뼈대만 만든다. 그대로 발행하지 않는다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def write(self, ctx: GuideContext) -> GuidePost:
        t = ctx.topic
        rows = guide_rows(ctx)
        now = " / ".join(f"{r.label} {r.value} (1년 전 {r.year_ago})" for r in rows) or "(데이터 없음)"
        return GuidePost(
            title=f"[템플릿 초안] {t.keyword} 정리｜{t.subtitle}",
            lead=[f"{t.keyword}에 대해 정리하는 글입니다. 도입부를 직접 작성하세요.",
                  "글 마지막에는 흔히 하는 오해도 정리합니다."],
            sections=[GuideSection(heading=f"{t.keyword}란?", paragraphs=[f"다룰 내용: {t.angle}"],
                                   table=GuideTable(columns=["구분", "내용"], rows=[["(직접 작성)", "(직접 작성)"]]))],
            now_comment=f"지금 수치: {now}",
            myths=[GuideMyth(myth="(흔히 하는 오해)", fact="(실제로는 어떤지 직접 작성)")],
            closing="(맺음 문단을 직접 작성하세요)",
            tags=[t.keyword.replace(" ", ""), "경제공부", "경제용어"],
            keywords=[t.keyword, f"{t.keyword} 뜻", "경제 공부"],
        )


def write_guide(settings: Settings, ctx: GuideContext, offline: bool = False) -> tuple[GuidePost, list[str]]:
    cfg = settings.write
    name = cfg.fallback if offline else cfg.provider
    try:
        return registry.load(GUIDE_WRITERS, name)(settings).write(ctx), []
    except Exception as e:  # noqa: BLE001
        if name == cfg.fallback:
            raise
        log.warning("경제 공부 작성기 '%s' 실패, '%s'로 대체: %s", name, cfg.fallback, e)
        post = registry.load(GUIDE_WRITERS, cfg.fallback)(settings).write(ctx)
        return post, [f"LLM 작성 실패로 템플릿 초안을 사용했습니다: {e}"]
