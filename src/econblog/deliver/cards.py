"""인스타 카드뉴스 전달: 로컬 저장, 메일(카드 이미지 + 캡션), 인스타 게시.

인스타 게시는 settings.yaml instagram.publish 가 true 이고 계정 토큰이 있을 때만 한다.
카드 JPEG 을 공개 이미지 레포(charts/publish.py)에 올린 뒤 그 주소로 캐러셀을 만든다.
인스타 API 는 JPEG 공개 주소만 받는다. 토큰과 계정 ID 는 로그에 남기지 않는다.
"""

from __future__ import annotations

import json
import logging
import time
from email.message import EmailMessage
from html import escape

import requests

from econblog.charts import publish
from econblog.config import CardAccount, Settings, env
from econblog.deliver import email as mail
from econblog.models import CardSet

log = logging.getLogger(__name__)

CAPTION_LIMIT = 2200
HASHTAG_LIMIT = 30


def full_caption(cs: CardSet, photo_used: bool) -> str:
    """캡션 본문 + 면책·출처 + 해시태그. 인스타 한도(2,200자, 해시태그 30개)를 넘지 않게 자른다."""
    if cs.lang == "ko":
        note = "투자 권유가 아닌 정보 제공용 콘텐츠입니다. 자료: Yahoo Finance" + (" · 사진: Pixabay" if photo_used else "")
    else:
        note = "For information only. Not financial advice. Data: Yahoo Finance" + (" · Photos: Pixabay" if photo_used else "")
    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in cs.text.hashtags[:HASHTAG_LIMIT] if t.strip())
    tail = f"\n\n{note}\n\n{tags}".rstrip()
    body = cs.text.caption.strip()
    room = CAPTION_LIMIT - len(tail)
    if len(body) > room:
        body = body[: room - 1].rstrip() + "…"
    return body + tail


