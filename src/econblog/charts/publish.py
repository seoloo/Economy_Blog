"""차트 PNG 를 공개 GitHub 레포에 올리고 이미지 주소를 Chart.url 에 채운다.

티스토리 HTML 모드에 post.html 을 붙여넣을 때 이미지까지 한 번에 들어가려면 공개 주소가 필요하다.
메일 본문도 같은 주소를 써서, 메일 내용을 복사해 붙여넣어도 이미지가 깨지지 않는다.

설정(settings.yaml publish)과 CHARTS_REPO_TOKEN(대상 레포 Contents 쓰기 권한)이 없으면
아무것도 하지 않고, 본문에는 기존처럼 업로드 안내 상자가 들어간다.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import date

import requests

from econblog.config import Settings, env
from econblog.models import Chart

log = logging.getLogger(__name__)

API = "https://api.github.com"


def is_configured(settings: Settings) -> bool:
    return bool(settings.publish.repo and settings.publish.base_url and env("CHARTS_REPO_TOKEN"))


def _blob_sha(data: bytes) -> str:
    """GitHub 가 파일마다 주는 sha 와 같은 방식으로 계산한다 (같은 파일인지 비교용)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _upload(session: requests.Session, settings: Settings, path: str, data: bytes, message: str) -> None:
    cfg = settings.publish
    url = f"{API}/repos/{cfg.repo}/contents/{path}"
    current = session.get(url, params={"ref": cfg.branch}, timeout=30)
    body = {"message": message, "content": base64.b64encode(data).decode(), "branch": cfg.branch}
    if current.status_code == 200:
        sha = current.json()["sha"]
        if sha == _blob_sha(data):
            return  # 이미 같은 파일이 있다 (고정 썸네일, 같은 날 재실행)
        body["sha"] = sha  # 내용이 바뀌었으면 덮어쓴다
    resp = session.put(url, json=body, timeout=60)
    resp.raise_for_status()


def publish_charts(settings: Settings, charts: list[Chart], run_date: date, offline: bool = False) -> list[str]:
    """올린 차트에 url 을 채운다. 실패하면 경고 문구를 돌려주고 해당 차트는 안내 상자로 남긴다."""
    if offline or not is_configured(settings):
        return []
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {env('CHARTS_REPO_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    base = settings.publish.base_url.rstrip("/")
    failed: list[str] = []
    for chart in charts:
        folder = "shared" if chart.shared else run_date.isoformat()
        path = f"{folder}/{chart.path.name}"
        try:
            _upload(session, settings, path, chart.path.read_bytes(), f"{run_date} {chart.path.name}")
            chart.url = f"{base}/{path}"
        except Exception as e:  # noqa: BLE001
            log.warning("차트 업로드 실패 %s: %s", chart.key, e)
            failed.append(chart.path.name)
    log.info("차트 업로드 %d/%d개", len(charts) - len(failed), len(charts))
    return [f"차트 업로드 실패({', '.join(failed)}): 해당 이미지는 직접 올려야 합니다"] if failed else []
