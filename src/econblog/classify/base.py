from __future__ import annotations

from abc import ABC, abstractmethod

from econblog.config import Settings
from econblog.models import Article, ClassifiedArticle


class Classifier(ABC):
    """기사마다 주제(topic)와 중요도(0~1)를 매긴다. 중복 판정은 dedupe.py 가 담당한다."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def topics(self) -> dict[str, str]:
        return self.settings.classify.topics

    @abstractmethod
    def classify(self, articles: list[Article]) -> list[ClassifiedArticle]:
        """입력과 같은 순서로 결과를 반환한다."""
