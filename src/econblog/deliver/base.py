from __future__ import annotations

from abc import ABC, abstractmethod

from econblog.config import Settings
from econblog.models import RenderedPost


class Deliverer(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings

    def is_configured(self) -> bool:
        """필요한 비밀값이 없으면 False. 파이프라인은 건너뛰고 계속 진행한다."""
        return True

    @abstractmethod
    def deliver(self, post: RenderedPost) -> str:
        """결과를 전달하고 사람이 읽을 한 줄 요약을 반환한다."""
