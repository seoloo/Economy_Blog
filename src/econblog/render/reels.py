"""인스타 릴스 영상: 그날 카드 내용으로 세로(9:16) 장면을 새로 그려 이어 붙이고 무료 음원을 깐다.

카드 10장을 줄여 넘기면 읽을 틈이 없다 (다른 경제 계정의 '시황 슬라이드쇼' 릴스는 반응이 가장 낮았다).
그래서 한 장면에 한 가지만 크게 보여 준다:
  1. 훅: 그날 가장 큰 움직임 두 줄 + 숫자 3개 (첫 1~2초에 멈추게)
  2. 숫자: 핵심 지표 4개
  3~4. 이슈 두 개: 제목 + 왜 중요한지 한 줄
  5. 다음에 볼 것: 체크리스트 3개
  6. 끝: 계정 이름
장면마다 천천히 확대되는 움직임을 주고, 짧게 겹쳐 넘긴다. 숫자는 모두 카드와 같은 데이터에서 온다.
ffmpeg 은 PATH 의 ffmpeg, 없으면 imageio-ffmpeg 이 들고 있는 실행 파일을 쓴다.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import date
from pathlib import Path

import requests
from pydantic import BaseModel

from econblog.config import CardAccount, MusicTrack, Settings

log = logging.getLogger(__name__)

W, H = 1080, 1920
FADE = 0.3
# 장면별 보여 주는 시간(초). 이슈는 제목과 이유 한 줄을 읽을 수 있게 길게.
SECONDS = {"hook": 2.5, "nums": 3.5, "story": 4.5, "next": 4.0, "end": 2.0}
# 어두운 배경 위에서 잘 보이는 등락 색
ON_DARK = {"ko": ("#ff6b6b", "#6ea8ff"), "en": ("#2ee66b", "#ff6b6b")}
END_TAG = {"ko": "화~토 아침, 밤사이 시장 정리", "en": "Every U.S. market close, recapped"}


class ReelFrame(BaseModel):
    slide: object        # render.cards.Slide (장면 내용)
    seconds: float


def ffmpeg_path() -> str | None:
    if p := shutil.which("ffmpeg"):
        return p
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- 장면 구성


def reel_frames(lang: str, slides: list) -> list[ReelFrame]:
    """캐러셀 카드(Slide 목록)에서 릴스 장면을 고른다. 카드에 없는 장면은 건너뛴다."""
    from econblog.render.cards import Slide

    by_kind = {}
    for s in slides:
        by_kind.setdefault(s.kind, []).append(s)
    frames: list[ReelFrame] = []
    if cover := (by_kind.get("cover") or [None])[0]:
        frames.append(ReelFrame(slide=Slide(kind="hook", kicker=cover.kicker, lines=cover.lines, chips=cover.chips,
                                            photo=cover.photo), seconds=SECONDS["hook"]))
    if board := (by_kind.get("board") or [None])[0]:
        chip_names = [c.n for c in (cover.chips if cover else [])]
        tiles = [t for t in board.tiles if t.n in chip_names] + [t for t in board.tiles if t.n not in chip_names]
        frames.append(ReelFrame(slide=Slide(kind="nums", kicker="숫자로 보면" if lang == "ko" else "BY THE NUMBERS",
                                            title=board.title, tiles=tiles[:4], source=board.source),
                                seconds=SECONDS["nums"]))
    for st in by_kind.get("story", [])[:2]:
        frames.append(ReelFrame(slide=Slide(kind="story", label=st.label, lines=st.lines, why=st.why, photo=st.photo),
                                seconds=SECONDS["story"]))
    if closing := (by_kind.get("closing") or [None])[0]:
        frames.append(ReelFrame(slide=Slide(kind="next", kicker=closing.kicker, title=closing.title,
                                            events=closing.events), seconds=SECONDS["next"]))
    frames.append(ReelFrame(slide=Slide(kind="end", title=END_TAG[lang]), seconds=SECONDS["end"]))
    return frames


def render_frames(settings: Settings, account: CardAccount, frames: list[ReelFrame], out_dir: Path) -> list[Path]:
    """장면을 1080x1920 JPEG 으로 찍는다."""
    from econblog.render.cards import THEMES, _env, chrome_path, screenshot

    chrome = chrome_path()
    if not chrome:
        raise RuntimeError("Chrome 을 찾지 못해 릴스 장면을 찍지 못했습니다")
    up, down = ON_DARK[account.lang]
    theme = {**THEMES[account.lang], "brand": account.brand, "brand_dot": account.brand_dot,
             "up_on_dark": up, "down_on_dark": down}
    tpl = _env(settings).get_template("reel.html.j2")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, fr in enumerate(frames, 1):
        html = out_dir / f"reel_{i:02d}.html"
        html.write_text(tpl.render(t=theme, s=fr.slide), encoding="utf-8")
        jpg = html.with_suffix(".jpg")
        screenshot(chrome, html, jpg, size=(W, H))
        paths.append(jpg)
    return paths


# ---------------------------------------------------------------- 음악


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


# ---------------------------------------------------------------- 영상


def reel_length(durations: list[float], fade: float = FADE) -> float:
    return sum(durations) - (len(durations) - 1) * fade


def build_command(ffmpeg: str, images: list[Path], durations: list[float], music: Path | None, out: Path,
                  fade: float = FADE, volume: float = 0.8, zoom: float = 0.05) -> list[str]:
    """장면마다 천천히 확대(최대 zoom)하고 fade 초씩 겹쳐 넘긴다."""
    n = len(images)
    total = reel_length(durations, fade)
    args = [ffmpeg, "-y", "-loglevel", "error"]
    for img, d in zip(images, durations):
        args += ["-loop", "1", "-framerate", "30", "-t", f"{d}", "-i", str(img)]
    if music:
        args += ["-i", str(music)]
    parts = []
    for i, d in enumerate(durations):
        step = zoom / max(d * 30, 1)
        parts.append(f"[{i}:v]scale={int(W * 1.1)}:{int(H * 1.1)}:out_range=tv,"
                     f"zoompan=z='min(1+{step:.6f}*on,{1 + zoom})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                     f":d=1:s={W}x{H}:fps=30,setsar=1,format=yuv420p[v{i}]")
    last, offset = "v0", 0.0
    for i in range(1, n):
        offset += durations[i - 1] - fade
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


def make_reel(images: list[Path], durations: list[float], music: Path | None, out: Path) -> Path:
    """장면 이미지로 릴스용 MP4 를 만든다. 인스타 릴스 규격: 9:16, H.264 + AAC, 30fps."""
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("ffmpeg 을 찾지 못해 릴스 영상을 만들지 못했습니다")
    if not images:
        raise ValueError("장면 이미지가 없음")
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(build_command(ffmpeg, images, durations, music, out), capture_output=True, text=True,
                          timeout=900)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"릴스 영상 만들기 실패: {proc.stderr[-400:]}")
    return out


def build_reel(settings: Settings, account: CardAccount, slides: list, card_dir: Path, run_date: date,
               offline: bool = False) -> tuple[Path, MusicTrack | None]:
    """그날 카드 내용으로 릴스 영상을 만든다. (영상 경로, 쓴 곡)."""
    frames = reel_frames(account.lang, slides)
    images = render_frames(settings, account, frames, card_dir / "reel")
    track = None if offline else pick_track(settings, run_date, account)
    music = fetch_track(track, card_dir / "reel_music.mp3") if track else None
    out = make_reel(images, [f.seconds for f in frames], music, card_dir / "reel.mp4")
    if music:
        music.unlink(missing_ok=True)   # 음원 파일은 남기지 않는다 (artifact·메일로 퍼지지 않게)
    return out, track if music else None
