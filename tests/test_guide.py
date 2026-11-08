import re
from datetime import date

from econblog.deliver.email import build_message
from econblog.pipeline import find_topic, pick_topic, run_guide


def test_guides_yaml_refers_to_known_series_and_unique_ids(settings):
    keys = {s.key for s in settings.series}
    ids = [t.id for t in settings.guides]
    assert len(ids) == len(set(ids)) and len(ids) >= 10
    for t in settings.guides:
        assert set(t.series) <= keys, (t.id, set(t.series) - keys)
        for c in t.charts:
            assert set(c.series) <= keys, (t.id, c.key)


def test_pick_topic_moves_on_each_scheduled_day(settings):
    g = settings.guide
    g.start_date, g.weekdays, g.start_index = date(2026, 11, 11), [2, 5], 0  # 수·토
    first, second, third = settings.guides[:3]
    assert pick_topic(settings, date(2026, 11, 11)).id == first.id     # 수
    assert pick_topic(settings, date(2026, 11, 14)).id == second.id    # 토
    assert pick_topic(settings, date(2026, 11, 18)).id == third.id     # 다음 수
    assert pick_topic(settings, date(2026, 11, 12)) is None            # 목: 실행일 아님
    assert pick_topic(settings, date(2026, 11, 7)) is None             # 시작 전
    g.start_index = 2  # 수동으로 두 편을 먼저 만든 경우
    assert pick_topic(settings, date(2026, 11, 11)).id == third.id


def test_guide_dry_run_end_to_end(settings):
    topic = find_topic(settings, "yield_curve")
    post = run_guide(settings, topic, run_date=date(2026, 11, 6), offline=True, deliver_methods=["local"])
    out = post.output_dir
    assert out.name == "2026-11-06-guide-yield_curve"
    assert (out / "charts" / "thumb_study.jpg").exists()  # 경제 공부 고정 썸네일
    assert not (out / "charts" / "yield_curve_cover.png").exists()
    assert (out / "charts" / "yield_curve_spread.png").exists()

    html = (out / "post.html").read_text(encoding="utf-8")
    # 참고 글 구성: 인사 도입 → 제목 소제목 + 대표 이미지 → 질문형 소제목(표) → 지금 수치 → 흔히 하는 오해 → 정리하면 → 끝
    order = ["흔히 하는 오해도", "<h2", "[이미지 삽입] thumb_study.jpg", "장단기 금리차란?", "<table",
             "지금 수치로 보면?", "최근 5년 범위", "미 국채 10년", "흔히 하는 오해</h3>", "① ", "정리하면",
             "※ 이 글은", "■ 최근에 올라온 글", "키워드: 장단기 금리차"]
    pos = [html.index(t) for t in order]
    assert pos == sorted(pos), order
    assert "#장단기금리차" not in html and "마무리" not in html

    # 네이버판: 제목·확인 상자 없이 본문만, 이미지는 [사진] 안내, 티스토리 글 링크 없음
    naver = (out / "naver.html").read_text(encoding="utf-8")
    assert "[사진] thumb_study.jpg" in naver and "<img" not in naver
    assert "발행 전 확인" not in naver and "<h1" not in naver and "최근에 올라온 글" not in naver
    assert "흔히 하는 오해" in naver and "※ 이 글은" in naver and "<table" in naver
    # 티스토리 기본 편집기가 지우는 스타일·태그를 쓰지 않는다
    assert "<th" not in html
    kept = {"color", "background-color", "text-align", "border-collapse", "width", "list-style-type"}
    used = {prop.strip() for style in re.findall(r'(?<![-\w])style="([^"]*)"', html)
            for prop in (d.split(":")[0] for d in style.split(";")) if prop.strip()}
    assert used <= kept, used - kept

    msg = build_message(post, "me@example.com", "me@example.com")
    assert msg["Subject"].startswith("[블로그 초안·경제 공부]")
    types = {p.get_filename(): p.get_content_type() for p in msg.iter_attachments()}
    assert types["thumb_study.jpg"] == "image/jpeg" and types["yield_curve_spread.png"] == "image/png"
    assert types["naver.html"] == "text/html"


def test_guide_without_thumbnail_draws_keyword_cover(settings):
    settings.thumbnails = {}
    post = run_guide(settings, find_topic(settings, "vix"), run_date=date(2026, 11, 6), offline=True,
                     deliver_methods=["local"])
    html = (post.output_dir / "post.html").read_text(encoding="utf-8")
    assert html.index("[이미지 삽입] vix_cover.png") < html.index("<h3")


def test_recent_posts_from_blog_rss_skip_current_title():
    from econblog.render.recent import parse_recent

    rss = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>그냥모아</title>
    <item><title>오늘 글</title><link>https://seolu.tistory.com/30</link></item>
    <item><title>어제 글</title><link>https://seolu.tistory.com/29</link></item>
    <item><title>그제 글</title><link>https://seolu.tistory.com/28</link></item>
    <item><title>미국증시&amp;middot;코스피 시황</title><link>https://seolu.tistory.com/27</link></item>
    </channel></rss>""".encode()
    recent = parse_recent(rss, 2, exclude_title="오늘 글")
    assert [(r.title, r.url) for r in recent] == [("어제 글", "https://seolu.tistory.com/29"),
                                                  ("그제 글", "https://seolu.tistory.com/28")]
    assert parse_recent(rss, 4)[-1].title == "미국증시·코스피 시황"


def test_recent_posts_are_linked_at_the_end(settings, tmp_path):
    from econblog.models import RecentPost
    from econblog.render.html import render_guide

    post = run_guide(settings, find_topic(settings, "yield_curve"), run_date=date(2026, 11, 6), offline=True,
                     deliver_methods=[])
    recent = [RecentPost(title="어제 글", url="https://seolu.tistory.com/29")]
    again = render_guide(settings, post.draft, tmp_path, recent=recent)
    assert '■ 최근에 올라온 글</b><br>· <a href="https://seolu.tistory.com/29">어제 글</a>' in again.html
    assert "seolu.tistory.com/29" not in again.naver_html
