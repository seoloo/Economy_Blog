"""결과 전달 단계."""

from __future__ import annotations

import logging

from econblog import registry
from econblog.config import Settings
from econblog.models import RenderedPost

log = logging.getLogger(__name__)

DELIVERERS: dict[str, str] = {
    "local": "econblog.deliver.local:LocalDeliverer",
    "email": "econblog.deliver.email:EmailDeliverer",
}


def deliver_all(settings: Settings, post: RenderedPost, methods: list[str] | None = None) -> list[str]:
    results: list[str] = []
    for name in methods if methods is not None else settings.deliver.methods:
        deliverer = registry.load(DELIVERERS, name)(settings)
        if not deliverer.is_configured():
            log.info("전달 건너뜀 %s: 설정 없음", name)
            continue
        results.append(deliverer.deliver(post))
    return results
