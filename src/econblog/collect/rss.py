"""RSS/Atom 피드 수집기. 제목·요약(최대 300자)·링크만 사용한다."""

from __future__ import annotations

import calendar
import html
import re
from datetime import datetime, timezone

import feedparser
import requests

from econblog.collect.base import Collector
from econblog.models import Article, Source

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
SUMMARY_MAX_CHARS = 300


def clean_text(raw: str, limit: int | None = None) -> str:
    text = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", raw or ""))).strip()
    if limit and len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    return None


class RssCollector(Collector):
    def fetch_feed(self, url: str) -> bytes:
        cfg = self.settings.collect
        resp = requests.get(url, headers={"User-Agent": cfg.user_agent}, timeout=cfg.timeout_sec)
        resp.raise_for_status()
        return resp.content

    def parse(self, source: Source, raw: bytes, since: datetime) -> list[Article]:
        feed = feedparser.parse(raw)
        if feed.bozo and not feed.entries:
            raise ValueError(f"피드 파싱 실패: {feed.bozo_exception}")

        articles: list[Article] = []
        for entry in feed.entries:
            title = clean_text(entry.get("title", ""))
            link = entry.get("link", "")
            if not title or not link:
                continue
            published = _published(entry)
            if published and published < since:
                continue
            articles.append(
                Article(
                    source_id=source.id,
                    source_name=source.name,
                    region=source.region,
                    kind=source.kind,
                    lang=source.lang,
                    title=title,
                    url=link,
                    summary=clean_text(entry.get("summary", ""), SUMMARY_MAX_CHARS),
                    published=published,
                )
            )

        oldest = datetime.min.replace(tzinfo=timezone.utc)
        articles.sort(key=lambda a: a.published or oldest, reverse=True)
        return articles[: self.settings.collect.max_per_source]

    def collect(self, source: Source, since: datetime) -> list[Article]:
        return self.parse(source, self.fetch_feed(source.url), since)
