"""블로그 아이콘·파비콘을 다시 만드는 스크립트 (그냥모아 글자 로고, 2026-11 확정안 4-A).

    python assets/brand/make_brand.py

- blog_icon.png : 티스토리 블로그 아이콘 (512x512, 크림 바탕에 남색 '모아' + 빨간 점)
- favicon.ico   : 티스토리 파비콘 (16·32·48·64px, 작은 크기에서도 읽히도록 '모' 한 글자 + 빨간 점)

글꼴은 OFL(무료 공개) 라이선스인 Noto Sans KR 가변 글꼴의 가장 굵은 두께(900)를 쓴다.
Windows 에 없으면 NOTO_SANS_KR 환경변수로 글꼴 파일 경로를 지정한다.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = os.environ.get("NOTO_SANS_KR", "C:/Windows/Fonts/NotoSansKR-VF.ttf")
S = 1024  # 크게 그린 뒤 줄여서 가장자리를 매끄럽게 한다
CREAM, NAVY, RED = (246, 241, 231), (19, 41, 75), (229, 72, 77)


def heavy(size: float) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FONT, int(size))
    f.set_variation_by_axes([900])
    return f


def draw_word(text: str, size: float, gap: float, cy: float) -> Image.Image:
    """글자를 하나씩 놓아 간격을 좁히고, 마침표처럼 기준선에 빨간 점을 찍는다."""
    img = Image.new("RGB", (S, S), CREAM)
    d = ImageDraw.Draw(img)
    f = heavy(size)
    boxes = [d.textbbox((0, 0), ch, font=f) for ch in text]
    widths = [b[2] - b[0] for b in boxes]
    top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
    dot = 0.2 * (bottom - top)
    total = sum(widths) + gap * (len(text) - 1) + gap * 0.9 + dot
    x, y = S / 2 - total / 2, cy - (bottom - top) / 2 - top
    for ch, b, w in zip(text, boxes, widths):
        d.text((x - b[0], y), ch, font=f, fill=NAVY)
        x += w + gap
    x += gap * 0.9 - gap
    d.ellipse([x, y + bottom - dot, x + dot, y + bottom], fill=RED)
    return img


def rounded(img: Image.Image, size: int) -> Image.Image:
    small = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size * 4 - 1, size * 4 - 1], radius=int(size * 4 * 0.22), fill=255)
    small.putalpha(mask.resize((size, size), Image.LANCZOS))
    return small


def main() -> None:
    icon = draw_word("모아", S * 0.36, -S * 0.012, S * 0.5)
    icon.resize((512, 512), Image.LANCZOS).save(HERE / "blog_icon.png")
    mark = draw_word("모", S * 0.56, 0, S * 0.52)
    frames = [rounded(mark, n) for n in (16, 32, 48, 64)]
    frames[-1].save(HERE / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)], append_images=frames[:-1])
    print(f"저장: {HERE / 'blog_icon.png'}, {HERE / 'favicon.ico'}")


if __name__ == "__main__":
    main()
