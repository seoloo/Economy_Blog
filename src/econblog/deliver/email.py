"""SMTP 로 초안 메일을 보낸다.

본문: preview.html (차트를 메일 안에 이미지로 표시)
첨부: post.html (티스토리 붙여넣기용), 차트 PNG
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from econblog.config import env
from econblog.deliver.base import Deliverer
from econblog.models import RenderedPost

REQUIRED = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO")


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
    msg.set_content(f"{draft.content.title}\n\nHTML 메일을 지원하는 메일 앱에서 확인하세요. 붙여넣기용 post.html 이 첨부되어 있습니다.")
    msg.add_alternative(html, subtype="html")

    html_part = msg.get_payload()[1]
    for chart in local:
        html_part.add_related(chart.path.read_bytes(), "image", "png", cid=f"<{chart.key}>")

    msg.add_attachment(post.html.encode("utf-8"), maintype="text", subtype="html", filename="post.html")
    for chart in draft.charts:
        msg.add_attachment(chart.path.read_bytes(), maintype="image", subtype="png", filename=chart.path.name)
    return msg


class EmailDeliverer(Deliverer):
    def is_configured(self) -> bool:
        return all(env(k) for k in REQUIRED)

    def deliver(self, post: RenderedPost) -> str:
        user = env("SMTP_USER")
        recipients = env("MAIL_TO")
        msg = build_message(post, user, recipients)
        with smtplib.SMTP(env("SMTP_HOST"), int(env("SMTP_PORT") or 587), timeout=60) as smtp:
            smtp.starttls()
            smtp.login(user, env("SMTP_PASSWORD"))
            smtp.send_message(msg)
        return "메일 발송 완료"
