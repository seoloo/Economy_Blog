from datetime import date

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


def test_check_naver_ignores_rank_words():
    from econblog.write.naver import NUM
    assert NUM.findall("상승률 1위는 2.74% 오른 나스닥, 2번째는 다우. 코스피 5,268.") == ["2.74", "5,268"]
