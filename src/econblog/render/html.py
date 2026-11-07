"""templates/post.html.j2 로 두 가지 HTML 을 만든다.

- post.html:    티스토리 HTML 모드에 붙여넣는 본문. 차트 자리는 업로드 안내 상자로 표시.
- preview.html: 로컬/메일 확인용. 발행 체크리스트와 차트 이미지를 함께 보여준다.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from econblog.config import Settings
from econblog.models import Draft, RenderedPost
from econblog.render.quotes import build_table


def _cited_references(draft: Draft) -> list:
    """이슈에서 실제로 인용한 기사만 참고 자료로 남긴다 (등장 순서 유지)."""
    by_url = {a.url: a for a in draft.references}
    seen: list = []
    for issue in draft.content.issues:
        for url in issue.reference_urls:
            article = by_url.get(url)
            if article and article not in seen:
                seen.append(article)
    return seen


def render_post(settings: Settings, draft: Draft, out_dir: Path) -> RenderedPost:
    env = Environment(
        loader=FileSystemLoader(settings.templates_dir),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("post.html.j2")
    references = _cited_references(draft)
    post = settings.post
    common = dict(
        draft=draft,
        c=draft.content,
        charts=draft.charts,
        glance=build_table(draft.quotes, post.glance),
        global_table=build_table(draft.quotes, post.global_table),
        korea_table=build_table(draft.quotes, post.korea_table),
        hashtags=" ".join("#" + t.replace(" ", "") for t in draft.content.tags if t.strip()),
        references=references,
        ref_names={a.url: a.source_name for a in draft.references},
    )
    return RenderedPost(
        draft=draft,
        html=template.render(mode="tistory", **common).strip() + "\n",
        preview_html=template.render(mode="preview", **common).strip() + "\n",
        output_dir=out_dir,
    )
