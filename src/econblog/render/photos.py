"""인스타 카드 배경 사진. Pixabay API 로 검색해 내려받는다 (PIXABAY_API_KEY 필요).

Pixabay 사진은 상업적 사용·수정이 허용되고 출처 표기를 요구하지 않는다. API 이용 조건에 따라
사진은 내려받아 쓰고(주소를 바로 걸지 않음), 캡션에 'Pixabay' 출처를 적는다.
키가 없거나 오프라인이면 None 을 돌려주고, 카드는 단색 배경으로 그린다.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests

from econblog.config import Settings, env

log = logging.getLogger(__name__)

API = "https://pixabay.com/api/"

# 검색어가 같아도 엉뚱한 사진이 걸리는 경우가 있다 (semiconductor wafer → 웨이퍼 과자).
# 음식 사진과 사람 얼굴이 중심인 사진은 태그로 걸러 낸다 (초상권 문제도 피한다).
BLOCKED_TAGS = {
    "food", "dessert", "cake", "cookie", "cookies", "biscuit", "waffle", "wafer", "wafers", "ice cream", "candy",
    "chocolate", "sweet", "sweets", "snack", "fruit", "breakfast", "meal", "pastry", "bakery", "cream",
    "portrait", "face", "girl", "woman", "man", "boy", "model", "selfie", "child",
}


def _allowed(hit: dict) -> bool:
    tags = {t.strip().lower() for t in str(hit.get("tags", "")).split(",")}
    return not (tags & BLOCKED_TAGS)


class PhotoPicker:
    """한 번의 실행에서 같은 사진이 두 번 나오지 않게 고른 사진 ID 를 기억한다."""

    def __init__(self, settings: Settings, out_dir: Path, seed: str, offline: bool = False):
        self.settings = settings
        self.out_dir = out_dir
        self.seed = seed
        self.key = None if offline or not settings.instagram.photos else env("PIXABAY_API_KEY")
        self.used: set[int] = set()
        self.session = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def find(self, query: str, orientation: str = "vertical") -> Path | None:
        if not self.key or not query.strip():
            return None
        try:
            return self._find(query.strip(), orientation)
        except Exception as e:  # noqa: BLE001
            log.warning("사진 검색 실패 '%s': %s", query, e)
            return None

    def _find(self, query: str, orientation: str) -> Path | None:
        resp = self.session.get(API, timeout=20, params={
            "key": self.key, "q": query[:100], "image_type": "photo", "orientation": orientation,
            "safesearch": "true", "per_page": 20, "order": "popular", "min_width": 1080,
        })
        resp.raise_for_status()
        hits = [h for h in resp.json().get("hits", [])
                if h.get("id") not in self.used and h.get("largeImageURL") and _allowed(h)]
        if not hits:
            return None
        # 인기 순 상위 몇 장 안에서 날짜마다 다른 사진이 나오게 고른다
        pick = int(hashlib.sha256(f"{self.seed}:{query}".encode()).hexdigest(), 16) % min(5, len(hits))
        hit = hits[pick]
        self.used.add(hit["id"])
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"pixabay_{hit['id']}.jpg"
        if not path.exists():
            img = self.session.get(hit["largeImageURL"], timeout=60)
            img.raise_for_status()
            path.write_bytes(img.content)
        return path
