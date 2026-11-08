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
    for text in ("이 글의 핵심", "지금 수치로 보기", "최근 5년 범위", "미 국채 10년", "자주 묻는 질문", "마무리",
                 "[함께 보면 좋은 글]", "#장단기금리차"):
        assert text in html, text
    assert html.index("[이미지 삽입] thumb_study.jpg") < html.index("이 글의 핵심")
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


def test_guide_without_thumbnail_draws_keyword_cover(settings):
    settings.thumbnails = {}
    post = run_guide(settings, find_topic(settings, "vix"), run_date=date(2026, 11, 6), offline=True,
                     deliver_methods=["local"])
    html = (post.output_dir / "post.html").read_text(encoding="utf-8")
    assert html.index("[이미지 삽입] vix_cover.png") < html.index("이 글의 핵심")
