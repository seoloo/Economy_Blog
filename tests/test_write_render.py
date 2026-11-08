from datetime import date

from conftest import make_article

from econblog.deliver.email import build_message
from econblog.guard.copyright import find_copied_passages
from econblog.models import Issue, PostContent, Quote
from econblog.pipeline import run
from econblog.render.quotes import DOWN_COLOR, FLAT_COLOR, UP_COLOR, build_table, format_quote


def _content(paragraph: str) -> PostContent:
    return PostContent(
        title="11월 7일 시황", lead="요약", summary_line="한 줄", global_market=[paragraph], korea_market=["국내"],
        korea_checkpoints=["체크"],
        issues=[Issue(title="이슈", paragraphs=["분석"], reference_urls=["https://example.com/a"])],
        watch_points=["FOMC"], closing="마무리", tags=["경제"],
    )


def _quote(key: str, unit: str, last: float, change: float | None) -> Quote:
    prev = last - change if change is not None else None
    pct = change / prev * 100 if change is not None and prev else None
    return Quote(key=key, label=key, unit=unit, category="", provider="yahoo", as_of=date(2026, 11, 6),
                 last=last, change=change, change_pct=pct)


def test_quote_formatting_uses_arrows_and_percent_points():
    up = format_quote(_quote("kospi", "pt", 2612.3, 31.2))
    assert (up.value, up.change, up.color) == ("2,612.30", "▲31.20", UP_COLOR)
    assert up.change_pct == "+1.21%" and up.headline == "▲1.21%"
    rate = format_quote(_quote("us10y", "%", 4.12, -0.05))
    assert (rate.value, rate.change, rate.change_pct, rate.headline) == ("4.12%", "▼0.05%p", "-", "▼0.05%p")
    assert rate.color == DOWN_COLOR
    flat = format_quote(_quote("base", "%", 2.5, 0.0))
    assert flat.change == "0.00%p" and flat.color == FLAT_COLOR
    assert format_quote(_quote("fx", "원", 1385.2, None)).change == "-"


def test_table_note_lists_dates_that_differ():
    quotes = {"a": _quote("a", "pt", 1.0, 0.1), "b": _quote("b", "pt", 2.0, 0.1)}
    quotes["c"] = _quote("c", "%", 3.0, 0.1).model_copy(update={"as_of": date(2026, 11, 5), "provider": "ecos"})
    table = build_table(quotes, ["a", "b", "c", "missing"])
    assert [r.label for r in table.rows] == ["a", "b", "c"]
    assert table.note == "기준일 11/6 (단, c 11/5) · 자료: Yahoo Finance, 한국은행 ECOS"


def test_copyright_guard_flags_copied_sentence():
    src = make_article("제목", summary="한국은행 금융통화위원회는 이날 기준금리를 연 2.50%로 동결하고 연내 추가 인하 가능성을 열어뒀다고 밝혔다.")
    copied = _content("한국은행 금융통화위원회는 이날 기준금리를 연 2.50%로 동결하고 연내 추가 인하 가능성을 열어뒀다고 밝혔다.")
    rewritten = _content("한은이 금리를 2.50%에서 묶었습니다. 다만 연말 전 한 차례 더 내릴 여지는 남겨 두었습니다.")
    assert find_copied_passages(copied, [src], 40)
    assert not find_copied_passages(rewritten, [src], 40)


