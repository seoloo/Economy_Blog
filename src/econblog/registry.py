"""구현체를 이름으로 찾는 지연 로딩 레지스트리.

각 단계 패키지의 __init__.py 가 {이름: "모듈경로:클래스명"} 을 등록한다.
무거운 의존성(yfinance, anthropic 등)은 실제로 쓰는 구현만 import 된다.
"""

from __future__ import annotations

import importlib
from typing import Any


def load(registry: dict[str, str], name: str) -> Any:
    try:
        target = registry[name]
    except KeyError as e:
        known = ", ".join(sorted(registry))
        raise ValueError(f"알 수 없는 구현 이름 '{name}' (사용 가능: {known})") from e
    module_path, _, attr = target.partition(":")
    return getattr(importlib.import_module(module_path), attr)
