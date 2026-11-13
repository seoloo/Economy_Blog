"""단계 조립만 담당한다. 각 단계의 세부 로직은 해당 패키지에 둔다."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from econblog.charts import build_charts
from econblog.charts.cover import fixed_thumbnail, guide_cover
from econblog.charts.publish import publish_charts
from econblog.classify import classify_and_select
from econblog.collect import collect_all
from econblog.config import Settings
from econblog.deliver import deliver_all
from econblog.deliver.cards import deliver_cards, full_caption
from econblog.guard.copyright import find_copied_passages
from econblog.guard.freshness import find_stale_series
from econblog.guard.numbers import find_unverified_numbers
from econblog.guard.style import find_ai_phrases, find_vague_phrases
from econblog.market import build_snapshot
from econblog.models import CardSet, ClassifiedArticle, Draft, GuideDraft, GuideTopic, MarketSnapshot, PostContent, RenderedPost
from econblog.render.cards import build_slides, render_cards
from econblog.render.reels import build_reel
from econblog.render.photos import PhotoPicker
from econblog.render.html import render_guide, render_post
from econblog.render.recent import fetch_recent
from econblog.write import write_post
from econblog.write.base import CardContext, GuideContext, WriteContext
from econblog.write.cards import write_cards
from econblog.write.guide import write_guide
from econblog.write.naver import rewrite_for_naver
from econblog.write.polish import polish
from econblog.write.prompting import guide_rows

log = logging.getLogger(__name__)


def today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def run(
    settings: Settings,
    run_date: date | None = None,
    offline: bool = False,
    deliver_methods: list[str] | None = None,
    card_methods: list[str] | None = None,
) -> RenderedPost:
    """시황 글 초안을 만들어 전달하고, 인스타 카드도 만든다. card_methods 를 따로 주면 카드만 그 방식으로 보낸다."""
    run_date = run_date or today(settings)
    out_dir = settings.resolve_output_dir() / run_date.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("=== %s 실행 (offline=%s) → %s", run_date, offline, out_dir)

    # 1. 수집
    since = datetime.now(timezone.utc) - timedelta(hours=settings.collect.lookback_hours)
    articles = collect_all(settings, since, offline=offline)
    log.info("수집 합계 %d건", len(articles))

    # 2. 분류·선별
    selected = classify_and_select(settings, articles, offline=offline)
    log.info("선별 %d건", len(selected))

    # 3. 시장 데이터
    snapshot = build_snapshot(settings, run_date, offline=offline)
    log.info("시장 데이터 %d개 (실패 %d개)", len(snapshot.series), len(snapshot.errors))

    # 4. 차트 (시황 고정 썸네일이 있으면 데이터 표지 대신 맨 위에 넣는다)
    thumb = fixed_thumbnail(settings, "daily", out_dir / "charts")
    specs = [s for s in settings.charts if not (thumb and s.position == "cover")]
    charts = ([thumb] if thumb else []) + build_charts(settings, snapshot, out_dir / "charts", specs)
    log.info("차트 %d개", len(charts))
    publish_warnings = publish_charts(settings, charts, run_date, offline=offline)

    # 5. 초안
    body_charts = [c for c in charts if c.position != "cover"]
    ctx = WriteContext(date=run_date, articles=selected, snapshot=snapshot, charts=body_charts)
    content, warnings = write_post(settings, ctx, offline=offline)
    content = polish(settings, content, offline=offline)   # 말투 검사에 걸린 문장만 다시 쓴다

    # 6. 저작권 검사
    references = [c.article for c in selected]
    warnings += find_copied_passages(content, references, settings.guard.max_shared_chars)
    warnings += find_ai_phrases(content, settings.guard.ai_phrases)
    warnings += publish_warnings
    warnings += find_stale_series(snapshot)
    if snapshot.errors:
        warnings.append("데이터 수집 실패: " + ", ".join(sorted(snapshot.errors)))
    naver, naver_warnings = _naver_version(settings, content, references, offline)
    warnings += naver_warnings

    # 7. 렌더링·전달
    draft = Draft(date=run_date, content=content, naver=naver, charts=charts, quotes=snapshot.quotes(),
                  references=references, warnings=warnings)
    post = render_post(settings, draft, out_dir, recent=fetch_recent(settings, offline, content.title))
    for line in deliver_all(settings, post, deliver_methods):
        log.info("전달: %s", line)
    if warnings:
        log.warning("검토 필요 %d건: %s", len(warnings), " | ".join(warnings))

    # 8. 인스타 카드뉴스 (실패해도 블로그 초안은 이미 나갔으므로 경고만 남긴다)
    if settings.instagram.enabled and settings.instagram.active_accounts:
        try:
            methods = card_methods or (deliver_methods if deliver_methods is not None else settings.deliver.methods)
            run_cards(settings, run_date, snapshot, selected, content, out_dir, offline, methods)
        except Exception as e:  # noqa: BLE001
            log.warning("인스타 카드 실패: %s", e)
    return post


def _naver_version(settings: Settings, content, references, offline: bool):
    """네이버판을 다시 쓰고, 티스토리판과 같은 말투 고쳐 쓰기·검사(출처 문장·AI 말투)를 한 번 더 한다."""
    naver, warnings = rewrite_for_naver(settings, content, offline=offline)
    if naver is not None:
        naver = polish(settings, naver, offline=offline)
        warnings += ["[네이버판] " + w for w in find_copied_passages(naver, references, settings.guard.max_shared_chars)]
        warnings += ["[네이버판] " + w for w in find_ai_phrases(naver, settings.guard.ai_phrases)]
    return naver, warnings


# ---------------------------------------------------------------- 인스타 카드뉴스


def run_cards(
    settings: Settings,
    run_date: date,
    snapshot: MarketSnapshot,
    articles: list[ClassifiedArticle],
    post: PostContent | None,
    out_dir,
    offline: bool,
    methods: list[str],
) -> list[CardSet]:
    """계정마다 카드 글 작성 → 사진 → 카드 그리기, 그다음 한꺼번에 전달(게시·메일)."""
    references = [c.article for c in articles]
    cardsets: list[CardSet] = []
    for account in settings.instagram.active_accounts:
        card_dir = out_dir / "insta" / account.key
        ctx = CardContext(date=run_date, account=account, articles=articles, snapshot=snapshot, post=post)
        text, warnings = write_cards(settings, ctx, offline=offline)
        warnings += find_copied_passages(text, references, settings.guard.max_shared_chars)
        if account.lang == "ko":
            warnings += find_ai_phrases(text, settings.guard.ai_phrases)
        warnings += find_vague_phrases(text, settings.instagram.vague_phrases.get(account.lang, []))
        warnings += find_vague_phrases(text, settings.instagram.sensitive_phrases.get(account.lang, []),
                                       label="개인 의혹·소문 표현, 사실 확인 필요")
        warnings += find_unverified_numbers(text, snapshot)
        warnings += find_stale_series(snapshot)   # 지난 값이 오늘 종가처럼 찍히면 자동 게시하지 않는다
        photos = PhotoPicker(settings, card_dir / "photos", seed=f"{run_date}-{account.key}", offline=offline)
        slides = build_slides(account, text, snapshot, run_date, photos)
        images, render_warnings = render_cards(settings, account, slides, card_dir)
        cs = CardSet(account=account.key, brand=account.brand, lang=account.lang, date=run_date, text=text,
                     images=images, warnings=warnings + render_warnings, output_dir=card_dir)
        cs.caption = full_caption(cs, photo_used=any(s.credit for s in slides), disclaimer=settings.instagram.disclaimer)
        # 카드 종류(릴스에서 장마다 보여 줄 시간)는 나중에 insta-reel 로 릴스만 다시 만들 때 쓴다
        (card_dir / "slides.json").write_text(json.dumps([s.model_dump(mode="json") for s in slides], ensure_ascii=False),
                                              encoding="utf-8")
        if settings.instagram.reels_on(account) and images:
            try:   # 릴스는 덤: 실패해도 캐러셀은 그대로 간다 (경고로 남기지 않아 게시를 막지 않는다)
                cs.reel, track = build_reel(settings, account, images, [s.kind for s in slides], card_dir, run_date,
                                            offline=offline)
                cs.reel_music = f"{track.title} – {track.artist}" if track else ""
            except Exception as e:  # noqa: BLE001
                log.warning("릴스 만들기 실패 %s: %s", account.key, e)
        cardsets.append(cs)
        log.info("카드 %s: %d장 (경고 %d건)", account.key, len(images) or len(slides), len(cs.warnings))
    for line in deliver_cards(settings, cardsets, methods, offline=offline):
        log.info("전달: %s", line)
    return cardsets


def run_intro(settings: Settings, account_key: str, examples_dir, run_date: date | None = None,
              methods: list[str] | None = None) -> CardSet:
    """프로필에 고정할 계정 소개 게시물. 글은 config/intro.yaml, 예시 그림은 실제로 올린 카드 묶음(examples_dir).

    게시는 하지 않는다. 메일로 받아 확인한 뒤 insta-post 로 올린다.
    """
    import shutil
    from pathlib import Path

    from econblog.config import load_intro
    from econblog.deliver.cards import load_saved
    from econblog.models import CardCopy
    from econblog.render.cards import build_intro_slides

    run_date = run_date or today(settings)
    account = next(a for a in settings.instagram.accounts if a.key == account_key)
    intro = load_intro(settings, account_key)
    example = load_saved(Path(examples_dir))
    if not example.images:
        raise ValueError(f"예시 카드 이미지가 없음: {examples_dir}")
    card_dir = settings.resolve_output_dir() / f"{run_date.isoformat()}-intro" / "insta" / account.key
    # 예시 그림을 카드 폴더 안에 복사해 둔다. 나중에 insta-edit 로 다시 찍을 때도 그림이 남아 있게.
    shots_dir = card_dir / "examples"
    shots_dir.mkdir(parents=True, exist_ok=True)
    shots = []
    for p in example.images:
        dst = shots_dir / p.name
        shutil.copyfile(p, dst)
        shots.append(dst)
    slides = build_intro_slides(intro, shots, example.date, account.lang)
    images, warnings = render_cards(settings, account, slides, card_dir)
    md = f"{example.date.month}월 {example.date.day}일" if account.lang == "ko" else f"{example.date:%b} {example.date.day}"
    text = CardCopy(cover_lines=[], cover_photo_query="", board_note="", stories=[], sector_title="", movers_title="",
                    asia_note="", events=[], checklist=[], caption=intro.caption.strip().replace("{example_date}", md),
                    hashtags=intro.hashtags)
    cs = CardSet(account=account.key, brand=account.brand, lang=account.lang, date=run_date, text=text,
                 images=images, warnings=warnings, output_dir=card_dir)
    # 예시 카드 안에 Pixabay 사진이 들어 있다
    cs.caption = full_caption(cs, photo_used=True, disclaimer=settings.instagram.disclaimer)
    publish_off = settings.instagram.model_copy(update={"publish": False})
    for line in deliver_cards(settings.model_copy(update={"instagram": publish_off}), [cs], methods or ["local"]):
        log.info("전달: %s", line)
    return cs


# ---------------------------------------------------------------- 경제 공부 글


def pick_topic(settings: Settings, run_date: date) -> GuideTopic | None:
    """자동 실행일(guide.weekdays)마다 다음 주제로 넘어간다.

    상태를 저장하지 않고, start_date 부터 run_date 까지 지난 실행일 수로 몇 번째 주제인지 계산한다.
    run_date 가 실행일이 아니거나 주제를 다 썼으면 None.
    """
    g = settings.guide
    if g.start_date is None or run_date < g.start_date or run_date.weekday() not in g.weekdays:
        return None
    slots = sum(1 for i in range((run_date - g.start_date).days + 1)
                if (g.start_date + timedelta(days=i)).weekday() in g.weekdays)
    index = g.start_index + slots - 1
    return settings.guides[index] if index < len(settings.guides) else None


def find_topic(settings: Settings, topic_id: str) -> GuideTopic:
    for t in settings.guides:
        if t.id == topic_id:
            return t
    raise KeyError(f"주제 '{topic_id}' 가 config/guides.yaml 에 없음")


def run_guide(
    settings: Settings,
    topic: GuideTopic,
    run_date: date | None = None,
    offline: bool = False,
    deliver_methods: list[str] | None = None,
) -> RenderedPost:
    run_date = run_date or today(settings)
    out_dir = settings.resolve_output_dir() / f"{run_date.isoformat()}-guide-{topic.id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("=== 경제 공부 %s: %s (offline=%s) → %s", run_date, topic.keyword, offline, out_dir)

    # 1. 시장 데이터 (주제에 필요한 시리즈만, 장기 차트용으로 길게)
    keys = sorted(set(topic.series) | {k for c in topic.charts for k in c.series})
    snapshot = build_snapshot(settings, run_date, offline=offline, keys=keys,
                              lookback_days=settings.guide.lookback_days)
    log.info("시장 데이터 %d개 (실패 %d개)", len(snapshot.series), len(snapshot.errors))

    # 2. 차트: 대표 이미지(경제 공부 고정 썸네일, 없으면 키워드 카드) + 주제별 장기 차트
    #    (파일 이름이 시황 차트와 겹치지 않게 주제 아이디를 붙인다)
    chart_dir = out_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    specs = [c.model_copy(update={"key": f"{topic.id}_{c.key}"}) for c in topic.charts]
    cover = fixed_thumbnail(settings, "guide", chart_dir) or guide_cover(
        settings, topic.keyword, topic.subtitle, chart_dir / f"{topic.id}_cover.png")
    charts = [cover]
    charts += build_charts(settings, snapshot, chart_dir, specs)
    log.info("차트 %d개", len(charts))
    warnings = publish_charts(settings, charts, run_date, offline=offline)

    # 3. 초안
    ctx = GuideContext(date=run_date, topic=topic, snapshot=snapshot, charts=charts[1:])
    content, write_warnings = write_guide(settings, ctx, offline=offline)
    content = polish(settings, content, offline=offline)
    warnings = write_warnings + warnings

    # 4. 말투 검사 (참고 기사가 없으므로 원문 복사 검사는 하지 않는다)
    warnings += find_ai_phrases(content, settings.guard.ai_phrases)
    if snapshot.errors:
        warnings.append("데이터 수집 실패: " + ", ".join(sorted(snapshot.errors)))

    # 5. 렌더링·전달
    naver, naver_warnings = _naver_version(settings, content, [], offline)
    warnings += naver_warnings
    draft = GuideDraft(date=run_date, topic=topic, content=content, naver=naver, charts=charts,
                       now_rows=guide_rows(ctx), warnings=warnings)
    post = render_guide(settings, draft, out_dir, recent=fetch_recent(settings, offline, content.title))
    for line in deliver_all(settings, post, deliver_methods):
        log.info("전달: %s", line)
    if warnings:
        log.warning("검토 필요 %d건: %s", len(warnings), " | ".join(warnings))
    return post
