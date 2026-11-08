"""@the4pmrecap(영어 계정) 프로필 이미지. 한국 계정 "모아." 로고와 같은 방식: 굵은 고딕 + 마침표 점.

    python assets/brand/make_profile_en.py   # assets/brand/profile_en.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
OUT.mkdir(parents=True, exist_ok=True)
S = 1024
SANS = "C:/Windows/Fonts/NotoSansKR-VF.ttf"
CREAM, NAVY = (246, 241, 231), (19, 41, 75)
INK, WHITE, GREEN = (11, 13, 16), (255, 255, 255), (46, 230, 107)


def font(size, weight):
    f = ImageFont.truetype(SANS, int(size))
    f.set_variation_by_axes([weight])
    return f


def word(d, text, f, cx, cy, gap, color, dot=None):
    boxes = [d.textbbox((0, 0), ch, font=f) for ch in text]
    widths = [b[2] - b[0] for b in boxes]
    top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
    h = bottom - top
    dot_d = dot[0] * h if dot else 0
    total = sum(widths) + gap * (len(text) - 1) + (gap + S * 0.02 + dot_d if dot else 0)
    x, y = cx - total / 2, cy - h / 2 - top
    for ch, b, w in zip(text, boxes, widths):
        d.text((x - b[0], y), ch, font=f, fill=color)
        x += w + gap
    if dot:
        x += S * 0.02
        d.ellipse([x, y + bottom - dot_d, x + dot_d, y + bottom], fill=dot[1])
    return y + top, y + bottom


def make(bg, fg, dot_color, sub=None, name="x"):
    img = Image.new("RGB", (S, S), bg)
    d = ImageDraw.Draw(img)
    cy = S * 0.47 if sub else S * 0.5
    _, bottom = word(d, "4PM", font(S * 0.30, 900), S * 0.5, cy, -S * 0.01, fg, dot=(0.2, dot_color))
    if sub:
        f = font(S * 0.075, 800)
        w = d.textlength(sub, font=f)
        # 글자 사이를 벌려 작은 부제처럼
        spaced = " ".join(sub)
        w = d.textlength(spaced, font=f)
        d.text((S * 0.5 - w / 2, bottom + S * 0.05), spaced, font=f, fill=dot_color)
    img.save(OUT / f"{name}.png")


make(INK, WHITE, GREEN, name="profile_en")   # 영어 카드와 같은 검정 + 초록
