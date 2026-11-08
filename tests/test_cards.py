from datetime import date

import pytest

from econblog.deliver import cards as card_deliver
from econblog.market import build_snapshot, moves
from econblog.models import CardCheck, CardCopy, CardEvent, CardSet, CardStory, Series, SeriesSpec
from econblog.pipeline import run
from econblog.render import cards as card_render
from econblog.render.photos import PhotoPicker
from econblog.write.prompting import user_prompt
from econblog.write.base import WriteContext


def _series(key, unit, values, category="index_global", label="이름", label_en="Name", sid="X"):
    spec = SeriesSpec(key=key, label=label, label_en=label_en, provider="yahoo", id=sid, unit=unit, category=category)
    return Series(spec=spec, dates=[date(2026, 11, 5), date(2026, 11, 6)], values=values)


def test_value_and_change_text_follow_each_language():
    rate = _series("us10y", "%", [4.838, 4.86], category="rates")
    assert moves.value_text(rate, "ko") == "4.86%"
    assert moves.change_text(rate, "ko") == ("▲ 0.02%p", "up")
    assert moves.change_text(rate, "en") == ("▲ 2.2 bp", "up")

    gold = _series("gold", "달러", [4113.6, 4074.9], category="commodity")
    assert moves.value_text(gold, "ko") == "4,074.90달러"
    assert moves.value_text(gold, "en") == "$4,074.90"
    assert moves.change_text(gold, "en")[1] == "down"

    hynix = _series("st_hynix", "원", [1264000, 1132000], category="kr_stock")
    assert moves.value_text(hynix, "en") == "₩1,132,000"
    assert moves.value_text(hynix, "ko") == "1,132,000원"
    assert moves.signed_pct(hynix) == "−10.44%"


def _copy(lang="ko"):
    story = CardStory(headline=["반도체가", "흔들렸다"], paragraphs=["코스피는 **6.02%** 내렸습니다.", "닛케이도 빠졌습니다."],
                      why="두 종목이 지수 방향을 정합니다.", photo_query="semiconductor chip")
    return CardCopy(cover_lines=["코스피 6% 급락,", "나스닥은 1% 올랐다"], cover_photo_query="seoul skyline",
                    board_note="아시아는 급락, 미국은 기술주 강세", stories=[story, story],
                    sector_title="기술주만 웃었다", movers_title="AMD 11% 급등", asia_note="",
                    events=[CardEvent(when="11/12(수)", title="미국 CPI", detail="금리 기대를 바꿀 지표", tag="지표")],
                    checklist=[CardCheck(key="usdkrw", title="원/달러 환율 1,360원", detail="다시 1,360원 위로 올라가는지"),
                               CardCheck(key="kospi", title="코스피 5,000선", detail="5,000선 아래로 내려가는지"),
                               CardCheck(key="없는키", title="SK하이닉스", detail="미국 반도체 반등을 따라가는지")],
                    caption="11월 7일(토) 아침 시황 | 코스피 급락",
                    hashtags=["미국증시", "코스피", "반도체"])


