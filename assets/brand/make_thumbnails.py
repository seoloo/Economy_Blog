"""카테고리별 대표 이미지(썸네일)를 다시 만드는 스크립트 (2026-11 확정안 B: 하단 제목).

    python assets/brand/make_thumbnails.py

캐릭터 그림(character.png)은 그대로 두고, 아래쪽에 카테고리 색 그라데이션과 큰 제목을 얹는다.
결과는 1200x900 JPEG 이며, 티스토리 목록처럼 정사각형으로 잘려도 제목이 가운데에 남는다.

- thumb_market.jpg   : 시황 (시황 글에 자동으로 들어감)
- thumb_study.jpg    : 경제 공부 (경제 공부 글에 자동으로 들어감)
- thumb_issue.jpg    : 시사 (직접 쓰는 글용)
- thumb_politics.jpg : 정치 (직접 쓰는 글용. 정당을 떠올리게 하는 빨강·파랑은 피한다)

카테고리를 늘리려면 CATS 에 한 줄을 추가한다.
글자는 SVG 로 그려 Chrome 으로 찍는다. 글꼴은 Noto Sans KR(OFL)이 설치돼 있어야 하고,
Chrome 경로가 다르면 CHROME 환경변수로 지정한다.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CHARACTER = HERE / "character.png"
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
W, H = 1448, 1086           # 캐릭터 그림 원본 크기 (좌표 기준)
OUT_W, OUT_H = 1200, 900
RED = "#e5484d"
FONT = "'Noto Sans KR', 'Malgun Gothic', sans-serif"

# key: (제목, 부제, 기본색, 그라데이션 색, 밑줄 색, 제목 끝 점 색)
CATS = {
    "market": ("오늘의 시황", "미국증시·코스피, 아침에 한눈에", "#13294b", "#0b1733", "#f2b33d", RED),
    "study": ("경제 공부", "어려운 경제, 쉽게 풀어 드립니다", "#1f6f54", "#0f3b2c", "#ffd166", RED),
    "issue": ("시사 정리", "오늘 꼭 알아야 할 이슈만 골라서", "#d9480f", "#6b2205", "#fff3e0", "#ffffff"),
    "politics": ("정치 읽기", "쟁점만 차분하게 정리합니다", "#3b3f4a", "#1d2027", "#e8c46a", RED),
}


def svg(title: str, sub: str, color: str, dark: str, accent: str, dot: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{OUT_W}" height="{OUT_H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{dark}" stop-opacity="0"/>
      <stop offset="0.45" stop-color="{dark}" stop-opacity="0.82"/>
      <stop offset="1" stop-color="{dark}" stop-opacity="0.97"/>
    </linearGradient>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="5"/><feOffset dy="4" result="o"/>
      <feFlood flood-color="#000000" flood-opacity="0.45"/><feComposite in2="o" operator="in" result="s"/>
      <feMerge><feMergeNode in="s"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <image href="{CHARACTER.as_uri()}" x="0" y="0" width="{W}" height="{H}"/>
  <rect x="0" y="660" width="{W}" height="{H - 660}" fill="url(#fade)"/>
  <rect x="0" y="0" width="{W}" height="14" fill="{color}"/>
  <g font-family="{FONT}" text-anchor="middle">
    <text x="{W / 2}" y="74" font-size="30" font-weight="800" fill="#ffffff" filter="url(#soft)">그냥모아<tspan fill="{RED}">.</tspan></text>
    <text x="{W / 2}" y="950" font-size="112" font-weight="900" fill="#ffffff" letter-spacing="-3">{title}<tspan fill="{dot}">.</tspan></text>
    <rect x="{W / 2 - 60}" y="978" width="120" height="8" rx="4" fill="{accent}"/>
    <text x="{W / 2}" y="1040" font-size="36" font-weight="500" fill="#ffffff" fill-opacity="0.9">{sub}</text>
  </g>
</svg>'''


def render(key: str, spec: tuple[str, ...], tmp: Path) -> Path:
    html = tmp / f"{key}.html"
    html.write_text('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;'
                    'overflow:hidden}svg{display:block}</style></head><body>' + svg(*spec) + "</body></html>",
                    encoding="utf-8")
    png = tmp / f"{key}.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    f"--window-size={OUT_W},{OUT_H}", f"--screenshot={png}", html.as_uri()],
                   capture_output=True, check=True)
    out = HERE / f"thumb_{key}.jpg"
    with Image.open(png) as im:
        im.convert("RGB").save(out, "JPEG", quality=92, optimize=True, progressive=True)
    return out


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        for key, spec in CATS.items():
            print(render(key, spec, Path(d)))


if __name__ == "__main__":
    main()
