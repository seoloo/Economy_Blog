"""SMTP 로 초안 메일을 보낸다.

메일 두 통을 보낸다.
1) 티스토리용 — 본문: preview.html (차트를 메일 안에 이미지로 표시), 첨부: post.html, naver.html, 차트 PNG
2) 네이버 블로그용 — 본문: 네이버판 글 그대로 (제목·태그 상자 + 붙여넣을 글), 첨부: naver.html, 차트 PNG
"""

from __future__ import annotations

import html as html_lib
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path

from econblog.config import env
from econblog.deliver.base import Deliverer
from econblog.models import RenderedPost

REQUIRED = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO")


def _subtype(path: Path) -> str:
    return "jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "png"


def build_message(post: RenderedPost, sender: str, recipients: str) -> EmailMessage:
    draft = post.draft
    flag = f"[검토 {len(draft.warnings)}건] " if draft.warnings else ""
    msg = EmailMessage()
    kind = "블로그 초안·경제 공부" if draft.kind == "guide" else "블로그 초안"
    msg["Subject"] = f"[{kind}] {flag}{draft.date:%m/%d} {draft.content.title}"
    msg["From"] = sender
    msg["To"] = recipients

    # 공개 주소에 올린 차트는 본문이 그 주소를 쓴다 (메일을 복사해 붙여넣어도 이미지가 살아 있음).
    # 올리지 못한 차트만 메일 안에 이미지로 넣는다.
    local = [c for c in draft.charts if not c.url]
    html = post.preview_html
    for chart in local:
        html = html.replace(f'src="charts/{chart.path.name}"', f'src="cid:{chart.key}"')
    msg.set_content(f"{draft.content.title}\n\nHTML 메일을 지원하는 메일 앱에서 확인하세요. 붙여넣기용 post.html(티스토리)과 naver.html(네이버 블로그)이 첨부되어 있습니다.")
    msg.add_alternative(html, subtype="html")

    html_part = msg.get_payload()[1]
    for chart in local:
        html_part.add_related(chart.path.read_bytes(), "image", _subtype(chart.path), cid=f"<{chart.key}>")

    msg.add_attachment(post.html.encode("utf-8"), maintype="text", subtype="html", filename="post.html")
    if post.naver_html:
        msg.add_attachment(post.naver_html.encode("utf-8"), maintype="text", subtype="html", filename="naver.html")
    for chart in draft.charts:
        msg.add_attachment(chart.path.read_bytes(), maintype="image", subtype=_subtype(chart.path),
                           filename=chart.path.name)
    return msg


def build_naver_message(post: RenderedPost, sender: str, recipients: str) -> EmailMessage | None:
    """네이버 블로그용 글을 따로 한 통으로 보낸다. 첨부를 열지 않아도 메일 본문에서 바로 읽고 복사할 수 있다."""
    if not post.naver_html:
        return None
    draft = post.draft
    content = draft.naver or draft.content
    notes = [w for w in draft.warnings if "네이버판" in w]
    flag = f"[검토 {len(notes)}건] " if notes else ""
    kind = "네이버 블로그 초안·경제 공부" if draft.kind == "guide" else "네이버 블로그 초안"
    msg = EmailMessage()
    msg["Subject"] = f"[{kind}] {flag}{draft.date:%m/%d} {content.title}"
    msg["From"] = sender
    msg["To"] = recipients

    esc = html_lib.escape
    same = "" if draft.naver else "<br>※ 다시 쓰기가 되지 않아 티스토리판과 같은 글입니다. 그대로 올리면 중복 문서로 보일 수 있습니다."
    warn = "".join(f"<br>※ 확인: {esc(w)}" for w in notes)
    box = ('<div style="background:#eaf7ee;border:1px solid #b7dfc2;padding:14px 16px;margin:0 0 24px;font-size:14px;line-height:1.7;">'
           "<b>네이버 블로그용 글입니다.</b> 티스토리판과 같은 내용을 다른 문장으로 다시 쓴 글이에요."
           f"<br><b>제목</b>: {esc(content.title)}<br><b>태그</b>: {esc(', '.join(content.tags))}"
           "<br>이 상자 아래부터 끝까지 복사해 붙여넣고, [사진] 줄 자리에는 첨부한 이미지를 올리세요."
           f"{same}{warn}</div>")
    body = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + box, post.naver_html, count=1)
    msg.set_content(f"{content.title}\n\nHTML 메일을 지원하는 메일 앱에서 확인하세요. 붙여넣기용 naver.html 이 첨부되어 있습니다.")
    msg.add_alternative(body, subtype="html")
    msg.add_attachment(post.naver_html.encode("utf-8"), maintype="text", subtype="html", filename="naver.html")
    for chart in draft.charts:
        msg.add_attachment(chart.path.read_bytes(), maintype="image", subtype=_subtype(chart.path),
                           filename=chart.path.name)
    return msg


class EmailDeliverer(Deliverer):
    def is_configured(self) -> bool:
        return all(env(k) for k in REQUIRED)

    def deliver(self, post: RenderedPost) -> str:
        send(build_message(post, env("SMTP_USER"), env("MAIL_TO")))
        naver = build_naver_message(post, env("SMTP_USER"), env("MAIL_TO"))
        if naver is None:
            return "메일 발송 완료"
        send(naver)
        return "메일 발송 완료 (티스토리용, 네이버용 2통)"


def is_configured() -> bool:
    return all(env(k) for k in REQUIRED)


def send(msg: EmailMessage) -> None:
    with smtplib.SMTP(env("SMTP_HOST"), int(env("SMTP_PORT") or 587), timeout=60) as smtp:
        smtp.starttls()
        smtp.login(env("SMTP_USER"), env("SMTP_PASSWORD"))
        smtp.send_message(msg)