def test_slides_follow_account_order_and_use_data_numbers(settings):
    snap = build_snapshot(settings, date(2026, 11, 7), offline=True)
    kr = next(a for a in settings.instagram.accounts if a.key == "kr")
    slides = card_render.build_slides(kr, _copy(), snap, date(2026, 11, 7))
    assert [s.kind for s in slides] == ["cover", "board", "story", "story", "sectors", "movers", "events", "closing"]
    assert slides[0].page == "1/8" and slides[-1].page == "8/8"
    assert len(slides[1].tiles) == 10 and len(slides[4].cells) == 11 and len(slides[5].rows) == 12
    assert slides[0].kicker == "11월 7일(토) 아침 시황"
    close = slides[-1]
    assert close.kicker == "월요일 체크리스트" and close.title == "장 열리면 볼 3가지"
    assert close.events[0].when.startswith("금요일 ") and "원" in close.events[0].when   # 수치는 데이터에서 붙는다
    assert close.events[2].when == ""   # 데이터에 없는 key 는 숫자를 붙이지 않는다

    pages = card_render.render_html(settings, kr, slides)
    assert "오늘 시장 한눈에" in pages[1] and "<strong>6.02%</strong>" in pages[2]
    for page in pages:   # 사용자가 빼 달라고 한 권유 문구는 카드에 없다
        assert "저장" not in page and "프로필 링크" not in page

    en = next(a for a in settings.instagram.accounts if a.key == "en")
    copy = _copy().model_copy(update={"events": []})
    en_slides = card_render.build_slides(en, copy, snap, date(2026, 11, 7))
    assert "events" not in [s.kind for s in en_slides]          # 일정이 없으면 그 장은 빠진다
    assert en_slides[0].kicker == "MARKET WRAP · FRI, NOV 6"
    check = next(s for s in en_slides if s.kind == "check")
    assert [t.n for t in check.tiles] == ["KOSPI", "Nikkei 225", "SK hynix", "Samsung Electronics", "USD/KRW"]


@pytest.mark.skipif(card_render.chrome_path() is None, reason="Chrome 없음")
def test_card_renders_to_jpeg(settings, tmp_path):
    settings.instagram.render_images = True
    snap = build_snapshot(settings, date(2026, 11, 7), offline=True)
    kr = next(a for a in settings.instagram.accounts if a.key == "kr")
    slides = card_render.build_slides(kr, _copy(), snap, date(2026, 11, 7))[:1]
    images, warnings = card_render.render_cards(settings, kr, slides, tmp_path)
    from PIL import Image

    assert warnings == [] and Image.open(images[0]).size == (1080, 1350) and Image.open(images[0]).format == "JPEG"


def test_dry_run_makes_cards_for_both_accounts(settings):
    post = run(settings, run_date=date(2026, 11, 7), offline=True, deliver_methods=["local"])
    for key, brand in (("kr", "그냥모아"), ("en", "4PM RECAP")):
        out = post.output_dir / "insta" / key
        assert (out / "01.html").exists() and (out / "caption.txt").exists()
        assert brand in (out / "01.html").read_text(encoding="utf-8")
    caption = (post.output_dir / "insta" / "en" / "caption.txt").read_text(encoding="utf-8")
    assert "Not financial advice" not in caption and "Data: Yahoo Finance" in caption and "#stockmarket" in caption
    closing = sorted((post.output_dir / "insta" / "kr").glob("*.html"))[-1].read_text(encoding="utf-8")
    assert "투자 권유" not in closing   # instagram.disclaimer 가 꺼져 있으면 마지막 카드에도 없다


def test_blog_prompt_leaves_out_card_only_series(settings):
    snap = build_snapshot(settings, date(2026, 11, 7), offline=True)
    prompt = user_prompt(settings, WriteContext(date=date(2026, 11, 7), articles=[], snapshot=snap, charts=[]))
    assert "| 코스피 |" in prompt
    assert "마이크로소프트" not in prompt and "| 기술 |" not in prompt


def test_caption_fits_instagram_limits(tmp_path):
    copy = _copy().model_copy(update={"caption": "가" * 3000, "hashtags": [f"태그{i}" for i in range(40)]})
    cs = CardSet(account="kr", brand="그냥모아", lang="ko", date=date(2026, 11, 7), text=copy, output_dir=tmp_path)
    caption = card_deliver.full_caption(cs, photo_used=True)
    assert len(caption) <= 2200 and caption.count("#") == 30
    assert "사진: Pixabay" in caption and "투자 권유가 아닌" in caption
    assert "투자 권유" not in card_deliver.full_caption(cs, photo_used=True, disclaimer=False)


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code, self.text = body, status, str(body)

    def json(self):
        return self._body


