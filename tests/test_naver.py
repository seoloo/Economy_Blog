from datetime import date

from econblog.deliver.email import build_naver_message, build_naver_message_from_dir
from econblog.models import Issue, PostContent
from econblog.pipeline import run
from econblog.render.html import render_post
from econblog.write.naver import check_naver, rewrite_for_naver


def _post(title, para, tags=("코스피",)) -> PostContent:
    return PostContent(title=title, lead="도입", summary_line="한 줄", global_market=[para], korea_market=["국내"],
                       korea_checkpoints=["체크"], issues=[Issue(title="이슈", paragraphs=["분석"], reference_urls=[])],
                       watch_points=["CPI"], closing="정리", tags=list(tags))


ORIG = _post("시황 | 11월 10일(화) | 미국 반등, 코스피도 따라갈까?",
             "나스닥이 2.74% 오르며 반도체가 반등을 이끌었고 엔비디아만 4.27% 내렸습니다.")


def test_naver_check_flags_new_numbers_and_copied_sentences():
    same = _post("시황 | 11월 10일(화) | 반도체 반등은 이어질까?", ORIG.global_market[0])
    assert any("40자 넘게 같음" in w for w in check_naver(ORIG, same))
    new_num = _post("시황 | 11월 10일(화) | 반도체 반등은 이어질까?", "반도체가 끌어올린 하루, 나스닥 2.74%·S&P 3.1%")
    assert any("원본에 없는 숫자: 3.1" in w for w in check_naver(ORIG, new_num))
    good = _post("시황 | 11월 10일(화) | 반도체 반등은 이어질까?",
                 "반도체 덕에 나스닥은 2.74% 뛰었죠. 다만 엔비디아는 혼자 4.27% 밀렸습니다.")
    assert check_naver(ORIG, good) == []


def test_offline_keeps_one_version(settings):
    assert rewrite_for_naver(settings, ORIG, offline=True) == (None, [])


def test_naver_html_uses_rewritten_post_and_email_shows_both_titles(settings, tmp_path):
    post = run(settings, run_date=date(2026, 11, 6), offline=True, deliver_methods=[])
    naver = post.draft.content.model_copy(update={"title": "네이버판 제목 | 반도체 반등은 이어질까?",
                                                  "tags": ["반도체", "나스닥"]})
    draft = post.draft.model_copy(update={"naver": naver})
    out = render_post(settings, draft, tmp_path)
    assert "네이버판 제목" in out.naver_html and "네이버판 제목" not in out.html
    assert "네이버 제목" in out.preview_html and "반도체, 나스닥" in out.preview_html
    assert "티스토리 제목" in out.preview_html

    # 네이버용은 따로 한 통: 제목이 네이버판 제목이고, 본문이 곧 붙여넣을 글이다
    msg = build_naver_message(out, "me@example.com", "me@example.com")
    assert msg["Subject"].startswith("[네이버 블로그 초안] 11/06 네이버판 제목")
    body = msg.get_body(preferencelist=("html",)).get_content()
    assert "네이버 블로그용 글입니다" in body and "반도체, 나스닥" in body and "티스토리판과 같은 글입니다" not in body
    assert "naver.html" in [a.get_filename() for a in msg.iter_attachments()]
    # 다시 쓴 글이 없으면 같은 글이라는 안내가 붙는다
    plain = build_naver_message(render_post(settings, post.draft, tmp_path), "me@example.com", "me@example.com")
    assert "티스토리판과 같은 글입니다" in plain.get_body(preferencelist=("html",)).get_content()


def test_check_naver_ignores_rank_words():
    from econblog.write.naver import NUM
    assert NUM.findall("상승률 1위는 2.74% 오른 나스닥, 2번째는 다우. 코스피 5,268.") == ["2.74", "5,268"]


def test_naver_mail_can_be_rebuilt_from_saved_draft(settings):
    post = run(settings, run_date=date(2026, 11, 6), offline=True, deliver_methods=["local"])
    msg = build_naver_message_from_dir(post.output_dir, "me@example.com", "me@example.com")
    assert msg["Subject"].startswith("[네이버 블로그 초안] 11/06 ")
    body = msg.get_body(preferencelist=("html",)).get_content()
    assert "네이버 블로그용 글입니다" in body and "오늘 시장 한눈에" in body
    names = [a.get_filename() for a in msg.iter_attachments()]
    assert "naver.html" in names and "thumb_market.jpg" in names
