"""글 끝 '최근에 올라온 글' 링크: 우리 블로그 RSS 에서 최근 글 몇 개를 가져온다.

남의 글이 아니라 우리 블로그 글 제목과 주소만 쓴다. 가져오지 못하면 빈 목록 (본문에는 링크 넣을 자리가 남는다).
"""

from __future__ import annotations

import logging

import feedparser
import requests

from econblog.config import Settings
from econblog.models import RecentPost

log = logging.getLogger(__name__)


def parse_recent(raw: bytes, limit: int, exclude_title: str = "") -> list[RecentPost]:
    feed = feedparser.parse(raw)
    out: list[RecentPost] = []
    for e in feed.entries:
        title, url = (e.get("title") or "").strip(), (e.get("link") or "").strip()
        if not title or not url or title == exclude_title.strip():
            continue
        out.append(RecentPost(title=title, url=url))
        if len(out) >= limit:
            break
    return out


def fetch_recent(settings: Settings, offline: bool = False, exclude_title: str = "") -> list[RecentPost]:
    post = settings.post
    if offline or not post.blog_rss or post.recent_posts <= 0:
        return []
    try:
        resp = requests.get(post.blog_rss, timeout=20, headers={"User-Agent": "Mozilla/5.0 (econblog)"})
        resp.raise_for_status()
        return parse_recent(resp.content, post.recent_posts, exclude_title)
    except Exception as e:  # noqa: BLE001
        log.warning("최근 글 목록을 가져오지 못함: %s", e)
        return []
