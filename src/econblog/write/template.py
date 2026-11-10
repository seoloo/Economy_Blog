"""LLM 없이 데이터만으로 뼈대 초안을 만든다 (--dry-run, 또는 Claude 실패 시 대체).

이 초안은 그대로 발행하지 않는다. 사람이 분석을 채워 넣어야 한다.
"""

from __future__ import annotations

from econblog.models import Issue, PostContent, Series
from econblog.write.base import WriteContext, Writer
from econblog.write.prompting import title_tail


def _move(s: Series | None) -> str | None:
    if s is None or s.change_pct is None or s.change is None:
        return None
    direction = "상승" if s.change > 0 else "하락" if s.change < 0 else "보합"
    if s.spec.unit == "%":  # 금리는 %p 변화로 쓴다
        return f"{s.spec.label}은(는) {s.last:.2f}%로 전일 대비 {s.change:+.2f}%p {direction}"
    return f"{s.spec.label}은(는) {s.last:,.2f}{s.spec.unit}로 전일 대비 {s.change_pct:+.2f}% {direction}"


class TemplateWriter(Writer):
    def write(self, ctx: WriteContext) -> PostContent:
        snap = ctx.snapshot
        by_cat: dict[str, list[str]] = {}
        for spec in self.settings.series:
            line = _move(snap.get(spec.key))
            if line:
                by_cat.setdefault(spec.category, []).append(line)

        def para(*cats: str) -> list[str]:
            lines = [x for c in cats for x in by_cat.get(c, [])]
            return [", ".join(lines) + "했습니다."] if lines else ["(데이터 없음)"]

        issues = [
            Issue(
                title=f"[검토 필요] {x.article.title}",
                paragraphs=[f"({x.article.source_name}) {x.article.summary or '요약 없음'}", "→ 분석을 직접 작성하세요."],
                reference_urls=[x.article.url],
            )
            for x in ctx.articles[:4]
        ]
        top = ctx.articles[0].topic if ctx.articles else "시장"
        return PostContent(
            title=f"[템플릿 초안] {top} 정리 | {title_tail(self.settings, ctx.date)}",
            lead="LLM 없이 데이터로만 만든 뼈대 초안입니다. 도입부와 분석을 직접 채워 넣어야 합니다.",
            summary_line="(오늘 시장 한 줄 요약을 직접 작성하세요)",
            global_market=para("index_global", "rates", "commodity"),
            korea_market=para("index_kr", "fx"),
            korea_checkpoints=["(해외 흐름이 오늘 국내 증시에 줄 영향을 직접 작성하세요)"],
            issues=issues,
            watch_points=["(직접 작성)"],
            closing="(마무리 한두 문장을 직접 작성하세요)",
            tags=["미국증시", "코스피", "경제", "시황", "환율", "금리"],
        )
