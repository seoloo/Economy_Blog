from econblog.config import load_settings


def test_settings_load():
    s = load_settings()
    assert s.sources, "sources.yaml 이 비어 있음"
    assert s.series, "series.yaml 이 비어 있음"
    assert s.charts, "settings.yaml charts 가 비어 있음"


def test_ids_are_unique():
    s = load_settings()
    source_ids = [x.id for x in s.sources]
    series_keys = [x.key for x in s.series]
    assert len(source_ids) == len(set(source_ids))
    assert len(series_keys) == len(set(series_keys))


def test_charts_reference_known_series():
    s = load_settings()
    keys = {x.key for x in s.series}
    for chart in s.charts:
        missing = set(chart.series) - keys
        assert not missing, f"{chart.key}: 정의되지 않은 시리즈 {missing}"


def test_regions_have_sources():
    s = load_settings()
    assert {x.region for x in s.sources} == {"kr", "global"}