def test_publish_instagram_builds_a_carousel(settings, monkeypatch):
    calls = []

    class FakeSession:
        def request(self, method, url, timeout, data=None, params=None):
            calls.append((method, url, data or params))
            if url.endswith("/media_publish"):
                return FakeResponse({"id": "POST1"})
            if method == "GET":
                return FakeResponse({"status_code": "FINISHED"})
            n = sum(1 for c in calls if c[0] == "POST")
            return FakeResponse({"id": f"C{n}"})

    monkeypatch.setattr(card_deliver.requests, "Session", FakeSession)
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "IGAAtest")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123")
    kr = next(a for a in settings.instagram.accounts if a.key == "kr")
    media = card_deliver.publish_instagram(settings, kr, ["https://x/1.jpg", "https://x/2.jpg"], "캡션")
    assert media == "POST1"
    posts = [c for c in calls if c[0] == "POST"]
    assert all(c[1].startswith("https://graph.instagram.com/") for c in calls)   # IG 토큰은 인스타 그래프
    assert posts[0][2]["is_carousel_item"] == "true" and posts[2][2]["media_type"] == "CAROUSEL"
    assert posts[2][2]["children"] == "C1,C2" and posts[3][2]["creation_id"] == "C3"


def test_publish_is_skipped_without_tokens(settings, tmp_path, monkeypatch):
    settings.instagram.publish = True
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    cs = CardSet(account="kr", brand="그냥모아", lang="ko", date=date(2026, 11, 7), text=_copy(), output_dir=tmp_path)
    assert card_deliver.deliver_cards(settings, [cs], ["local"]) == [f"카드 저장 {tmp_path}"]
    assert cs.media_id is None and (tmp_path / "caption.txt").exists()


def test_cards_email_has_inline_images_and_caption(tmp_path):
    img = tmp_path / "01.jpg"
    from PIL import Image

    Image.new("RGB", (10, 10)).save(img, "JPEG")
    cs = CardSet(account="kr", brand="그냥모아", lang="ko", date=date(2026, 11, 7), text=_copy(), images=[img],
                 caption="캡션 본문", output_dir=tmp_path)
    msg = card_deliver.build_cards_message([cs], "me@example.com", "me@example.com")
    assert msg["Subject"].startswith("[인스타 카드] 11/07 그냥모아 1장")
    html = msg.get_payload()[1]
    assert "cid:kr01" in html.get_payload()[0].get_content() and "캡션 본문" in html.get_payload()[0].get_content()


def test_photo_picker_downloads_and_never_repeats(settings, tmp_path, monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "k")

    class FakeSession:
        def get(self, url, timeout, params=None):
            if params:
                hits = [{"id": 9, "largeImageURL": "https://img/9.jpg", "tags": "wafer, chip, dessert"},   # 과자
                        {"id": 8, "largeImageURL": "https://img/8.jpg", "tags": "beach, sea"}]             # 상관없음
                hits += [{"id": i, "largeImageURL": f"https://img/{i}.jpg", "tags": "computer chip, circuit"} for i in (1, 2)]
                return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {"hits": hits}})()
            return type("R", (), {"raise_for_status": lambda s: None, "content": b"jpeg"})()

    picker = PhotoPicker(settings, tmp_path, seed="2026-11-07-kr")
    picker.session = FakeSession()
    a, b = picker.find("chip"), picker.find("chip")
    assert a != b and a.read_bytes() == b"jpeg" and picker.find("chip") is None
    assert PhotoPicker(settings, tmp_path, seed="x", offline=True).find("chip") is None


def test_check_account_reads_without_posting(settings, monkeypatch):
    calls = []

    class FakeSession:
        def request(self, method, url, timeout, data=None, params=None):
            calls.append(method)
            if url.endswith("content_publishing_limit"):
                return FakeResponse({"data": [{"quota_usage": 0}]})
            return FakeResponse({"username": "dailyjustmoa", "media_count": 0})

    monkeypatch.setattr(card_deliver.requests, "Session", FakeSession)
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "EAAtest")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "1784")
    kr = next(a for a in settings.instagram.accounts if a.key == "kr")
    ok, line = card_deliver.check_account(settings, kr)
    assert ok and "@dailyjustmoa" in line and "graph.facebook.com" in line and "EAAtest" not in line
    assert set(calls) == {"GET"}


