"""templates/post.html.j2 로 두 가지 HTML 을 만든다.

- post.html:    티스토리 HTML 모드에 붙여넣는 본문. 차트 자리는 업로드 안내 문구로 표시.
- preview.html: 로컬/메일 확인용. 차트 이미지를 실제로 보여준다.
"""

from __future__ import annotations

from pathlib import Path

from econblog.config import Settings
from econblog.models import Draft, RenderedPost


def render_post(settings: Settings, draft: Draft, out_dir: Path) -> RenderedPost:
    raise NotImplementedError
