"""templates/post.html.j2 로 세 가지 HTML 을 만든다.

- post.html:    티스토리 HTML 모드에 붙여넣는 본문. 차트 자리는 업로드 안내 상자로 표시.
- preview.html: 로컬/메일 확인용. 발행 체크리스트와 차트 이미지를 함께 보여준다.
- naver.html:   네이버 블로그용. 브라우저로 열어 전체 복사해 스마트에디터에 붙여넣는다 (이미지는 공개 주소의 그림, 없으면 [사진] 안내 줄).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

from econblog.config import Settings
from econblog.models import Article, Draft, GuideDraft, RecentPost, RenderedPost
from econblog.render.quotes import build_table


class RefLink(NamedTuple):
    url: str
    title: str
    source_name: str


def ref_link(a: Article) -> RefLink:
    """구글 뉴스 RSS 는 제목 끝에 ' - 언론사' 가 붙어 있다. 출처를 'Google 뉴스' 대신 실제 언론사로 표시한다."""
    if a.source_id.startswith("gnews") and " - " in a.title:
        title, publisher = a.title.rsplit(" - ", 1)
        if title.strip() and publisher.strip():
            return RefLink(a.url, title.strip(), publisher.strip())
    return RefLink(a.url, a.title, a.source_name)


def _cited_references(draft: Draft) -> list[RefLink]:
    """이슈에서 실제로 인용한 기사만 참고 자료로 남긴다 (등장 순서 유지)."""
    by_url = {a.url: a for a in draft.references}
    seen: list[RefLink] = []
    for issue in draft.content.issues:
        for url in issue.reference_urls:
            article = by_url.get(url)
            if article and (link := ref_link(article)) not in seen:
                seen.append(link)
    return seen


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def rich(text: str) -> Markup:
    """LLM 문장의 **강조** 를 <strong> 으로 바꾼다. 나머지는 모두 이스케이프한다."""
    return Markup(_BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", str(escape(text))))


def plain(text: str) -> str:
    return text.replace("**", "")


def _env(settings: Settings) -> Environment:
    env = Environment(
        loader=FileSystemLoader(settings.templates_dir),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["rich"] = rich
    env.filters["plain"] = plain
    return env


def _render_all(template, draft: Draft | GuideDraft, out_dir: Path, common: dict) -> RenderedPost:
    def one(mode: str) -> str:
        # 네이버판은 다시 쓴 글(draft.naver)로 그린다. 없으면 티스토리판과 같은 글
        ctx = {**common, "c": draft.naver or draft.content} if mode == "naver" else common
        return template.render(mode=mode, **ctx).strip() + "\n"

    return RenderedPost(draft=draft, html=one("tistory"), preview_html=one("preview"),
                        naver_html=one("naver"), output_dir=out_dir)


def render_post(settings: Settings, draft: Draft, out_dir: Path,
                recent: list[RecentPost] | None = None) -> RenderedPost:
    template = _env(settings).get_template("post.html.j2")
    references = _cited_references(draft)
    post = settings.post
    common = dict(
        draft=draft,
        c=draft.content,
        cover=next((ch for ch in draft.charts if ch.position == "cover"), None),
        lead_charts=[ch for ch in draft.charts if ch.position == "lead"],
        body_charts=[ch for ch in draft.charts if ch.position == "body"],
        glance=build_table(draft.quotes, post.glance),
        global_table=build_table(draft.quotes, post.global_table),
        korea_table=build_table(draft.quotes, post.korea_table),
        references=references,
        ref_names={a.url: ref_link(a).source_name for a in draft.references},
        recent=recent or [],
    )
    return _render_all(template, draft, out_dir, common)


def render_guide(settings: Settings, draft: GuideDraft, out_dir: Path,
                 recent: list[RecentPost] | None = None) -> RenderedPost:
    """경제 공부 글. 공통 부품은 시황 글과 같다 (templates/_tistory.html.j2)."""
    template = _env(settings).get_template("guide.html.j2")
    body_charts = [ch for ch in draft.charts if ch.position != "cover"]
    sources = sorted({ch.source_note.removeprefix("자료: ") for ch in body_charts if ch.source_note})
    common = dict(
        draft=draft,
        c=draft.content,
        cover=next((ch for ch in draft.charts if ch.position == "cover"), None),
        body_charts=body_charts,
        now_rows=draft.now_rows,
        source_note="자료: " + ", ".join(sources) if sources else "자료: Yahoo Finance, FRED, 한국은행 ECOS",
        recent=recent or [],
    )
    return _render_all(template, draft, out_dir, common)
