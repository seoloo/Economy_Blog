"""차트 공통 스타일. 모든 차트가 같은 색·폰트·여백을 쓰도록 여기서만 정의한다.

색은 dataviz 기준 팔레트에서 가져왔다.
- 상승/하락은 국내 관례대로 빨강/파랑이고, 값 라벨(+/-)을 함께 표시해 색에만 의존하지 않는다.
- 2개 시리즈는 카테고리 1·2번(파랑·주황) 순서를 고정한다.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
UP = "#e34948"
DOWN = "#2a78d6"
NEUTRAL_FILL = "#e1e0d9"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

FIGSIZE = (8, 4.5)  # 16:9, 150dpi → 1200x675
DPI = 150
KOREAN_FONTS = ["Malgun Gothic", "NanumGothic", "NanumBarunGothic", "Noto Sans CJK KR", "Noto Sans KR", "AppleGothic"]


def _pick_font() -> str | None:
    installed = {f.name for f in font_manager.fontManager.ttflist}
    return next((name for name in KOREAN_FONTS if name in installed), None)


def bold_font() -> font_manager.FontProperties:
    """한글 굵은 글꼴. 나눔고딕 Bold 는 별도 패밀리 이름으로 잡혀 weight 지정만으로는 못 찾는다."""
    family = _pick_font()
    if family:
        for f in font_manager.fontManager.ttflist:
            is_bold = (isinstance(f.weight, int) and f.weight >= 600) or f.weight in ("bold", "heavy", "black") \
                or "bold" in f.fname.lower() or "bd." in f.fname.lower()
            if f.name.startswith(family) and is_bold:
                return font_manager.FontProperties(fname=f.fname)
    return font_manager.FontProperties(weight="bold")


def apply() -> None:
    font = _pick_font()
    if font:
        plt.rcParams["font.family"] = font
    plt.rcParams.update(
        {
            "axes.unicode_minus": False,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK_2,
            "axes.titlecolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 2,
        }
    )


def decorate(fig, title: str, subtitle: str, source_note: str, brand: str) -> None:
    """제목·부제는 좌상단, 출처는 좌하단, 블로그 이름은 우하단."""
    fig.text(0.02, 0.965, title, fontsize=14, fontproperties=bold_font(), color=INK, va="top")
    fig.text(0.02, 0.895, subtitle, fontsize=9.5, color=INK_2, va="top")
    fig.text(0.02, 0.025, source_note, fontsize=8, color=MUTED, va="bottom")
    fig.text(0.98, 0.025, brand, fontsize=8, color=MUTED, va="bottom", ha="right")


def save(fig, path) -> None:
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
