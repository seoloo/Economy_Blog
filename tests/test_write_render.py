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
    for name in ("post.html", "preview.html", "meta.json"):
        assert (out / name).exists()
    html = (out / "post.html").read_text(encoding="utf-8")
    preview = (out / "preview.html").read_text(encoding="utf-8")
    assert "[이미지 삽입]" in html and "<img" not in html
    assert '<img src="charts/index_change.png"' in preview
    assert "투자를 권유하지" in html or "권유하지 않습니다" in html
    assert "발행 전 확인" in preview and "발행 전 확인" not in html
    # 데이터로 만든 요약 상자·표와 새 섹션
    for text in ("오늘 시장 한눈에", "<table", "코스피", "한국 증시 체크포인트", "마무리", "[함께 보면 좋은 글]", "#미국증시"):
        assert text in html, text
    assert html.index("오늘 시장 한눈에") < html.index("해외 시장") < html.index("국내 시장")
    assert post.draft.content.title.startswith("[템플릿 초안] 미국증시·코스피 시황 | 11월 6일(금)")

    msg = build_message(post, "me@example.com", "me@example.com")
    html_body = next(p.get_content() for p in msg.walk() if p.get_content_type() == "text/html" and not p.get_filename())
    assert 'src="cid:index_change"' in html_body
    attachments = {p.get_filename() for p in msg.iter_attachments()}
    assert {"post.html", "index_change.png"} <= attachments
    assert any(p.get("Content-ID") == "<index_change>" for p in msg.walk())


def test_ai_phrase_guard_counts_over_limit():
    from econblog.guard.style import find_ai_phrases

    content = _content("상승한 것으로 보입니다. 하락한 것으로 보입니다. 이른바 블루웨이브입니다.")
    warnings = find_ai_phrases(content, {"로 보입니다": 1, "이른바": 0, "결국": 1})
    assert len(warnings) == 1
    assert "「로 보입니다」 2회" in warnings[0] and "「이른바」 1회" in warnings[0] and "결국" not in warnings[0]
