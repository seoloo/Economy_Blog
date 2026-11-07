"""Laya 결정 모델(api.laya-ai.com)로 주제와 중요도를 판정한다.

Laya 는 글을 생성하지 않고 choice/score 같은 판단만 돌려준다.
요금: 1,000회 호출당 $0.05 (2026-11 기준). 배치 1회 = 기사 수만큼 호출로 계산될 수 있다.
"""

from __future__ import annotations

import logging
import time

import requests

from econblog.classify.base import Classifier
from econblog.config import env
from econblog.models import Article, ClassifiedArticle

log = logging.getLogger(__name__)

API_BASE = "https://api.laya-ai.com/v1"
BATCH_SIZE = 64
STATE_MAX_CHARS = 800

IMPORTANCE_LEVELS = ["minor", "notable", "important", "major"]
IMPORTANCE_INSTRUCTIONS = (
    "How important is this news for a daily financial market summary written for Korean investors? "
    "major = moves global or Korean markets today (central bank decisions, key inflation/jobs data, big index moves); "
    "minor = niche, local or promotional."
)
TOPIC_INSTRUCTIONS = "Which economic topic does this news article mainly cover?"


def level_to_importance(answer: dict) -> float:
    """score 응답을 0~1 로 바꾼다. probabilities 가 있으면 기대값, 없으면 단계 위치."""
    n = len(IMPORTANCE_LEVELS)
    probs = answer.get("probabilities")
    if isinstance(probs, dict) and probs:
        total = sum(probs.values()) or 1.0
        return sum(IMPORTANCE_LEVELS.index(k) / (n - 1) * v for k, v in probs.items() if k in IMPORTANCE_LEVELS) / total
    if isinstance(probs, list) and len(probs) == n:
        total = sum(probs) or 1.0
        return sum(i / (n - 1) * p for i, p in enumerate(probs)) / total
    score = answer.get("score")
    if isinstance(score, str) and score in IMPORTANCE_LEVELS:
        return IMPORTANCE_LEVELS.index(score) / (n - 1)
    if isinstance(score, (int, float)):
        return max(0.0, min(1.0, float(score) / (n - 1)))
    return 0.5


class LayaClassifier(Classifier):
    def __init__(self, settings):
        super().__init__(settings)
        self.api_key = env("LAYA_API_KEY")
        if not self.api_key:
            raise RuntimeError("LAYA_API_KEY 가 설정되지 않음")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.api_key}"

    def _questions(self) -> dict:
        return {
            "topic": {"type": "choice", "instructions": TOPIC_INSTRUCTIONS, "criteria": dict(self.topics)},
            "importance": {"type": "score", "instructions": IMPORTANCE_INSTRUCTIONS, "criteria": IMPORTANCE_LEVELS},
        }

    def _base_body(self) -> dict:
        body = {"questions": self._questions()}
        if self.settings.classify.laya_model:
            body["model"] = self.settings.classify.laya_model
        return body

    def _post(self, path: str, body: dict) -> dict:
        for attempt in range(3):
            resp = self.session.post(f"{API_BASE}{path}", json=body, timeout=60)
            if resp.status_code == 503 and attempt < 2:
                time.sleep(float(resp.headers.get("Retry-After", 2 ** attempt)))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("Laya 응답 없음")

    @staticmethod
    def _state(a: Article) -> str:
        return f"{a.title}\n{a.summary}"[:STATE_MAX_CHARS]

    def _classify_batch(self, chunk: list[Article]) -> list[dict]:
        """배치 엔드포인트를 쓰고, 응답 형식을 해석하지 못하면 단건 호출로 대체한다."""
        try:
            data = self._post("/systemone/batch", {**self._base_body(), "states": [self._state(a) for a in chunk]})
            results = data if isinstance(data, list) else next(
                (data[k] for k in ("results", "responses", "items", "outputs") if isinstance(data.get(k), list)), None
            )
            if results is not None and len(results) == len(chunk):
                return results
            log.warning("Laya 배치 응답 형식을 해석하지 못해 단건 호출로 전환")
        except requests.HTTPError as e:
            log.warning("Laya 배치 실패(%s), 단건 호출로 전환", e)
        return [self._post("/systemone", {**self._base_body(), "state": self._state(a)}) for a in chunk]

    def _to_result(self, a: Article, result: dict) -> ClassifiedArticle:
        answers = result.get("answers", result)
        topic_ans = answers.get("topic", {})
        topic = topic_ans.get("choice", "other")
        conf = topic_ans.get("answer_confidence")
        if topic not in self.topics or (conf is not None and conf < self.settings.classify.laya_min_confidence):
            topic = "other"
        importance = level_to_importance(answers.get("importance", {}))
        return ClassifiedArticle(article=a, topic=topic, importance=round(importance, 3))

    def classify(self, articles: list[Article]) -> list[ClassifiedArticle]:
        out: list[ClassifiedArticle] = []
        for i in range(0, len(articles), BATCH_SIZE):
            chunk = articles[i : i + BATCH_SIZE]
            out.extend(self._to_result(a, r) for a, r in zip(chunk, self._classify_batch(chunk)))
        log.info("Laya 분류 완료 %d건", len(out))
        return out
