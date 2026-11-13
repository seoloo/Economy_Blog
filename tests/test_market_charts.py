from datetime import date

from econblog.charts import build_charts
from econblog.market import build_snapshot
from econblog.market.ecos import parse_rows
from econblog.market.fred import parse_observations
from econblog.models import SeriesSpec


def test_fred_skips_missing_values():
    spec = SeriesSpec(key="us10y", label="10년", provider="fred", id="DGS10")
    s = parse_observations(spec, {"observations": [
        {"date": "2026-11-04", "value": "4.10"},
        {"date": "2026-11-05", "value": "."},
        {"date": "2026-11-06", "value": "4.20"},
    ]})
    assert s.values == [4.10, 4.20]
    assert round(s.change, 2) == 0.10


def test_ecos_parses_rows_and_errors():
    spec = SeriesSpec(key="kr3y", label="국고채 3년", provider="ecos", id="817Y002", params={"cycle": "D"})
    s = parse_rows(spec, {"StatisticSearch": {"row": [
        {"TIME": "20261106", "DATA_VALUE": "2.61"},
        {"TIME": "20261105", "DATA_VALUE": "2.58"},
    ]}})
    assert s.dates == [date(2026, 11, 5), date(2026, 11, 6)]
    try:
        parse_rows(spec, {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}})
    except ValueError as e:
        assert "INFO-200" in str(e)
    else:
        raise AssertionError("ECOS 오류 응답을 예외로 처리해야 함")


def test_offline_snapshot_and_charts(settings, tmp_path):
    snapshot = build_snapshot(settings, date(2026, 11, 6), offline=True)
    assert not snapshot.errors
    assert {s.key for s in settings.series} == set(snapshot.series)

    charts = build_charts(settings, snapshot, tmp_path)
    assert [c.key for c in charts] == [c.key for c in settings.charts]
    for c in charts:
        assert c.path.exists() and c.path.stat().st_size > 10_000
        assert c.alt_text and c.source_note.startswith("자료:")


def test_treasury_csv_picks_column_and_sorts_dates():
    from econblog.market.treasury import parse_csv

    spec = SeriesSpec(key="us10y", label="10년", provider="treasury", id="10 Yr")
    s = parse_csv(spec, 'Date,"1 Mo","2 Yr","10 Yr"\n'
                        "11/13/2026,4.10,4.88,5.15\n"
                        "11/12/2026,4.12,4.86,5.10\n"
                        "11/10/2026,4.05,4.73,\n")
    assert s.dates == [date(2026, 11, 12), date(2026, 11, 13)]   # 빈 칸은 건너뛰고 날짜 오름차순
    assert s.values == [5.10, 5.15] and round(s.change, 2) == 0.05


def test_treasury_falls_back_to_fred(monkeypatch, settings):
    from econblog.market import treasury
    from econblog.market.fred import FredProvider
    from econblog.models import Series

    def boom(*a, **k):
        raise ConnectionError("blocked")

    monkeypatch.setattr(treasury.requests, "get", boom)
    monkeypatch.setattr(FredProvider, "__init__", lambda self, s: None)
    monkeypatch.setattr(FredProvider, "fetch", lambda self, spec, start, end: Series(
        spec=spec, dates=[date(2026, 11, 12)], values=[5.10]))
    spec = SeriesSpec(key="us10y", label="10년", provider="treasury", id="10 Yr", params={"fred": "DGS10"})
    s = treasury.TreasuryProvider(settings).fetch(spec, date(2026, 11, 1), date(2026, 11, 14))
    assert s.values == [5.10] and s.spec.provider == "fred" and s.spec.id == "10 Yr"
