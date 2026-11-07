"""초안 작성 단계."""

from __future__ import annotations

import logging

from econblog import registry
from econblog.config import Settings
from econblog.models import PostContent
from econblog.write.base import WriteContext

log = logging.getLogger(__name__)

WRITERS: dict[str, str] = {
    "claude": "econblog.write.claude:ClaudeWriter",
    "template": "econblog.write.template:TemplateWriter",
}


def write_post(settings: Settings, ctx: WriteContext, offline: bool = False) -> tuple[PostContent, list[str]]:
    """(본문, 경고 목록)을 반환한다. 대체 작성기로 넘어가면 경고에 남긴다."""
    cfg = settings.write
    name = cfg.fallback if offline else cfg.provider
    try:
        return registry.load(WRITERS, name)(settings).write(ctx), []
    except Exception as e:  # noqa: BLE001
        if name == cfg.fallback:
            raise
        log.warning("작성기 '%s' 실패, '%s'로 대체: %s", name, cfg.fallback, e)
        content = registry.load(WRITERS, cfg.fallback)(settings).write(ctx)
        return content, [f"LLM 작성 실패로 템플릿 초안을 사용했습니다: {e}"]
