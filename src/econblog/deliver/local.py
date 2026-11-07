"""output/<날짜>/ 에 post.html, preview.html, meta.json 을 저장한다 (차트는 charts/ 에 이미 있음)."""

from __future__ import annotations

import json

from econblog.deliver.base import Deliverer
from econblog.models import RenderedPost


class LocalDeliverer(Deliverer):
    def deliver(self, post: RenderedPost) -> str:
        out = post.output_dir
        out.mkdir(parents=True, exist_ok=True)
        (out / "post.html").write_text(post.html, encoding="utf-8")
        (out / "preview.html").write_text(post.preview_html, encoding="utf-8")
        meta = {
            "date": post.draft.date.isoformat(),
            "title": post.draft.content.title,
            "tags": post.draft.content.tags,
            "warnings": post.draft.warnings,
            "charts": [c.path.name for c in post.draft.charts],
        }
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"로컬 저장 {out}"
