"""인스타 릴스 영상: 카드 JPEG 을 세로(9:16) 영상으로 이어 붙이고 무료 음원을 깐다.

카드(1080x1350)를 1080x1920 화면 가운데에 두고 위아래는 계정 테마 색으로 채운다.
장마다 몇 초씩 보여 주고 짧게 겹쳐 넘긴다. 음악은 영상 길이에 맞춰 자르고 앞뒤를 줄여 들어간다.
ffmpeg 은 PATH 의 ffmpeg, 없으면 imageio-ffmpeg 이 들고 있는 실행 파일을 쓴다.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import requests

from econblog.config import CardAccount, MusicTrack, Settings

log = logging.getLogger(__name__)

W, H = 1080, 1920
CARD_H = 1350


def ffmpeg_path() -> str | None:
    if p := shutil.which("ffmpeg"):
        return p
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def reel_length(n: int, seconds: float, fade: float) -> float:
    return n * seconds - (n - 1) * fade


def build_command(ffmpeg: str, images: list[Path], music: Path | None, out: Path, bg: str = "#0b0d10",
                  seconds: float = 3.0, fade: float = 0.3, volume: float = 0.8) -> list[str]:
    n = len(images)
    total = reel_length(n, seconds, fade)
    args = [ffmpeg, "-y", "-loglevel", "error"]
    for img in images:
        args += ["-loop", "1", "-t", f"{seconds}", "-i", str(img)]
    if music:
        args += ["-i", str(music)]
    color = bg.lstrip("#")
    top = (H - CARD_H) // 2
    parts = [f"[{i}:v]scale={W}:{CARD_H}:out_range=tv,pad={W}:{H}:0:{top}:color=0x{color},setsar=1,fps=30,format=yuv420p[v{i}]"
             for i in range(n)]
    last = "v0"
    for i in range(1, n):
        offset = i * (seconds - fade)
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[x{i}]")
        last = f"x{i}"
    if music:
        parts.append(f"[{n}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.5,"
                     f"afade=t=out:st={max(total - 1.5, 0):.3f}:d=1.5,volume={volume}[a]")
    args += ["-filter_complex", ";".join(parts), "-map", f"[{last}]"]
    if music:
        args += ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    args += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
             "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
    return args


def pick_track(settings: Settings, run_date: date, account: CardAccount) -> MusicTrack | None:
    """날짜마다 다음 곡으로 넘어간다. 두 계정이 같은 날 같은 곡을 쓰지 않게 계정 순서만큼 밀어 준다."""
    tracks = settings.instagram.reels.music
    if not tracks:
        return None
    shift = [a.key for a in settings.instagram.accounts].index(account.key) if account in settings.instagram.accounts else 0
    return tracks[(run_date.toordinal() + shift) % len(tracks)]


def fetch_track(track: MusicTrack, out: Path) -> Path | None:
    """곡을 내려받는다. 실패하면 None (음악 없이 영상을 만든다)."""
    try:
        resp = requests.get(track.url, timeout=60, headers={"User-Agent": "Mozilla/5.0 (econblog reels)"})
        resp.raise_for_status()
        if not resp.content.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
            raise ValueError("MP3 가 아님")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(resp.content)
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("릴스 음악 내려받기 실패 (%s): %s", track.title, e)
        return None


def reel_cover(card_dir: Path, chrome: str | None) -> Path | None:
    """표지(01.html)에서 '넘겨 보기/Swipe' 글자를 뺀 릴스용 표지를 찍는다. 릴스는 저절로 넘어가므로."""
    from econblog.render.cards import screenshot

    html = card_dir / "01.html"
    if not chrome or not html.exists():
        return None
    reel_html = card_dir / "reel_cover.html"
    reel_html.write_text(re.sub(r'<div class="swipe">.*?</div>', "", html.read_text(encoding="utf-8")), encoding="utf-8")
    out = card_dir / "reel_cover.jpg"
    screenshot(chrome, reel_html, out)
    return out


def build_reel(settings: Settings, account: CardAccount, images: list[Path], card_dir: Path, run_date: date,
               bg: str, offline: bool = False) -> tuple[Path, MusicTrack | None]:
    """그날 카드로 릴스 영상을 만든다. (영상 경로, 쓴 곡)."""
    from econblog.render.cards import chrome_path

    cover = reel_cover(card_dir, chrome_path())
    frames = [cover, *images[1:]] if cover else list(images)
    track = None if offline else pick_track(settings, run_date, account)
    music = fetch_track(track, card_dir / "reel_music.mp3") if track else None
    out = make_reel(frames, music, card_dir / "reel.mp4", bg=bg, seconds=settings.instagram.reels.seconds)
    if music:
        music.unlink(missing_ok=True)   # 음원 파일은 남기지 않는다 (artifact·메일로 퍼지지 않게)
    return out, track if music else None


def make_reel(images: list[Path], music: Path | None, out: Path, bg: str = "#0b0d10", seconds: float = 3.0) -> Path:
    """카드 이미지로 릴스용 MP4 를 만든다. 인스타 릴스 규격: 9:16, H.264 + AAC, 30fps."""
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("ffmpeg 을 찾지 못해 릴스 영상을 만들지 못했습니다")
    if not images:
        raise ValueError("카드 이미지가 없음")
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(build_command(ffmpeg, images, music, out, bg=bg, seconds=seconds),
                          capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"릴스 영상 만들기 실패: {proc.stderr[-400:]}")
    return out
