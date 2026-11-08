"""인스타 카드뉴스를 그린다: 카드 글(CardCopy) + 시장 데이터 → 카드 HTML → Chrome 스크린샷 → JPEG.

카드의 숫자(숫자판·업종·대형주·아시아 체크·표지 칩)는 모두 데이터에서 만든다.
Chrome 이 없으면 HTML 만 남기고 경고한다 (GitHub Actions 의 ubuntu 러너에는 Chrome 이 깔려 있다).
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from PIL import Image
from pydantic import BaseModel, Field

from econblog.config import CardAccount, Settings
from econblog.market import moves
from econblog.models import CardCopy, CardEvent, MarketSnapshot
from econblog.render.html import rich
from econblog.render.photos import PhotoPicker

log = logging.getLogger(__name__)

W, H = 1080, 1350
EN_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
KO_WEEKDAYS = "월화수목금토일"

THEMES = {
    "ko": dict(lang="ko", bg="#f5f3ee", ink="#121826", muted="#6b7280", line="#e4e0d6", dark="#13294b", glow="#2b4f8a",
               hl1="#13294b", hl1ink="#ffffff", hl2="#ffd23f", hl2ink="#13294b", accent="#ffd23f", kick="#e5484d",
               up="#e03a3e", down="#2f6fdb", dot="#e5484d", mark="rgba(255,210,63,.6)",
               heat_up=("#fbd5d5", "#c62828"), heat_down=("#d6e3fb", "#1d4ed8"),
               swipe="넘겨 보기", why="왜 중요할까", disclaimer="투자 권유가 아닌 정보 제공용 콘텐츠입니다.",
               photo_credit="사진: Pixabay"),
    "en": dict(lang="en", bg="#f3f4f1", ink="#0b0d10", muted="#6b7078", line="#dfe1dc", dark="#0b0d10", glow="#1f3b2b",
               hl1="#0b0d10", hl1ink="#ffffff", hl2="#2ee66b", hl2ink="#0b0d10", accent="#2ee66b", kick="#0f9d58",
               up="#12a150", down="#e5383b", dot="#2ee66b", mark="rgba(46,230,107,.38)",
               heat_up=("#d3f2dd", "#11843f"), heat_down=("#fbd6d6", "#c3262b"),
               swipe="Swipe", why="WHY IT MATTERS", disclaimer="For information only. Not financial advice.",
               photo_credit="Photo: Pixabay"),
}


class Chip(BaseModel):
    n: str
    v: str
    d: str


class Tile(BaseModel):
    n: str
    v: str
    c: str
    d: str


class Cell(BaseModel):
    n: str
    v: str
    bg: str
    fg: str
    wide: bool = False


class RankRow(BaseModel):
    tk: str
    nm: str
    p: float


class Slide(BaseModel):
    """카드 한 장. kind 에 따라 필요한 칸만 채운다."""

    kind: str
    page: str = ""
    kicker: str = ""
    title: str = ""
    sub: str = ""
    label: str = ""
    lines: list[str] = Field(default_factory=list)
    chips: list[Chip] = Field(default_factory=list)
    tiles: list[Tile] = Field(default_factory=list)
    cells: list[Cell] = Field(default_factory=list)
    rows: list[RankRow] = Field(default_factory=list)
    paras: list[object] = Field(default_factory=list)   # rich() 를 거친 Markup
    why: str = ""
    note: str = ""
    events: list[CardEvent] = Field(default_factory=list)
    photo: str | None = None   # file:// 주소
    credit: str = ""
    source: str = ""


# ---------------------------------------------------------------- 카드 구성


def _mix(a: str, b: str, t: float) -> str:
    x, y = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(p + (q - p) * t):02x}" for p, q in zip(x, y))


def _heat(v: float, vmax: float, theme: dict) -> tuple[str, str]:
    if round(v, 2) == 0:
        return "#e6e3dc", theme["ink"]
    t = min(1.0, abs(v) / vmax) ** 0.7 if vmax else 0.0
    light, strong = theme["heat_up"] if v > 0 else theme["heat_down"]
    return _mix(light, strong, 0.25 + 0.75 * t), ("#ffffff" if t > 0.4 else theme["ink"])


def _tiles(series, lang) -> list[Tile]:
    out = []
    for s in series:
        c, d = moves.change_text(s, lang)
        out.append(Tile(n=moves.name(s, lang), v=moves.value_text(s, lang), c=c, d=d))
    return out


def _session(snapshot: MarketSnapshot, fallback: date) -> date:
    s = snapshot.series.get("sp500") or next(iter(snapshot.series.values()), None)
    return s.last_date if s and s.last_date else fallback


def _source(lang: str, d: date) -> str:
    return f"자료: Yahoo Finance · {d.month}/{d.day} 종가" if lang == "ko" else f"Data: Yahoo Finance · {d:%b} {d.day} close"


def build_slides(account: CardAccount, text: CardCopy, snapshot: MarketSnapshot, run_date: date,
                 photos: PhotoPicker | None = None) -> list[Slide]:
    lang = account.lang
    theme = THEMES[lang]
    session = _session(snapshot, run_date)
    source = _source(lang, session)
    used_photo = False

    def photo(query: str, orientation: str) -> str | None:
        nonlocal used_photo
        path = photos.find(query, orientation) if photos else None
        used_photo = used_photo or path is not None
        return path.resolve().as_uri() if path else None

    cover_photo = photo(text.cover_photo_query, "vertical")
    slides: list[Slide] = []
    story_i = 0
    for kind in account.slides:
        if kind == "cover":
            chips = []
            for s in moves.by_keys(snapshot, account.chips):
                _, d = moves.change_text(s, lang)
                chips.append(Chip(n=moves.name(s, lang), v=moves.signed_pct(s), d=d))
            kicker = (f"{run_date.month}월 {run_date.day}일({KO_WEEKDAYS[run_date.weekday()]}) 아침 시황" if lang == "ko"
                      else f"MARKET WRAP · {EN_WEEKDAYS[session.weekday()][:3].upper()}, {session:%b} {session.day}".upper())
            slides.append(Slide(kind="cover", kicker=kicker, lines=[x for x in text.cover_lines[:2] if x],
                                chips=chips, photo=cover_photo))
        elif kind == "board":
            title = (f"{session.month}월 {session.day}일 마감 기준" if lang == "ko"
                     else f"{EN_WEEKDAYS[session.weekday()]}'s close")
            slides.append(Slide(kind="board", kicker="오늘 시장 한눈에" if lang == "ko" else "THE SCOREBOARD",
                                title=title, sub=text.board_note, tiles=_tiles(moves.by_keys(snapshot, account.board), lang),
                                source=source))
        elif kind == "story":
            if story_i >= len(text.stories):
                continue
            st = text.stories[story_i]
            story_i += 1
            p = photo(st.photo_query, "horizontal")
            slides.append(Slide(kind="story", label=(f"이슈 {story_i}" if lang == "ko" else f"STORY {story_i}"),
                                lines=[x for x in st.headline[:2] if x], paras=[rich(x) for x in st.paragraphs[:2]],
                                why=st.why.replace("**", ""), photo=p, source=source,
                                credit=theme["photo_credit"] if p else ""))
        elif kind == "sectors":
            sec = moves.ranked(snapshot, "us_sector")
            if not sec:
                continue
            vmax = max(abs(s.change_pct or 0) for s in sec)
            cells = []
            for i, s in enumerate(sec):
                bg, fg = _heat(s.change_pct or 0, vmax, theme)
                cells.append(Cell(n=moves.name(s, lang), v=moves.signed_pct(s), bg=bg, fg=fg, wide=(i == 0 and len(sec) == 11)))
            top, bottom = sec[0], sec[-1]
            sub = (f"S&P 500 업종 {len(sec)}개 등락률 · 최고 {moves.name(top, lang)} {moves.signed_pct(top)}, "
                   f"최저 {moves.name(bottom, lang)} {moves.signed_pct(bottom)}" if lang == "ko" else
                   f"S&P 500 sectors · {moves.name(top, lang)} {moves.signed_pct(top)}, "
                   f"{moves.name(bottom, lang)} {moves.signed_pct(bottom)}")
            slides.append(Slide(kind="sectors", kicker="미국 업종 히트맵" if lang == "ko" else "SECTOR HEATMAP",
                                title=text.sector_title, sub=sub, cells=cells,
                                source=source.replace("Yahoo Finance", "Yahoo Finance (업종 ETF)" if lang == "ko"
                                                      else "Yahoo Finance (SPDR sector ETFs)")))
        elif kind == "movers":
            st = moves.ranked(snapshot, "us_stock")
            if not st:
                continue
            rows = [RankRow(tk=s.spec.id, nm=moves.name(s, lang), p=round(s.change_pct or 0, 2)) for s in st]
            sub = (f"시가총액 상위 {len(st)}개 종목" if lang == "ko" else f"{len(st)} largest U.S. names")
            slides.append(Slide(kind="movers", kicker="미국 대형주 등락" if lang == "ko" else "MEGA-CAP MOVERS",
                                title=text.movers_title, sub=sub, rows=rows, source=source))
        elif kind == "check":
            rows = _tiles(moves.by_keys(snapshot, account.check), lang)
            if not rows:
                continue
            slides.append(Slide(kind="check", kicker="아시아·한국 체크" if lang == "ko" else "ASIA & KOREA CHECK",
                                title="아시아 시장" if lang == "ko" else "Asia at a glance",
                                sub="같은 날 뉴욕 개장 전" if lang == "ko" else "Earlier the same day, before New York opened",
                                tiles=rows, note=text.asia_note.replace("**", ""), source=source))
        elif kind == "events":
            if not text.events:
                continue
            slides.append(Slide(kind="events", kicker="앞으로 볼 일정" if lang == "ko" else "WHAT'S NEXT",
                                title="다음에 볼 것" if lang == "ko" else "On the calendar", events=text.events[:5],
                                source=theme_source_note(lang)))
        elif kind == "closing":
            p = photo(text.cover_photo_query + " night", "vertical") or cover_photo
            slides.append(Slide(kind="closing", kicker="오늘의 한 줄" if lang == "ko" else "THE TAKEAWAY",
                                lines=[x.strip() for x in text.takeaway.replace("**", "").split("\n") if x.strip()],
                                photo=p, credit=theme["photo_credit"] if p else ""))
    if used_photo:
        for s in slides:
            if s.kind == "cover":
                s.credit = theme["photo_credit"]
    n = len(slides)
    for i, s in enumerate(slides, 1):
        s.page = f"{i}/{n}"
    return slides


def theme_source_note(lang: str) -> str:
    return "그냥모아 정리 · 기사 기준" if lang == "ko" else "Compiled from news reports"


# ---------------------------------------------------------------- 그리기


def chrome_path() -> str | None:
    """CHROME 환경변수 → PATH 의 chrome/chromium → Windows 기본 설치 경로 순으로 찾는다."""
    if p := os.environ.get("CHROME"):
        return p
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        if p := shutil.which(name):
            return p
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if Path(p).exists():
            return p
    return None


def _env(settings: Settings) -> Environment:
    return Environment(loader=FileSystemLoader(settings.templates_dir / "cards"), undefined=StrictUndefined,
                       autoescape=select_autoescape(["html", "j2"]), trim_blocks=True, lstrip_blocks=True)


def render_html(settings: Settings, account: CardAccount, slides: list[Slide]) -> list[str]:
    tpl = _env(settings).get_template("card.html.j2")
    theme = {**THEMES[account.lang], "brand": account.brand, "brand_dot": account.brand_dot}
    return [tpl.render(t=theme, s=s) for s in slides]


def screenshot(chrome: str, html: Path, out: Path) -> None:
    png = out.with_suffix(".png")
    args = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
            "--allow-file-access-from-files", f"--window-size={W},{H}", f"--screenshot={png}", html.resolve().as_uri()]
    if platform.system() == "Linux":
        args.insert(1, "--no-sandbox")
    subprocess.run(args, capture_output=True, timeout=90, check=False)
    if not png.exists():
        raise RuntimeError(f"Chrome 스크린샷 실패: {html.name}")
    with Image.open(png) as im:   # 인스타 API 는 JPEG 만 받는다
        im.convert("RGB").save(out, "JPEG", quality=92, optimize=True, progressive=True)
    png.unlink()


def render_cards(settings: Settings, account: CardAccount, slides: list[Slide], out_dir: Path) -> tuple[list[Path], list[str]]:
    """카드 HTML 을 저장하고 JPEG 로 찍는다. (이미지 목록, 경고)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = render_html(settings, account, slides)
    htmls = []
    for i, page in enumerate(pages, 1):
        path = out_dir / f"{i:02d}.html"
        path.write_text(page, encoding="utf-8")
        htmls.append(path)
    if not settings.instagram.render_images:
        return [], []
    chrome = chrome_path()
    if not chrome:
        return [], ["Chrome 을 찾지 못해 카드 이미지를 만들지 못했습니다 (HTML 만 저장)"]
    images = []
    for html in htmls:
        out = html.with_suffix(".jpg")
        screenshot(chrome, html, out)
        images.append(out)
    return images, []