def test_dry_run_end_to_end(settings):
    post = run(settings, run_date=date(2026, 11, 6), offline=True, deliver_methods=["local"])
    out = post.output_dir
    for name in ("post.html", "preview.html", "naver.html", "meta.json"):
        assert (out / name).exists()
    html = (out / "post.html").read_text(encoding="utf-8")
    preview = (out / "preview.html").read_text(encoding="utf-8")
    assert "[이미지 삽입]" in html and "<img" not in html
    assert '<img src="charts/index_change.png"' in preview and '<img src="charts/thumb_market.jpg"' in preview
    assert html.index("[이미지 삽입] thumb_market.jpg") < html.index("오늘 시장 한눈에")  # 시황 썸네일이 맨 위
    assert not (out / "charts" / "cover.png").exists()  # 고정 썸네일이 있으면 데이터 표지는 그리지 않는다
    assert "투자를 권유하지" in html or "권유하지 않습니다" in html
    assert "발행 전 확인" in preview and "발행 전 확인" not in html
    # 데이터로 만든 요약 상자·표와 새 섹션
    for text in ("오늘 시장 한눈에", "<table", "코스피", "한국 증시 체크포인트", "정리하면", "■ 최근에 올라온 글",
                 "키워드: 미국증시"):
        assert text in html, text
    assert html.index("정리하면") < html.index("※ 이 글은") < html.index("■ 최근에 올라온 글") < html.index("키워드:")
    assert html.index("오늘 시장 한눈에") < html.index("해외 시장") < html.index("국내 시장")
    assert post.draft.content.title.startswith("[템플릿 초안] 미국증시·코스피 시황 | 11월 6일(금)")

    msg = build_message(post, "me@example.com", "me@example.com")
    html_body = next(p.get_content() for p in msg.walk() if p.get_content_type() == "text/html" and not p.get_filename())
    assert 'src="cid:index_change"' in html_body
    attachments = {p.get_filename() for p in msg.iter_attachments()}
    assert {"post.html", "naver.html", "index_change.png"} <= attachments
    naver = (out / "naver.html").read_text(encoding="utf-8")
    assert "[사진] index_change.png" in naver and "발행 전 확인" not in naver and "<img" not in naver
    assert any(p.get("Content-ID") == "<index_change>" for p in msg.walk())


def test_rich_text_escapes_html_and_bolds_marked_phrase():
    from econblog.render.html import rich

    assert str(rich("<b>x</b> **핵심** 끝")) == "&lt;b&gt;x&lt;/b&gt; <strong>핵심</strong> 끝"


def test_ai_phrase_guard_counts_over_limit():
    from econblog.guard.style import find_ai_phrases

    content = _content("상승한 것으로 보입니다. 하락한 것으로 보입니다. 이른바 블루웨이브입니다.")
    warnings = find_ai_phrases(content, {"로 보입니다": 1, "이른바": 0, "결국": 1})
    assert len(warnings) == 1
    assert "「로 보입니다」 2회" in warnings[0] and "「이른바」 1회" in warnings[0] and "결국" not in warnings[0]


def test_published_charts_use_public_url(settings, monkeypatch):
    """공개 레포에 올린 차트는 post.html·메일 모두 공개 주소를 쓴다 (붙여넣기 한 번으로 이미지까지)."""
    from econblog.charts import publish

    calls = []

    class FakeResponse:
        def __init__(self, status):
            self.status_code = status

        def json(self):
            return {"sha": "old"}

        def raise_for_status(self):
            pass

    class FakeSession:
        headers: dict = {}

        def __init__(self):
            self.headers = {}

        def get(self, url, **kw):
            return FakeResponse(404)

        def put(self, url, json, **kw):
            calls.append((url, json))
            return FakeResponse(201)

    monkeypatch.setenv("CHARTS_REPO_TOKEN", "test-token")
    monkeypatch.setattr(publish.requests, "Session", FakeSession)
    settings.publish.repo = "owner/assets"
    settings.publish.base_url = "https://owner.github.io/assets"

    from econblog.market import build_snapshot
    from econblog.charts import build_charts

    snap = build_snapshot(settings, date(2026, 11, 6), offline=True)
    charts = build_charts(settings, snap, settings.resolve_output_dir() / "charts")
    assert publish.publish_charts(settings, charts, date(2026, 11, 6)) == []
    assert {c.url for c in charts} == {f"https://owner.github.io/assets/2026-11-06/{c.path.name}" for c in charts}
    assert calls[0][0].endswith("/repos/owner/assets/contents/2026-11-06/cover.png")
    assert "sha" not in calls[0][1]

    # 오프라인(dry run)에서는 올리지 않는다
    assert publish.publish_charts(settings, charts, date(2026, 11, 6), offline=True) == []


