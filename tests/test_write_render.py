from datetime import date

from conftest import make_article

from econblog.deliver.email import build_message
from econblog.guard.copyright import find_copied_passages
from econblog.models import Issue, PostContent
from econblog.pipeline import run


def _content(paragraph: str) -> PostContent:
    return PostContent(
        title="11월 7일 시황", lead="요약", global_market=[paragraph], korea_market=["국내"],
        issues=[Issue(title="이슈", paragraphs=["분석"], reference_urls=["https://example.com/a"])],
        watch_points=["FOMC"], tags=["경제"],
    )


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

    msg = build_message(post, "me@example.com", "me@example.com")
    html_body = next(p.get_content() for p in msg.walk() if p.get_content_type() == "text/html" and not p.get_filename())
    assert 'src="cid:index_change"' in html_body
    attachments = {p.get_filename() for p in msg.iter_attachments()}
    assert {"post.html", "index_change.png"} <= attachments
    assert any(p.get("Content-ID") == "<index_change>" for p in msg.walk())
