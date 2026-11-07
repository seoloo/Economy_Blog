"""Claude API 로 초안을 작성한다. 출력은 PostContent 스키마로 강제한다 (structured outputs)."""

from __future__ import annotations

import logging

from econblog.config import env
from econblog.models import PostContent
from econblog.write.base import WriteContext, Writer
from econblog.write.prompting import system_prompt, user_prompt

log = logging.getLogger(__name__)


class ClaudeWriter(Writer):
    def __init__(self, settings):
        super().__init__(settings)
        if not env("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY 가 설정되지 않음")
        import anthropic

        self.client = anthropic.Anthropic()

    def write(self, ctx: WriteContext) -> PostContent:
        cfg = self.settings.write
        response = self.client.messages.parse(
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            system=system_prompt(self.settings),
            messages=[{"role": "user", "content": user_prompt(self.settings, ctx)}],
            output_config={"effort": cfg.effort},
            output_format=PostContent,
        )
        log.info(
            "Claude 사용량: 입력 %s / 출력 %s 토큰 (stop=%s)",
            response.usage.input_tokens, response.usage.output_tokens, response.stop_reason,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Claude 가 요청을 거절함")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("출력이 max_tokens 에서 잘림 (settings.yaml write.max_tokens 상향 필요)")
        if response.parsed_output is None:
            raise RuntimeError("구조화된 출력을 해석하지 못함")
        return response.parsed_output
