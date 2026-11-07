"""글 맨 위 대표 이미지(썸네일). 티스토리 목록·검색 결과·공유 미리보기에 이 이미지가 쓰인다.

데이터만으로 그린다: 연재 제목, 날짜, 주요 지표 4개(값과 등락).
목록에서 정사각형으로 잘려도 내용이 보이도록 가운데 900px 안에 배치한다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from econblog.charts import style
from econblog.charts.base import ChartBuilder
from econblog.models import Chart, ChartSpec, MarketSnapshot, Series

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