def test_vague_phrases_are_flagged(settings):
    from econblog.guard.style import find_vague_phrases

    vague = _copy().model_copy(update={"board_note": "서울은 6% 빠졌고 월요일은 그 사이 어디쯤일 겁니다."})
    warning = find_vague_phrases(vague, settings.instagram.vague_phrases["ko"])
    assert warning and "서울은" in warning[0] and "어디쯤" in warning[0]
    clear = _copy().model_copy(update={"board_note": "코스피 6.02% 하락, 나스닥 1.09% 상승",
                                       "sector_title": "기술 업종 1.45% 상승"})
    assert find_vague_phrases(clear, settings.instagram.vague_phrases["ko"]) == []


def test_saved_cards_can_be_published_as_is(settings, tmp_path, monkeypatch):
    from PIL import Image

    cs = CardSet(account="kr", brand="그냥모아", lang="ko", date=date(2026, 11, 7), text=_copy(),
                 caption="확인한 캡션", output_dir=tmp_path)
    for i in (1, 2):
        Image.new("RGB", (10, 10)).save(tmp_path / f"0{i}.jpg", "JPEG")
    card_deliver.save_local(cs)
    loaded = card_deliver.load_saved(tmp_path)
    assert [p.name for p in loaded.images] == ["01.jpg", "02.jpg"] and loaded.caption == "확인한 캡션"

    sent = {}
    monkeypatch.setattr(card_deliver, "_publish", lambda s, a, c: sent.update(caption=c.caption, n=len(c.images)) or "M1")
    assert card_deliver.publish_saved(settings, tmp_path).media_id == "M1"
    assert sent == {"caption": "확인한 캡션", "n": 2}


def test_numbers_not_in_data_are_flagged(settings):
    from econblog.guard.numbers import find_unverified_numbers

    snap = build_snapshot(settings, date(2026, 11, 7), offline=True)
    kospi = snap.series["kospi"]
    ok_text = f"코스피 {abs(kospi.change_pct):.2f}% 하락, {kospi.last:,.2f}로 마감했습니다."
    plain = CardStory(headline=["반도체가", "흔들렸다"], paragraphs=[ok_text, "닛케이도 빠졌습니다."], why="지수 방향을 정합니다.",
                      photo_query="server room")
    good = _copy().model_copy(update={"board_note": ok_text, "stories": [plain, plain],
                                      "caption": "코스피 5,000선을 지키는지 봅니다. 11월 13일 발표."})
    assert find_unverified_numbers(good, snap) == []
    bad = _copy().model_copy(update={"board_note": "기름값이 14.8% 뛰었고 환율은 1,320원대에서 올랐습니다."})
    warning = find_unverified_numbers(bad, snap)
    assert warning and "14.8" in warning[0] and "1,320" in warning[0]


def test_cards_with_warnings_are_not_auto_posted(settings, tmp_path, monkeypatch):
    settings.instagram.publish = True
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "IGAAtest")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "1")
    monkeypatch.setattr(card_deliver, "_publish", lambda *a: pytest.fail("경고가 있으면 게시하면 안 됨"))
    cs = CardSet(account="kr", brand="그냥모아", lang="ko", date=date(2026, 11, 7), text=_copy(),
                 warnings=["데이터에 없는 숫자: 14.8"], output_dir=tmp_path)
    card_deliver.deliver_cards(settings, [cs], ["local"])
    assert cs.media_id is None and "자동 게시하지 않았습니다" in cs.warnings[-1]