def save_local(cs: CardSet) -> None:
    cs.output_dir.mkdir(parents=True, exist_ok=True)
    (cs.output_dir / "caption.txt").write_text(cs.caption, encoding="utf-8")
    meta = {"account": cs.account, "brand": cs.brand, "lang": cs.lang, "date": cs.date.isoformat(),
            "images": [p.name for p in cs.images],
            "urls": cs.urls, "media_id": cs.media_id, "warnings": cs.warnings,
            "text": cs.text.model_dump()}
    (cs.output_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- 인스타 게시


class GraphError(RuntimeError):
    pass


def _graph(account_token: str, version: str) -> tuple[requests.Session, str]:
    # 인스타 로그인 토큰(IG…)은 graph.instagram.com, 페이스북(비즈니스) 로그인 토큰은 graph.facebook.com
    host = "graph.instagram.com" if account_token.startswith("IG") else "graph.facebook.com"
    return requests.Session(), f"https://{host}/{version}"


def _call(session: requests.Session, method: str, url: str, **data) -> dict:
    resp = session.request(method, url, timeout=60, **({"data": data} if method == "POST" else {"params": data}))
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code >= 400 or "error" in body:
        msg = (body.get("error") or {}).get("message") or resp.text[:200]
        raise GraphError(msg)
    return body


def _wait_ready(session, base: str, container: str, token: str, timeout: float = 180) -> None:
    deadline = time.monotonic() + timeout
    while True:
        status = _call(session, "GET", f"{base}/{container}", fields="status_code", access_token=token).get("status_code")
        if status in (None, "FINISHED", "PUBLISHED"):
            return
        if status in ("ERROR", "EXPIRED"):
            raise GraphError(f"미디어 처리 실패 ({status})")
        if time.monotonic() > deadline:
            raise GraphError("미디어 처리 시간 초과")
        time.sleep(3)


def publish_instagram(settings: Settings, account: CardAccount, image_urls: list[str], caption: str) -> str:
    """캐러셀 게시: 장마다 컨테이너 → 캐러셀 컨테이너 → 게시. 게시물 ID 를 돌려준다."""
    token, user = env(account.token_env), env(account.user_env)
    if not token or not user:
        raise GraphError("토큰 또는 계정 ID 없음")
    session, base = _graph(token, settings.instagram.graph_version)
    children = []
    for url in image_urls[:10]:   # 캐러셀은 최대 10장
        cid = _call(session, "POST", f"{base}/{user}/media", image_url=url, is_carousel_item="true", access_token=token)["id"]
        children.append(cid)
    for cid in children:
        _wait_ready(session, base, cid, token)
    parent = _call(session, "POST", f"{base}/{user}/media", media_type="CAROUSEL", children=",".join(children),
                   caption=caption, access_token=token)["id"]
    _wait_ready(session, base, parent, token)
    return _call(session, "POST", f"{base}/{user}/media_publish", creation_id=parent, access_token=token)["id"]


def check_account(settings: Settings, account: CardAccount) -> tuple[bool, str]:
    """게시 없이 토큰·계정 ID 가 맞는지 확인한다 (계정 이름과 게시 한도 조회만). 토큰 값은 출력하지 않는다."""
    token, user = env(account.token_env), env(account.user_env)
    if not token or not user:
        return False, f"{account.key}: 토큰 또는 계정 ID 없음 ({account.token_env}, {account.user_env})"
    session, base = _graph(token, settings.instagram.graph_version)
    host = base.split("/")[2]
    try:
        info = _call(session, "GET", f"{base}/{user}", fields="username,media_count", access_token=token)
    except GraphError as e:
        return False, f"{account.key}: 계정 조회 실패 ({host}): {e}"
    try:
        quota = _call(session, "GET", f"{base}/{user}/content_publishing_limit", fields="quota_usage", access_token=token)
        used = (quota.get("data") or [{}])[0].get("quota_usage", "?")
        limit = f"게시 권한 확인됨 (최근 24시간 게시 {used}건)"
    except GraphError as e:
        return False, f"{account.key}: @{info.get('username')} 연결됨, 게시 권한 확인 실패: {e}"
    return True, f"{account.key}: @{info.get('username')} 연결됨 ({host}, 게시물 {info.get('media_count', 0)}개), {limit}"


def _publish(settings: Settings, account: CardAccount, cs: CardSet) -> str:
    if not cs.images:
        raise GraphError("카드 이미지가 없음")
    if not publish.is_configured(settings):
        raise GraphError("공개 이미지 레포 설정(CHARTS_REPO_TOKEN)이 없어 카드 주소를 만들 수 없음")
    files = [(p, f"{cs.date.isoformat()}/insta/{cs.account}/{p.name}") for p in cs.images]
    cs.urls = publish.publish_files(settings, files, f"{cs.date} insta {cs.account}")
    if not publish.wait_until_public(cs.urls):
        raise GraphError("카드 공개 주소가 열리지 않음 (GitHub Pages 반영 지연)")
    return publish_instagram(settings, account, cs.urls, cs.caption)


def load_saved(card_dir) -> CardSet:
    """이미 만든 카드 폴더(01.jpg…, caption.txt, meta.json)를 다시 읽는다. 확인한 카드를 그대로 게시할 때 쓴다."""
    from datetime import date as _date
    from pathlib import Path as _Path

    from econblog.models import CardCopy

    card_dir = _Path(card_dir)
    meta = json.loads((card_dir / "meta.json").read_text(encoding="utf-8"))
    return CardSet(account=meta["account"], brand=meta.get("brand", meta["account"]), lang=meta.get("lang", "ko"),
                   date=_date.fromisoformat(meta["date"]), text=CardCopy.model_validate(meta["text"]),
                   images=sorted(card_dir.glob("[0-9][0-9].jpg")),
                   caption=(card_dir / "caption.txt").read_text(encoding="utf-8"), output_dir=card_dir)


def apply_edits(card_dir, edits: list[list[str]]) -> list:
    """확인한 카드 묶음에서 문장만 고친다 (카드 HTML·caption.txt·meta.json 에 찾아 바꾸기).

    고친 HTML 은 다시 찍어야 하므로 그 목록을 돌려준다. 어느 파일에도 없는 문장이 있으면 멈춘다.
    """
    from html import escape as _esc
    from pathlib import Path as _Path

    card_dir = _Path(card_dir)
    files = sorted(card_dir.glob("[0-9][0-9].html")) + [card_dir / "caption.txt", card_dir / "meta.json"]
    texts = {f: f.read_text(encoding="utf-8") for f in files if f.exists()}
    for old, _ in edits:
        if not any(old in t or _esc(old, quote=False) in t for t in texts.values()):
            raise ValueError(f"카드에서 찾지 못한 문장: {old}")
    changed = []
    for f, t in texts.items():
        new = t
        for old, rep in edits:
            new = new.replace(old, rep)
            if f.suffix == ".html":
                new = new.replace(_esc(old, quote=False), _esc(rep, quote=False))
        if new != t:
            f.write_text(new, encoding="utf-8")
            if f.suffix == ".html":
                changed.append(f)
    return changed


def publish_saved(settings: Settings, card_dir) -> CardSet:
    """저장된 카드 묶음을 그 내용 그대로 인스타에 올린다 (publish 설정과 상관없이, 사람이 직접 실행할 때만)."""
    cs = load_saved(card_dir)
    account = next(a for a in settings.instagram.accounts if a.key == cs.account)
    cs.media_id = _publish(settings, account, cs)
    save_local(cs)
    return cs


# ---------------------------------------------------------------- 메일


def build_cards_message(cardsets: list[CardSet], sender: str, recipients: str) -> EmailMessage:
    first = cardsets[0]
    warn = sum(len(cs.warnings) for cs in cardsets)
    flag = f"[검토 {warn}건] " if warn else ""
    parts = " · ".join(f"{cs.brand} {len(cs.images)}장{' 게시됨' if cs.media_id else ''}" for cs in cardsets)
    msg = EmailMessage()
    msg["Subject"] = f"[인스타 카드] {flag}{first.date:%m/%d} {parts}"
    msg["From"] = sender
    msg["To"] = recipients
    msg.set_content("HTML 메일을 지원하는 메일 앱에서 확인하세요. 카드 이미지와 캡션이 들어 있습니다.")

    blocks = []
    cids: list[tuple[str, bytes]] = []
    for cs in cardsets:
        status = ("인스타에 게시했습니다." if cs.media_id else
                  "메일로만 보냈습니다. 카드를 저장해 직접 올리거나, 확인 후 settings.yaml 의 instagram.publish 를 켜세요.")
        warns = "".join(f"<li>{escape(w)}</li>" for w in cs.warnings)
        imgs = []
        for i, p in enumerate(cs.images, 1):
            cid = f"{cs.account}{i:02d}"
            cids.append((cid, p.read_bytes()))
            imgs.append(f'<img src="cid:{cid}" width="300" style="margin:0 6px 10px 0;border-radius:8px">')
        blocks.append(
            f"<h2 style='margin:28px 0 6px'>{escape(cs.brand)}</h2><p style='color:#555'>{escape(status)}</p>"
            + (f"<ul style='color:#b42318'>{warns}</ul>" if warns else "")
            + f"<div>{''.join(imgs)}</div>"
            + "<p style='margin-top:14px;font-weight:bold'>캡션 (복사해서 쓰세요)</p>"
            + f"<pre style='white-space:pre-wrap;font-family:inherit;background:#f6f6f6;padding:14px;border-radius:8px'>"
              f"{escape(cs.caption)}</pre>"
        )
    msg.add_alternative("<html><body style='font-family:sans-serif'>" + "".join(blocks) + "</body></html>", subtype="html")
    html_part = msg.get_payload()[1]
    for cid, data in cids:
        html_part.add_related(data, "image", "jpeg", cid=f"<{cid}>")
    return msg


# ---------------------------------------------------------------- 묶음 전달


def deliver_cards(settings: Settings, cardsets: list[CardSet], methods: list[str], offline: bool = False) -> list[str]:
    accounts = {a.key: a for a in settings.instagram.accounts}
    results = []
    if settings.instagram.publish and not offline:
        for cs in cardsets:
            account = accounts[cs.account]
            if not (env(account.token_env) and env(account.user_env)):
                log.info("인스타 게시 건너뜀 %s: 토큰 없음", cs.account)
                continue
            if cs.warnings:   # 검토 경고(숫자·저작권·모호한 표현)가 있는 날은 사람이 보고 올린다
                log.info("인스타 게시 건너뜀 %s: 검토 경고 %d건", cs.account, len(cs.warnings))
                cs.warnings.append("검토 경고가 있어 자동 게시하지 않았습니다 (확인 후 insta-post 로 올리세요)")
                continue
            try:
                cs.media_id = _publish(settings, account, cs)
                results.append(f"인스타 게시 {cs.account}")
            except Exception as e:  # noqa: BLE001
                log.warning("인스타 게시 실패 %s: %s", cs.account, e)
                cs.warnings.append(f"인스타 게시 실패: {e}")
    for cs in cardsets:
        save_local(cs)
    results.append(f"카드 저장 {', '.join(str(cs.output_dir) for cs in cardsets)}")
    if "email" in methods and mail.is_configured() and any(cs.images for cs in cardsets):
        mail.send(build_cards_message(cardsets, env("SMTP_USER"), env("MAIL_TO")))
        results.append("카드 메일 발송")
    return results
