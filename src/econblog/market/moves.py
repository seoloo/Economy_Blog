"""시리즈 값·등락을 사람이 읽는 글자로 바꾸고, 업종·종목을 등락률 순으로 줄 세운다.

인스타 카드(render/cards.py)와 카드 글 프롬프트(write/prompting.py)가 같이 쓴다.
카드에 들어가는 숫자는 모두 여기서 데이터로 만든다. LLM 은 숫자 칸을 채우지 않는다.
"""

from __future__ import annotations

from typing import Literal

from econblog.models import MarketSnapshot, Series

Lang = Literal["ko", "en"]
Direction = Literal["up", "down", "flat"]


def name(s: Series, lang: Lang) -> str:
    return (s.spec.label_en or s.spec.label) if lang == "en" else s.spec.label


def direction(x: float | None) -> Direction:
    if x is None or round(x, 2) == 0:
        return "flat"
    return "up" if x > 0 else "down"


def _arrow(d: Direction) -> str:
    return {"up": "▲ ", "down": "▼ ", "flat": ""}[d]


def value_text(s: Series, lang: Lang) -> str:
    v, unit = s.last, s.spec.unit
    if v is None:
        return "-"
    if unit == "%":
        return f"{v:.2f}%"
    num = f"{v:,.0f}" if abs(v) >= 10000 and unit in ("원", "달러") else f"{v:,.2f}"
    if lang == "ko":
        return num + (unit if unit in ("원", "달러") else "")
    if unit == "달러":
        return "$" + num
    if unit == "원" and s.spec.category == "kr_stock":
        return "₩" + num
    return num


def change_text(s: Series, lang: Lang) -> tuple[str, Direction]:
    """(▲ 1.23%, up). 금리는 등락률 대신 변화폭으로 쓴다 (한국어 %p, 영어 bp)."""
    if s.spec.unit == "%":
        ch = s.change
        d = direction(ch)
        if ch is None:
            return "-", d
        return (f"{_arrow(d)}{abs(ch) * 100:.1f} bp" if lang == "en" else f"{_arrow(d)}{abs(ch):.2f}%p"), d
    p = s.change_pct
    d = direction(p)
    if p is None:
        return "-", d
    return f"{_arrow(d)}{abs(p):.2f}%", d


def signed_pct(s: Series) -> str:
    """+1.23% / −0.45% (표지 칩·제목용, 화살표 없이)."""
    p = s.change_pct or 0.0
    return f"{'+' if p >= 0 else '−'}{abs(p):.2f}%"


def by_keys(snapshot: MarketSnapshot, keys: list[str]) -> list[Series]:
    return [snapshot.series[k] for k in keys if k in snapshot.series and snapshot.series[k].last is not None]


def ranked(snapshot: MarketSnapshot, category: str) -> list[Series]:
    """카테고리(us_sector, us_stock …)의 시리즈를 등락률 높은 순으로."""
    items = [s for s in snapshot.series.values() if s.spec.category == category and s.change_pct is not None]
    return sorted(items, key=lambda s: -(s.change_pct or 0))
