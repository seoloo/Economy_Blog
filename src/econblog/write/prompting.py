"""prompts/ 의 템플릿을 채워 Writer 입력을 만든다."""

from __future__ import annotations

from datetime import date, timedelta

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from econblog.config import Settings
from econblog.models import NowRow
from econblog.write.base import WriteContext

WEEKDAYS = "월화수목금토일"


def signed(x: float) -> str:
    """+1,234.56 형식. 반올림해서 0 이 되는 음수가 -0.00 으로 찍히지 않게 한다."""
    return f"{round(x, 2) + 0.0:+,.2f}"


def _env(settings: Settings) -> Environment:
    env = Environment(loader=FileSystemLoader(settings.prompts_dir), undefined=StrictUndefined, autoescape=False)
    env.filters["signed"] = signed
    return env


def title_prefix(settings: Settings, d: date) -> str:
    """제목 앞부분(연재 머리말 | 날짜). 매일 같은 형식이라 검색에서 연재로 묶인다."""
    return f"{settings.post.series_title} | {d.month}월 {d.day}일({WEEKDAYS[d.weekday()]})"


def system_prompt(settings: Settings) -> str:
    return _env(settings).get_template("system.md").render(blog_name=settings.blog_name)


def user_prompt(settings: Settings, ctx: WriteContext) -> str:
    series = [ctx.snapshot.series[s.key] for s in settings.series if s.key in ctx.snapshot.series]

    def labels(keys: list[str]) -> list[str]:
        return [ctx.snapshot.series[k].spec.label for k in keys if k in ctx.snapshot.series]

    return _env(settings).get_template("daily_post.md.j2").render(
        date=ctx.date,
        weekday=WEEKDAYS[ctx.date.weekday()],
        title_prefix=title_prefix(settings, ctx.date),
        series=series,
        missing=sorted(ctx.snapshot.errors),
        charts=ctx.charts,
        glance_labels=labels(settings.post.glance),
        global_labels=labels(settings.post.global_table),
        korea_labels=labels(settings.post.korea_table),
        global_articles=[x for x in ctx.articles if x.article.region == "global"],
        kr_articles=[x for x in ctx.articles if x.article.region == "kr"],
    )


# ---------------------------------------------------------------- 경제 공부 글


def _fmt(v: float, unit: str) -> str:
    if unit == "%":
        return f"{v:.2f}%"
    return f"{v:,.2f}{unit if unit in ('원', '달러') else ''}"


def guide_rows(ctx) -> list[NowRow]:
    """'지금 수치' 표의 줄: 마지막 값, 1년 전 값, 최근 5년 범위. 모두 수집한 데이터에서 계산한다."""
    rows = []
    for key in ctx.topic.series:
        s = ctx.snapshot.get(key)
        if s is None or s.last is None:
            continue
        unit = s.spec.unit
        target = s.last_date - timedelta(days=365)
        before = [(d, v) for d, v in zip(s.dates, s.values) if d <= target]
        past = before[-1][1] if before and (target - before[-1][0]).days <= 10 else None  # 1년 전 데이터가 없으면 비움
        window = s.last_days(1825)
        rows.append(NowRow(
            key=key,
            label=s.spec.label,
            as_of=s.last_date.isoformat(),
            value=_fmt(s.last, unit),
            year_ago=_fmt(past, unit) if past is not None else "-",
            range=f"{_fmt(min(window.values), unit)} ~ {_fmt(max(window.values), unit)}",
        ))
    return rows


def guide_system_prompt(settings: Settings) -> str:
    return _env(settings).get_template("guide_system.md").render(blog_name=settings.blog_name)


def guide_user_prompt(settings: Settings, ctx) -> str:
    return _env(settings).get_template("guide.md.j2").render(
        date=ctx.date, topic=ctx.topic, rows=guide_rows(ctx), charts=ctx.charts,
    )
