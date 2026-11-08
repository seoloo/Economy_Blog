"""prompts/ 의 템플릿을 채워 Writer 입력을 만든다."""

from __future__ import annotations

from datetime import date, timedelta

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from econblog.config import Settings
from econblog.models import NowRow
from econblog.market import moves
from econblog.write.base import CardContext, WriteContext

WEEKDAYS = "월화수목금토일"
# 인스타 카드에만 쓰는 시리즈 (업종 ETF·개별 종목). 블로그 글 프롬프트에는 넣지 않는다.
CARD_ONLY = {"us_sector", "us_stock", "kr_stock", "crypto"}


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
    series = [ctx.snapshot.series[s.key] for s in settings.series
              if s.key in ctx.snapshot.series and s.category not in CARD_ONLY]

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


# ---------------------------------------------------------------- 인스타 카드


EN_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

CARD_STRUCTURE = {
    "ko": {
        "cover": "표지: 사진 배경, 날짜, 제목 두 줄(cover_lines), 숫자 칩 세 개",
        "board": "숫자판: 지표 10개 (자동) + 한 줄 요약(board_note)",
        "story": "이슈 카드: 위쪽 사진, 제목 두 줄, 본문 두 문단, '왜 중요할까' 상자",
        "sectors": "미국 업종 히트맵 (자동) + 제목(sector_title)",
        "movers": "미국 대형주 등락 순위 (자동) + 제목(movers_title)",
        "check": "아시아·한국 체크 (자동) + 설명(asia_note)",
        "events": "앞으로 볼 일정 (events, 없으면 이 장은 빠짐)",
        "closing": "마지막 장: 다음 거래일 체크리스트 3개(checklist). 각 항목 아래에 금요일·전날 수치가 자동으로 붙음",
    },
    "en": {
        "cover": "Cover: photo, date, two-line headline (cover_lines), three number chips",
        "board": "Scoreboard: 10 indicators (auto) + one-line note (board_note)",
        "story": "Story card: photo on top, two-line headline, two paragraphs, 'why it matters' box",
        "sectors": "S&P 500 sector heatmap (auto) + title (sector_title)",
        "movers": "Mega-cap movers ranking (auto) + title (movers_title)",
        "check": "Asia & Korea check (auto numbers) + note (asia_note)",
        "events": "What's next (events; card is dropped if empty)",
        "closing": "Closing card: next-session checklist of 3 items (checklist); the latest value is added automatically under each",
    },
}


def _fact(s, lang: str) -> str:
    change, _ = moves.change_text(s, lang)
    return f"[{s.spec.key}] {moves.name(s, lang)} ({s.spec.id}): {moves.value_text(s, lang)}, {change} ({s.last_date})"


def card_date_label(d: date) -> str:
    return f"{d.month}월 {d.day}일({WEEKDAYS[d.weekday()]})"


def cards_system_prompt(settings: Settings, ctx: CardContext) -> str:
    return _env(settings).get_template("cards_system.md.j2").render(
        lang=ctx.account.lang, brand=ctx.account.brand, date_label=card_date_label(ctx.date))


def cards_user_prompt(settings: Settings, ctx: CardContext) -> str:
    lang = ctx.account.lang
    snap = ctx.snapshot
    main_keys = [s.key for s in settings.series if s.category not in CARD_ONLY or s.category == "crypto"]
    us = snap.series.get("sp500")
    session = us.last_date if us and us.last_date else ctx.date
    return _env(settings).get_template("cards.md.j2").render(
        lang=lang,
        date=ctx.date,
        weekday=WEEKDAYS[ctx.date.weekday()],
        session_label=f"{EN_WEEKDAYS[session.weekday()]}, {session:%b} {session.day}",
        market=[_fact(s, lang) for s in moves.by_keys(snap, main_keys)],
        missing=sorted(snap.errors),
        sectors=[_fact(s, lang) for s in moves.ranked(snap, "us_sector")],
        stocks=[_fact(s, lang) for s in moves.ranked(snap, "us_stock")],
        korea=[_fact(s, lang) for s in moves.by_keys(snap, ctx.account.check or ["st_hynix", "st_samsung"])],
        post=ctx.post,
        articles=ctx.articles,
        structure=[CARD_STRUCTURE[lang][k] for k in dict.fromkeys(ctx.account.slides)],
    )

