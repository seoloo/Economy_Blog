"""인스타 카드 글의 숫자가 우리 시장 데이터와 맞는지 대조한다.

카드는 자동으로 게시되므로 기사에서 옮겨 온 숫자(검증하지 않은 값)나 계산해서 만든 숫자를 막는다.
데이터에 없는 숫자가 나오면 경고를 붙이고, 경고가 있는 날은 자동 게시하지 않는다(deliver/cards.py).
"""

from __future__ import annotations

import re

from econblog.models import CardCopy, MarketSnapshot

_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _variants(v: float) -> set[float]:
    a = abs(v)
    return {round(a, 2), round(a, 1), float(round(a))}


def allowed_numbers(snapshot: MarketSnapshot) -> set[float]:
    """데이터에서 나올 수 있는 숫자: 마지막 값, 전일 대비 변화, 등락률 (소수 둘째·첫째 자리, 정수 반올림)."""
    vals: set[float] = set()
    for s in snapshot.series.values():
        for v in (s.last, s.change, s.change_pct):
            if v is not None:
                vals |= _variants(v)
        if s.spec.unit == "%" and s.change is not None:
            vals |= _variants(s.change * 100)   # bp
        if s.last is not None and s.spec.unit == "원" and s.last >= 10000:
            vals |= _variants(s.last / 10000)   # 113.2만원
    return vals


def _numbers(text: str, names: tuple[str, ...] = ()) -> list[str]:
    text = text.replace("**", "")
    for n in names:   # 닛케이225, S&P 500, 러셀2000 처럼 이름 안의 숫자는 빼고 본다
        text = text.replace(n, " ")
    return _NUM_RE.findall(text)


def _names_with_digits(snapshot: MarketSnapshot) -> tuple[str, ...]:
    names = {x for s in snapshot.series.values() for x in (s.spec.label, s.spec.label_en, s.spec.id) if x and any(c.isdigit() for c in x)}
    names |= {"S&P500", "S&P 500", "닛케이 225", "코스피200", "코스피 200", "Nikkei 225", "Russell 2000", "Dow 30"}
    return tuple(sorted(names, key=len, reverse=True))


def find_unverified_numbers(content: CardCopy, snapshot: MarketSnapshot) -> list[str]:
    allowed = allowed_numbers(snapshot)
    names = _names_with_digits(snapshot)
    # 체크리스트 제목의 기준선(5,000선, 1,360원)은 LLM 이 정한 값이라 허용하고, 캡션에서 다시 써도 된다
    levels = {float(n.replace(",", "")) for c in content.checklist for n in _numbers(c.title, names)}
    texts = [*content.cover_lines, content.board_note, content.sector_title, content.movers_title, content.asia_note,
             content.caption, *(c.detail for c in content.checklist)]
    for st in content.stories:
        texts += [*st.headline, *st.paragraphs, st.why]
    bad: list[str] = []
    for text in texts:
        for tok in _numbers(text, names):
            x = float(tok.replace(",", ""))
            if x in allowed or x in levels:
                continue
            if x.is_integer() and (x <= 31 or 1990 <= x <= 2100):   # 개수·월·날짜·연도
                continue
            if tok not in bad:
                bad.append(tok)
    return [f"데이터에 없는 숫자: {', '.join(bad)} (기사 숫자이거나 계산한 값일 수 있음)"] if bad else []
