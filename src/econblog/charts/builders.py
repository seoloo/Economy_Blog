"""차트 종류별 빌더. settings.yaml charts[].type 과 charts/__init__.py BUILDERS 로 연결된다."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from econblog.charts import style
from econblog.charts.base import ChartBuilder
from econblog.models import Chart, ChartSpec, MarketSnapshot


def _fmt_signed(v: float, unit: str = "%") -> str:
    return f"{v:+.2f}{unit}"


def _date_axis(ax, days: int) -> None:
    """1년이 넘는 기간은 월/일 대신 연.월로 표시한다."""
    if days > 400:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%y.%m"))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))


class ChangeBarChart(ChartBuilder):
    """시리즈별 전일 대비 등락률 가로 막대. 위에서부터 설정 순서대로 표시."""

    def build(self, spec: ChartSpec, snapshot: MarketSnapshot, out_dir: Path) -> Chart | None:
        rows = [(s, s.change_pct) for s in self.collect_series(spec, snapshot) if s.change_pct is not None]
        if not rows:
            return None
        style.apply()
        fig, ax = plt.subplots(figsize=style.FIGSIZE)
        fig.subplots_adjust(left=0.2, right=0.9, top=0.78, bottom=0.13)

        labels = [f"{s.spec.label} ({s.last_date:%m/%d})" for s, _ in rows]
        values = [v for _, v in rows]
        colors = [style.UP if v >= 0 else style.DOWN for v in values]
        y = list(range(len(rows)))[::-1]
        ax.barh(y, values, height=0.55, color=colors, edgecolor=style.SURFACE, linewidth=2)
        ax.set_yticks(y, labels, color=style.INK_2, fontsize=10)
        ax.axvline(0, color=style.MUTED, linewidth=0.8)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)

        span = max(abs(v) for v in values) or 1.0
        ax.set_xlim(-span * 1.35, span * 1.35)
        for yi, v in zip(y, values):
            ax.text(v + (span * 0.04 if v >= 0 else -span * 0.04), yi, _fmt_signed(v),
                    va="center", ha="left" if v >= 0 else "right", fontsize=9.5, color=style.INK)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))
        ax.xaxis.set_major_formatter(lambda x, _: f"{x:+.2f}%" if span < 1 else f"{x:+.1f}%")
        ax.set_axisbelow(True)

        series = [s for s, _ in rows]
        style.decorate(fig, spec.title, f"기준: {snapshot.as_of:%Y-%m-%d} · 괄호는 각 시장 마지막 거래일",
                       self.source_note(series), self.settings.blog_name)
        path = out_dir / f"{spec.key}.png"
        style.save(fig, path)
        alt = ", ".join(f"{s.spec.label} {_fmt_signed(v)}" for s, v in rows)
        return Chart(key=spec.key, title=spec.title, path=path, alt_text=f"{spec.title}: {alt}",
                     source_note=self.source_note(series))


class LineChart(ChartBuilder):
    """최근 N일 추이 선 그래프. 마지막 값에 직접 라벨."""

    def build(self, spec: ChartSpec, snapshot: MarketSnapshot, out_dir: Path) -> Chart | None:
        series = [s.last_days(spec.days) for s in self.collect_series(spec, snapshot)]
        series = [s for s in series if len(s.values) >= 2]
        if not series:
            return None
        style.apply()
        fig, ax = plt.subplots(figsize=style.FIGSIZE)
        fig.subplots_adjust(left=0.08, right=0.88, top=0.78, bottom=0.14)

        for i, s in enumerate(series):
            color = style.SERIES[i % len(style.SERIES)]
            ax.plot(s.dates, s.values, color=color, label=s.spec.label)
            ax.scatter([s.dates[-1]], [s.last], s=28, color=color, edgecolor=style.SURFACE, linewidth=2, zorder=3)
            ax.annotate(f"{s.last:,.2f}", (s.dates[-1], s.last), xytext=(8, 0), textcoords="offset points",
                        va="center", fontsize=9.5, color=style.INK)
        ax.grid(axis="x", visible=False)
        _date_axis(ax, spec.days)
        ax.yaxis.set_major_formatter(lambda y, _: f"{y:,.0f}" if abs(y) >= 1000 else f"{y:,.2f}")
        if len(series) >= 2:
            ax.legend(loc="upper left", ncols=len(series))

        first = series[0]
        sub = f"{first.spec.label} {first.last:,.2f}{first.spec.unit}"
        if first.change is not None:
            sub += f" (전일 대비 {first.change:+,.2f})"
        style.decorate(fig, spec.title, f"기준: {first.last_date:%Y-%m-%d} · {sub}",
                       self.source_note(series), self.settings.blog_name)
        path = out_dir / f"{spec.key}.png"
        style.save(fig, path)
        return Chart(key=spec.key, title=spec.title, path=path, alt_text=f"{spec.title}: {sub}",
                     source_note=self.source_note(series))


class SpreadChart(ChartBuilder):
    """두 시리즈(같은 단위)와 그 차이. 위 패널은 두 선, 아래 패널은 차이 (축은 각각 하나)."""

    def build(self, spec: ChartSpec, snapshot: MarketSnapshot, out_dir: Path) -> Chart | None:
        series = self.collect_series(spec, snapshot)
        if len(series) != 2:
            return None
        a, b = series
        a, b = a.last_days(spec.days), b.last_days(spec.days)
        bmap = dict(zip(b.dates, b.values))
        common = [(d, v, bmap[d]) for d, v in zip(a.dates, a.values) if d in bmap]
        if len(common) < 2:
            return None
        dates = [d for d, _, _ in common]
        va = [x for _, x, _ in common]
        vb = [y for _, _, y in common]
        spread = [x - y for x, y in zip(va, vb)]

        style.apply()
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=style.FIGSIZE, sharex=True,
                                       gridspec_kw={"height_ratios": [2, 1], "hspace": 0.12})
        fig.subplots_adjust(left=0.08, right=0.88, top=0.76, bottom=0.12)

        for vals, s, color in ((va, a, style.SERIES[0]), (vb, b, style.SERIES[1])):
            ax1.plot(dates, vals, color=color, label=s.spec.label)
            ax1.annotate(f"{vals[-1]:.2f}{s.spec.unit}", (dates[-1], vals[-1]), xytext=(8, 0),
                         textcoords="offset points", va="center", fontsize=9.5, color=style.INK)
        ax1.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncols=2, borderaxespad=0.2)
        ax1.grid(axis="x", visible=False)

        ax2.fill_between(dates, spread, 0, color=style.NEUTRAL_FILL, linewidth=0)
        ax2.plot(dates, spread, color=style.INK_2, linewidth=1.5)
        ax2.axhline(0, color=style.MUTED, linewidth=0.8)
        ax2.annotate(f"{spread[-1]:+.2f}%p", (dates[-1], spread[-1]), xytext=(8, 0),
                     textcoords="offset points", va="center", fontsize=9.5, color=style.INK)
        ax2.text(0.0, 1.02, f"금리차({a.spec.label} - {b.spec.label}, %p)", transform=ax2.transAxes,
                 fontsize=8.5, color=style.INK_2, va="bottom")
        ax2.grid(axis="x", visible=False)
        _date_axis(ax2, spec.days)

        sub = f"{a.spec.label} {va[-1]:.2f}% · {b.spec.label} {vb[-1]:.2f}% · 차이 {spread[-1]:+.2f}%p"
        style.decorate(fig, spec.title, f"기준: {dates[-1]:%Y-%m-%d} · {sub}",
                       self.source_note(series), self.settings.blog_name)
        path = out_dir / f"{spec.key}.png"
        style.save(fig, path)
        return Chart(key=spec.key, title=spec.title, path=path, alt_text=f"{spec.title}: {sub}",
                     source_note=self.source_note(series))
