"""시장 데이터(Quote)를 본문 표와 '오늘 시장 한눈에' 상자에 넣을 문자열로 바꾼다.

수치는 여기서만 만든다. LLM 이 쓴 문단의 숫자와 달리 데이터와 항상 일치한다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date

from econblog.models import PROVIDER_NAMES, Quote

# 한국 관례: 상승 빨강, 하락 파랑. 흰 바탕에서 글자로 읽힐 만큼 진한 색을 쓰고 ▲▼ 도 함께 표시한다.
UP_COLOR = "#c62828"
DOWN_COLOR = "#1a5fb4"
FLAT_COLOR = "#52514e"


@dataclass(frozen=True)
class QuoteRow:
    label: str
    value: str          # 6,812.34 / 4.12% / 1,385.20원
    change: str         # ▲31.20 / ▼0.05%p / 0.00 / -
    change_pct: str     # +1.21% / - (금리는 %p 변화만 쓴다)
    headline: str       # 요약 상자용 한 칸: 지수·환율은 ▲1.21%, 금리는 ▲0.05%p
    color: str
    as_of: date


@dataclass(frozen=True)
class QuoteTable:
    rows: list[QuoteRow]
    note: str           # 기준일 · 자료 출처


def _is_rate(q: Quote) -> bool:
    return q.unit == "%"


def format_value(q: Quote) -> str:
    if _is_rate(q):
        return f"{q.last:.2f}%"
    if q.unit in ("원", "달러"):
        return f"{q.last:,.2f}{q.unit}"
    return f"{q.last:,.2f}"


def format_quote(q: Quote) -> QuoteRow:
    rate = _is_rate(q)
    suffix = "%p" if rate else ""
    if q.change is None:
        change, color, sign = "-", FLAT_COLOR, 0
    elif round(q.change, 2) == 0:
        change, color, sign = f"0.00{suffix}", FLAT_COLOR, 0
    else:
        sign = 1 if q.change > 0 else -1
        arrow = "▲" if sign > 0 else "▼"
        change, color = f"{arrow}{abs(q.change):,.2f}{suffix}", UP_COLOR if sign > 0 else DOWN_COLOR

    if rate or q.change_pct is None:
        pct = "-"
    else:
        pct = f"{q.change_pct:+.2f}%"

    if rate or q.change_pct is None:
        headline = change
    elif sign == 0:
        headline = "0.00%"
    else:
        headline = f"{'▲' if sign > 0 else '▼'}{abs(q.change_pct):.2f}%"
    return QuoteRow(label=q.label, value=format_value(q), change=change, change_pct=pct,
                    headline=headline, color=color, as_of=q.as_of)


def _md(d: date) -> str:
    return f"{d.month}/{d.day}"


def as_of_note(rows: list[QuoteRow]) -> str:
    """가장 많은 기준일을 대표로 쓰고, 다른 날짜인 항목만 따로 적는다."""
    if not rows:
        return ""
    common, _ = Counter(r.as_of for r in rows).most_common(1)[0]
    others = [f"{r.label} {_md(r.as_of)}" for r in rows if r.as_of != common]
    note = f"기준일 {_md(common)}"
    return note + (f" (단, {', '.join(others)})" if others else "")


def build_table(quotes: dict[str, Quote], keys: list[str]) -> QuoteTable:
    picked = [quotes[k] for k in keys if k in quotes]
    rows = [format_quote(q) for q in picked]
    providers = sorted({PROVIDER_NAMES.get(q.provider, q.provider) for q in picked})
    parts = [as_of_note(rows)] + (["자료: " + ", ".join(providers)] if providers else [])
    return QuoteTable(rows=rows, note=" · ".join(p for p in parts if p))