def test_index_names_are_not_counted_as_numbers(settings):
    from econblog.guard.numbers import find_unverified_numbers

    snap = build_snapshot(settings, date(2026, 11, 7), offline=True)
    text = _copy().model_copy(update={"stories": [], "board_note": "닛케이225와 S&P 500, Nikkei 225 모두 움직였습니다."})
    assert find_unverified_numbers(text, snap) == []


def test_claude_card_writer_runs_a_review_pass(settings, monkeypatch):
    from econblog.write import cards as card_write
    from econblog.write.base import CardContext

    calls = []

    def fake_call(client, s, system, user, fmt):
        calls.append((system, user))
        return _copy() if len(calls) == 1 else _copy().model_copy(update={"board_note": "교열본"})

    monkeypatch.setattr("econblog.write.claude.make_client", lambda: object())
    monkeypatch.setattr("econblog.write.claude.structured_call", fake_call)
    snap = build_snapshot(settings, date(2026, 11, 7), offline=True)
    kr = next(a for a in settings.instagram.accounts if a.key == "kr")
    out = card_write.ClaudeCardWriter(settings).write(CardContext(date=date(2026, 11, 7), account=kr, articles=[], snapshot=snap))
    assert out.board_note == "교열본" and len(calls) == 2
    assert "교열 담당" in calls[1][0] and "검토할 초안" in calls[1][1]


def test_apply_edits_changes_only_matching_text(tmp_path):
    (tmp_path / "03.html").write_text("<p>반도체 레버리지 상품 손실이 커지면서</p>", encoding="utf-8")
    (tmp_path / "04.html").write_text("<p>그대로</p>", encoding="utf-8")
    (tmp_path / "caption.txt").write_text("자동차 관세보다 이 AI 수요 문제가", encoding="utf-8")
    (tmp_path / "meta.json").write_text("{}", encoding="utf-8")
    changed = card_deliver.apply_edits(tmp_path, [["반도체 레버리지 상품 손실이 커지면서", "AI 서버 수요가 흔들리면"],
                                                  ["자동차 관세보다 ", ""]])
    assert [p.name for p in changed] == ["03.html"]
    assert "AI 서버 수요가 흔들리면" in (tmp_path / "03.html").read_text(encoding="utf-8")
    assert (tmp_path / "caption.txt").read_text(encoding="utf-8") == "이 AI 수요 문제가"
    with pytest.raises(ValueError):
        card_deliver.apply_edits(tmp_path, [["없는 문장", "x"]])


def _example_set(tmp_path, n=8):
    """실제로 올린 카드 묶음처럼 생긴 예시 폴더 (meta.json + 01~08.jpg)."""
    from PIL import Image

    d = tmp_path / "examples" / "2026-11-08" / "insta" / "kr"
    d.mkdir(parents=True)
    for i in range(1, n + 1):
        Image.new("RGB", (10, 10)).save(d / f"{i:02d}.jpg", "JPEG")
    card_deliver.save_local(CardSet(account="kr", brand="그냥모아", lang="ko", date=date(2026, 11, 8), text=_copy(),
                                    caption="원래 캡션", output_dir=d))
    return d


def test_intro_slides_follow_config_and_show_example_cards(settings, tmp_path):
    from econblog.config import load_intro

    intro = load_intro(settings, "kr")
    examples = sorted(_example_set(tmp_path).glob("*.jpg"))
    slides = card_render.build_intro_slides(intro, examples, date(2026, 11, 8))
    assert slides[0].kind == "intro-cover" and {s.kind for s in slides[1:]} <= {"intro-text", "intro-shots", "intro-end"}
    assert slides[0].page == f"1/{len(slides)}"
    shots = [s for s in slides if s.kind == "intro-shots"]
    assert shots and all(x.startswith("file:") for s in shots for x in s.shots)
    assert shots[0].note == "예시 · 11월 8일에 올린 카드"
    html = card_render.render_html(settings, next(a for a in settings.instagram.accounts if a.key == "kr"), slides)
    assert '<img src="file:' in html[0] and '<img src="file:' in html[2]
    with pytest.raises(ValueError):
        card_render.build_intro_slides(intro, examples[:2], None)   # 예시 카드가 모자라면 멈춘다


