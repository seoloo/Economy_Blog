"""prompts/ 의 템플릿을 채워 Writer 입력을 만든다."""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from econblog.config import Settings
from econblog.write.base import WriteContext

WEEKDAYS = "월화수목금토일"


def _env(settings: Settings) -> Environment:
    return Environment(loader=FileSystemLoader(settings.prompts_dir), undefined=StrictUndefined, autoescape=False)


def system_prompt(settings: Settings) -> str:
    return _env(settings).get_template("system.md").render(blog_name=settings.blog_name)


def user_prompt(settings: Settings, ctx: WriteContext) -> str:
    series = [ctx.snapshot.series[s.key] for s in settings.series if s.key in ctx.snapshot.series]
    return _env(settings).get_template("daily_post.md.j2").render(
        date=ctx.date,
        weekday=WEEKDAYS[ctx.date.weekday()],
        series=series,
        missing=sorted(ctx.snapshot.errors),
        charts=ctx.charts,
        global_articles=[x for x in ctx.articles if x.article.region == "global"],
        kr_articles=[x for x in ctx.articles if x.article.region == "kr"],
    )
