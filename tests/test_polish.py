from econblog.guard.style import find_ai_phrases
from econblog.models import Issue, PostContent, SentenceFix
from econblog.write.polish import apply_fixes, find_targets, polish

LIMITS = {"정리하면": 0, "찬물": 0, "수 있습니다": 1}


def _post(closing, market) -> PostContent:
    return PostContent(title="코스피는 왜 올랐을까? | 11월 11일(수) 미국증시·코스피 시황", lead="도입", summary_line="한 줄",
                       global_market=market, korea_market=["국내"], korea_checkpoints=["체크"],
                       issues=[Issue(title="이슈", paragraphs=["분석"], reference_urls=["https://example.com/a"])],
                       watch_points=["CPI"], closing=closing, tags=["코스피"])


POST = _post("정리하면 코스피 4.39% 급등은 CPI 전의 반등이었습니다. 오늘 장에서는 외국인 매매부터 봅니다.",
             ["나스닥이 0.74% 내렸습니다. 기술주가 더 밀릴 수 있습니다.",
              "금리가 더 오를 수 있습니다. 물가 지표가 분위기에 찬물을 끼얹었습니다."])


def test_targets_are_only_sentences_over_the_limit():
    targets = find_targets(POST, LIMITS)
    # '수 있습니다'는 1번까지 허용이라 첫 문장은 남기고 두 번째만 고친다
    assert [t.sentence for t in targets] == [
        "금리가 더 오를 수 있습니다.",
        "물가 지표가 분위기에 찬물을 끼얹었습니다.",
        "정리하면 코스피 4.39% 급등은 CPI 전의 반등이었습니다.",
    ]
    assert targets[2].phrases == ["정리하면"] and "오늘 장에서는" in targets[2].paragraph
    assert find_targets(_post("맺음", ["평범한 문장입니다."]), LIMITS) == []


def test_fixes_replace_only_those_sentences():
    targets = find_targets(POST, LIMITS)
    fixes = [SentenceFix(number=1, text="금리는 더 오를 가능성이 큽니다."),
             SentenceFix(number=2, text="물가 지표가 나온 뒤 나스닥이 하락으로 돌아섰습니다."),
             SentenceFix(number=3, text="코스피 4.39% 급등은 CPI가 나오기 전의 반등이었습니다.")]
    fixed, count = apply_fixes(POST, targets, fixes, LIMITS)
    assert count == 3 and find_ai_phrases(fixed, LIMITS) == []
    assert fixed.closing == "코스피 4.39% 급등은 CPI가 나오기 전의 반등이었습니다. 오늘 장에서는 외국인 매매부터 봅니다."
    assert fixed.global_market[0] == POST.global_market[0] and fixed.title == POST.title
    assert fixed.issues == POST.issues and fixed.tags == POST.tags


def test_bad_fixes_are_dropped():
    targets = find_targets(POST, LIMITS)
    fixes = [SentenceFix(number=2, text="물가 지표가 분위기에 다시 찬물을 부었습니다."),   # 금지 표현이 또 있음
             SentenceFix(number=3, text="코스피 4.4% 급등은 CPI 전의 반등이었습니다."),     # 숫자가 바뀜
             SentenceFix(number=9, text="없는 번호")]
    fixed, count = apply_fixes(POST, targets, fixes, LIMITS)
    assert count == 0 and fixed == POST


def test_offline_keeps_the_draft(settings):
    assert polish(settings, POST, offline=True) is POST