def test_glue_keeps_short_words_and_dotted_lists_together():
    out = card_render._glue("칩 세 개는 코스피·나스닥 안 써요")
    assert "세\u00a0개" in out and "안\u00a0써요" in out and "코스피\u2060·\u2060나스닥" in out


def test_intro_is_saved_for_insta_post_and_never_auto_posted(settings, tmp_path, monkeypatch):
    from econblog.pipeline import run_intro

    settings.instagram.publish = True
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "IGAAtest")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "1")
    monkeypatch.setattr(card_deliver, "_publish", lambda *a: pytest.fail("소개 게시물은 자동 게시하면 안 됨"))
    cs = run_intro(settings, "kr", _example_set(tmp_path), run_date=date(2026, 11, 8))
    assert cs.output_dir.parent.parent.name == "2026-11-08-intro" and cs.media_id is None
    loaded = card_deliver.load_saved(cs.output_dir)
    assert "11월 8일에 올린 카드" in loaded.caption and "{example_date}" not in loaded.caption
    assert "투자 권유" not in loaded.caption and "사진: Pixabay" in loaded.caption and "#그냥모아" in loaded.caption
    assert len(list((cs.output_dir / "examples").glob("*.jpg"))) == 8   # 다시 찍을 때 쓸 예시 그림


def test_upload_path_keeps_same_day_sets_apart(settings, tmp_path, monkeypatch):
    sent = {}
    monkeypatch.setattr(card_deliver.publish, "is_configured", lambda s: True)
    monkeypatch.setattr(card_deliver.publish, "publish_files", lambda s, files, msg: sent.setdefault("paths", [p for _, p in files]) or [])
    monkeypatch.setattr(card_deliver.publish, "wait_until_public", lambda urls: True)
    monkeypatch.setattr(card_deliver, "publish_instagram", lambda *a: "M1")
    d = tmp_path / "2026-11-08-intro" / "insta" / "kr"
    d.mkdir(parents=True)
    cs = CardSet(account="kr", brand="그냥모아", lang="ko", date=date(2026, 11, 8), text=_copy(),
                 images=[d / "01.jpg"], output_dir=d)
    kr = next(a for a in settings.instagram.accounts if a.key == "kr")
    card_deliver._publish(settings, kr, cs)
    assert sent["paths"] == ["2026-11-08-intro/insta/kr/01.jpg"]


def test_monday_cards_are_not_auto_posted(settings, tmp_path, monkeypatch):
    # 월요일 아침엔 토요일 이후 새 장이 없어 같은 숫자가 두 번 올라간다
    settings.instagram.publish = True
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "IGAAtest")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "1")
    posted = []
    monkeypatch.setattr(card_deliver, "_publish", lambda s, a, cs: posted.append(cs.date) or "M1")
    for day in (date(2026, 11, 9), date(2026, 11, 10)):   # 월, 화
        cs = CardSet(account="kr", brand="그냥모아", lang="ko", date=day, text=_copy(), output_dir=tmp_path / str(day))
        card_deliver.deliver_cards(settings, [cs], ["local"])
    assert posted == [date(2026, 11, 10)]


def test_allegations_about_people_are_flagged(settings):
    from econblog.guard.style import find_vague_phrases

    text = _copy("en").model_copy(update={"events": [CardEvent(when="This week", title="Nvidia AI Day",
                                                              detail="Follow-up on the Jensen Huang allegations", tag="Tech")]})
    warning = find_vague_phrases(text, settings.instagram.sensitive_phrases["en"], label="개인 의혹·소문 표현")
    assert warning and "allegation" in warning[0]
    assert find_vague_phrases(_copy(), settings.instagram.sensitive_phrases["ko"]) == []