def test_fixed_thumbnail_uploads_once_to_shared(settings, monkeypatch):
    """고정 썸네일은 날짜 폴더가 아니라 shared/ 에 올리고, 같은 파일이 이미 있으면 다시 올리지 않는다."""
    from econblog.charts import publish
    from econblog.charts.cover import fixed_thumbnail

    thumb = fixed_thumbnail(settings, "daily", settings.resolve_output_dir() / "charts")
    assert thumb is not None and thumb.position == "cover"
    assert thumb.path.read_bytes() == (settings.root / "assets/brand/thumb_market.jpg").read_bytes()  # 다시 압축하지 않는다
    remote = {"sha": None}
    puts = []

    class FakeResponse:
        def __init__(self, status):
            self.status_code = status

        def json(self):
            return {"sha": remote["sha"]}

        def raise_for_status(self):
            pass

    class FakeSession:
        def __init__(self):
            self.headers = {}

        def get(self, url, **kw):
            return FakeResponse(200 if remote["sha"] else 404)

        def put(self, url, json, **kw):
            puts.append(url)
            return FakeResponse(201)

    monkeypatch.setenv("CHARTS_REPO_TOKEN", "test-token")
    monkeypatch.setattr(publish.requests, "Session", FakeSession)
    settings.publish.repo = "owner/assets"
    settings.publish.base_url = "https://owner.github.io/assets"

    assert publish.publish_charts(settings, [thumb], date(2026, 11, 6)) == []
    assert thumb.url == "https://owner.github.io/assets/shared/thumb_market.jpg"
    assert puts == ["https://api.github.com/repos/owner/assets/contents/shared/thumb_market.jpg"]

    remote["sha"] = publish._blob_sha(thumb.path.read_bytes())  # 다음 날: 같은 파일이 이미 있음
    assert publish.publish_charts(settings, [thumb], date(2026, 11, 7)) == []
    assert len(puts) == 1


def test_without_thumbnail_each_post_draws_its_own_cover(settings):
    settings.thumbnails = {}
    post = run(settings, run_date=date(2026, 11, 6), offline=True, deliver_methods=["local"])
    html = (post.output_dir / "post.html").read_text(encoding="utf-8")
    assert html.index("[이미지 삽입] cover.png") < html.index("오늘 시장 한눈에")
    assert not (post.output_dir / "charts" / "thumb_market.jpg").exists()


def test_google_news_reference_shows_real_publisher():
    from econblog.render.html import ref_link

    a = make_article("코스피 급락…외국인 매도 - 경향신문", url="https://news.google.com/x")
    a = a.model_copy(update={"source_id": "gnews_kr_business", "source_name": "Google 뉴스 경제(한국)"})
    assert ref_link(a)[1:] == ("코스피 급락…외국인 매도", "경향신문")
    b = make_article("Fed holds rates - not a publisher split")  # 구글 뉴스가 아니면 그대로
    assert ref_link(b)[1:] == (b.title, b.source_name)


def test_tistory_html_uses_only_styles_the_editor_keeps(settings):
    """티스토리 기본 편집기는 margin·padding·border·font-size 등을 지우고 thead/th 를 글자로 풀어 버린다."""
    import re

    post = run(settings, run_date=date(2026, 11, 6), offline=True, deliver_methods=[])
    assert "<th" not in post.html and "<thead" not in post.html
    kept = {"color", "background-color", "text-align", "border-collapse", "width", "list-style-type"}
    used = {prop.strip() for style in re.findall(r'(?<![-\w])style="([^"]*)"', post.html)
            for prop in (d.split(":")[0] for d in style.split(";")) if prop.strip()}
    assert used <= kept, used - kept
    assert 'blockquote data-ke-style="style3"' in post.html  # 오늘 시장 한눈에 상자
