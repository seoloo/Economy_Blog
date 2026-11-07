from datetime import datetime, timezone

import pytest

from econblog.config import load_settings
from econblog.models import Article


@pytest.fixture
def settings(tmp_path):
    s = load_settings()
    s.output_dir = tmp_path / "output"
    return s


def make_article(title: str, region: str = "kr", summary: str = "", kind: str = "news", url: str | None = None) -> Article:
    return Article(
        source_id="t",
        source_name="테스트",
        region=region,
        kind=kind,
        lang="ko" if region == "kr" else "en",
        title=title,
        url=url or f"https://example.com/{abs(hash(title))}",
        summary=summary,
        published=datetime.now(timezone.utc),
    )
