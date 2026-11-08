"""글 맨 위 대표 이미지(썸네일). 티스토리 목록·검색 결과·공유 미리보기에 이 이미지가 쓰인다.

settings.thumbnails 에 글 종류별 고정 썸네일이 있으면 그 그림을 쓰고(fixed_thumbnail), 없으면 글마다 아래 표지를 그린다.

데이터만으로 그린다: 연재 제목, 날짜, 주요 지표 4개(값과 등락).
목록에서 정사각형으로 잘려도 내용이 보이도록 가운데 900px 안에 배치한다.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image
from matplotlib.patches import Ellipse, FancyBboxPatch

from econblog.charts import style
from econblog.charts.base import ChartBuilder
from econblog.models import Chart, ChartSpec, MarketSnapshot, Series

log = logging.getLogger(__name__)

WEEKDAYS = "월화수목금토일"
BG = "#13294b"
TILE = "#1e3a63"
TEXT = "#ffffff"
TEXT_2 = "#c3d1e6"
# 어두운 바탕에서 읽히도록 밝게 조정한 상승/하락 색
UP = "#ff7b72"
DOWN = "#79b8ff"


def _value(s: Series) -> str:
    if s.spec.unit == "%":
        return f"{s.last:.2f}%"
    return f"{s.last:,.2f}"


def _change(s: Series) -> tuple[str, str]:
    if s.spec.unit == "%":
        if s.change is None or round(s.change, 2) == 0:
            return "0.00%p", TEXT_2
        return f"{'▲' if s.change > 0 else '▼'} {abs(s.change):.2f}%p", UP if s.change > 0 else DOWN
    pct = s.change_pct
    if pct is None or round(pct, 2) == 0:
        return "0.00%", TEXT_2
    return f"{'▲' if pct > 0 else '▼'} {abs(pct):.2f}%", UP if pct > 0 else DOWN


class CoverChart(ChartBuilder):
    def build(self, spec: ChartSpec, snapshot: MarketSnapshot, out_dir: Path) -> Chart | None:
        series = [s for s in self.collect_series(spec, snapshot) if s.last is not None][:4]
        if not series:
            return None
        style.apply()
        bold = style.bold_font()
        fig = plt.figure(figsize=(8, 6), dpi=style.DPI)  # 1200x900
        fig.patch.set_facecolor(BG)
        d = snapshot.as_of

        fig.text(0.5, 0.86, f"{d.year}. {d.month}. {d.day} ({WEEKDAYS[d.weekday()]})", ha="center",
                 fontsize=15, color=TEXT_2)
        fig.text(0.5, 0.745, self.settings.post.series_title, ha="center", fontproperties=bold,
                 fontsize=34, color=TEXT)

        # 2x2 지표 타일 (가운데 x 0.15~0.85)
        w, h, gap = 0.335, 0.215, 0.03
        x0, y_top = 0.5 - w - gap / 2, 0.62
        for i, s in enumerate(series):
            col, row = i % 2, i // 2
            x = x0 + col * (w + gap)
            y = y_top - (row + 1) * h - row * gap
            fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.02",
                                              transform=fig.transFigure, facecolor=TILE, edgecolor="none"))
            change, color = _change(s)
            fig.text(x + 0.03, y + h - 0.045, s.spec.label, fontsize=14, color=TEXT_2, va="top")
            fig.text(x + 0.03, y + 0.095, _value(s), fontproperties=bold, fontsize=22, color=TEXT, va="center")
            fig.text(x + 0.03, y + 0.04, change, fontsize=15, color=color, va="center")

        fig.text(0.5, 0.05, f"{self.settings.blog_name} · {self.source_note(series)}", ha="center",
                 fontsize=10.5, color=TEXT_2)

        path = out_dir / f"{spec.key}.png"
        fig.savefig(path, dpi=style.DPI, facecolor=BG)
        plt.close(fig)
        moves = ", ".join(f"{s.spec.label} {_value(s)} {_change(s)[0]}" for s in series)
        title = f"{d.month}월 {d.day}일 {self.settings.post.series_title}"
        return Chart(key=spec.key, title=title, path=path, alt_text=f"{title}: {moves}",
                     source_note=self.source_note(series))


# ---------------------------------------------------------------- 경제 공부 글 대표 이미지

CREAM = "#f6f1e7"
NAVY = "#13294b"
NAVY_2 = "#4a5a75"
RED = "#e5484d"


def _wrap(text: str, width: int) -> list[str]:
    """띄어쓰기 단위로 한 줄 width 글자 안팎이 되게 나눈다."""
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


def guide_cover(settings, keyword: str, subtitle: str, out_path: Path) -> Chart:
    """크림 바탕에 남색 키워드와 빨간 점(블로그 아이콘과 같은 톤). 데이터 없이 글 주제만으로 그린다."""
    style.apply()
    bold = style.bold_font()
    fig = plt.figure(figsize=(8, 6), dpi=style.DPI)  # 1200x900
    fig.patch.set_facecolor(CREAM)
    left = 0.15

    fig.patches.append(FancyBboxPatch((left, 0.74), 0.17, 0.065, boxstyle="round,pad=0,rounding_size=0.015",
                                      transform=fig.transFigure, facecolor=NAVY, edgecolor="none"))
    fig.text(left + 0.085, 0.7725, "경제 공부", ha="center", va="center", fontproperties=bold, fontsize=15,
             color="#ffffff")

    lines = _wrap(keyword, 9)
    size = 46 if max(len(x) for x in lines) <= 8 else 40
    y = 0.64
    last = None
    for line in lines:
        last = fig.text(left, y, line, fontproperties=bold, fontsize=size, color=NAVY, va="top")
        y -= 0.115 if size == 46 else 0.10
    fig.canvas.draw()
    box = last.get_window_extent().transformed(fig.transFigure.inverted())
    r = 0.011  # 그림 비율이 4:3 이라 세로 반지름을 늘려 정원으로 그린다
    fig.patches.append(Ellipse((box.x1 + 0.022, box.y0 + r * 2), 2 * r, 2 * r * 8 / 6, transform=fig.transFigure,
                               facecolor=RED, edgecolor="none"))

    sub_y = y - 0.045
    for line in _wrap(subtitle, 18):
        fig.text(left, sub_y, line, fontsize=20, color=NAVY_2, va="top")
        sub_y -= 0.065

    fig.add_artist(plt.Line2D([left, 0.85], [0.13, 0.13], transform=fig.transFigure, color=NAVY, linewidth=1.2))
    fig.text(left, 0.085, settings.blog_name, fontproperties=bold, fontsize=14, color=NAVY, va="center")

    fig.savefig(out_path, dpi=style.DPI, facecolor=CREAM)
    plt.close(fig)
    title = f"{keyword} - {subtitle}"
    return Chart(key=out_path.stem, title=title, path=out_path, alt_text=title, source_note="", position="cover")


THUMB_WIDTH = 1200


def fixed_thumbnail(settings, kind: str, out_dir: Path) -> Chart | None:
    """글 종류(daily·guide)마다 정해 둔 대표 이미지(settings.thumbnails)를 쓴다. 설정이나 파일이 없으면 None.

    가로 1200px 이하 JPEG 는 그대로 쓰고, 그 밖의 그림은 1200px JPEG(약 200KB)로 줄인다.
    공개 레포에는 날짜 폴더가 아니라 shared/ 에 한 번만 올라간다 (Chart.shared).
    """
    src = settings.thumbnail_path(kind)
    if src is None:
        return None
    if not src.exists():
        log.warning("고정 썸네일 파일이 없어 표지를 그립니다: %s", settings.thumbnails[kind])
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{src.stem}.jpg"
    with Image.open(src) as im:
        if im.format == "JPEG" and im.width <= THUMB_WIDTH:
            shutil.copyfile(src, out_path)
        else:
            im = im.convert("RGB")
            if im.width > THUMB_WIDTH:
                im = im.resize((THUMB_WIDTH, round(im.height * THUMB_WIDTH / im.width)), Image.LANCZOS)
            im.save(out_path, "JPEG", quality=88, optimize=True, progressive=True)
    alt = f"{settings.blog_name} 대표 이미지"
    return Chart(key="thumbnail", title=alt, path=out_path, alt_text=alt, source_note="",
                 position="cover", shared=True)
