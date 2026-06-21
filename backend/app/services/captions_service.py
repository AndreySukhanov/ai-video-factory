"""Captions burn-in service.

Takes a video + word-level timings (from TTS) and burns ASS subtitles directly
onto the video via FFmpeg. Two display modes:

  - "word_pop"     one word at a time, centered, big — classic TikTok style
  - "karaoke_line" 4-5 words per line, current word highlighted (sing-along)

Five visual styles: modern (white bold), neon (cyan-pink), bold (Impact),
minimal (thin white), cinematic (Georgia serif).
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

# ASS color helper: &HAABBGGRR (alpha-blue-green-red, little-endian)
def _ass_color(r: int, g: int, b: int, a: int = 0) -> str:
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"


STYLES = {
    "modern": {
        "fontname": "Arial",
        "fontsize": 56,
        "primary": _ass_color(255, 255, 255),
        "secondary": _ass_color(255, 213, 0),  # highlight (karaoke)
        "outline": _ass_color(0, 0, 0),
        "back": _ass_color(0, 0, 0, 0x80),
        "bold": 1,
        "border_w": 4,
        "shadow": 1,
        "alignment": 2,
        "margin_v": 220,
    },
    "neon": {
        "fontname": "Arial Black",
        "fontsize": 60,
        "primary": _ass_color(0, 255, 255),
        "secondary": _ass_color(255, 0, 200),
        "outline": _ass_color(120, 0, 200),
        "back": _ass_color(0, 0, 0, 0x80),
        "bold": 1,
        "border_w": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 240,
    },
    "bold": {
        "fontname": "Impact",
        "fontsize": 72,
        "primary": _ass_color(255, 255, 255),
        "secondary": _ass_color(255, 213, 0),
        "outline": _ass_color(0, 0, 0),
        "back": _ass_color(0, 0, 0, 0x80),
        "bold": 1,
        "border_w": 5,
        "shadow": 2,
        "alignment": 2,
        "margin_v": 220,
    },
    "minimal": {
        "fontname": "Helvetica",
        "fontsize": 42,
        "primary": _ass_color(255, 255, 255),
        "secondary": _ass_color(255, 213, 0),
        "outline": _ass_color(0, 0, 0),
        "back": _ass_color(0, 0, 0, 0x40),
        "bold": 0,
        "border_w": 2,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 180,
    },
    "cinematic": {
        "fontname": "Georgia",
        "fontsize": 46,
        "primary": _ass_color(255, 255, 204),
        "secondary": _ass_color(255, 213, 0),
        "outline": _ass_color(51, 51, 51),
        "back": _ass_color(0, 0, 0),
        "bold": 0,
        "border_w": 2,
        "shadow": 2,
        "alignment": 2,
        "margin_v": 200,
    },
}


def _format_ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _ass_header(style_key: str, video_w: int, video_h: int) -> str:
    s = STYLES.get(style_key, STYLES["modern"])
    return (
        "[Script Info]\n"
        "Title: Burned Captions\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_w}\n"
        f"PlayResY: {video_h}\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Caption,{s['fontname']},{s['fontsize']},{s['primary']},{s['secondary']},"
        f"{s['outline']},{s['back']},{s['bold']},0,0,0,100,100,0,0,1,{s['border_w']},"
        f"{s['shadow']},{s['alignment']},40,40,{s['margin_v']},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _ass_dialogue(start: float, end: float, text: str) -> str:
    return (
        f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Caption,,0,0,0,,{text}\n"
    )


def _create_word_pop_ass(words: list[dict], style: str, video_w: int, video_h: int) -> str:
    """One word at a time. Each word stays visible from word.start until next word.start
    (or word.end + 80ms for the last word). Slight \\fad for snap-pop effect."""
    out = [_ass_header(style, video_w, video_h)]
    n = len(words)
    for i, w in enumerate(words):
        start = float(w["start"])
        end = float(words[i + 1]["start"]) if i + 1 < n else float(w["end"]) + 0.08
        if end <= start:
            end = start + 0.1
        text = str(w["word"]).strip().upper().replace("{", "(").replace("}", ")")
        if not text:
            continue
        out.append(_ass_dialogue(start, end, f"{{\\fad(60,40)}}{text}"))
    return "".join(out)


def _chunk_words(words: list[dict], chunk_size: int = 5) -> Iterable[list[dict]]:
    for i in range(0, len(words), chunk_size):
        yield words[i : i + chunk_size]


def _create_karaoke_line_ass(words: list[dict], style: str, video_w: int, video_h: int) -> str:
    """4-5 words per line. Current word highlighted via \\k (karaoke).
    Uses ASS \\k tags: \\k<centiseconds> highlights the word for that duration."""
    out = [_ass_header(style, video_w, video_h)]
    for chunk in _chunk_words(words, chunk_size=5):
        if not chunk:
            continue
        start = float(chunk[0]["start"])
        end = float(chunk[-1]["end"]) + 0.1
        pieces = []
        for w in chunk:
            ws = float(w["start"])
            we = float(w["end"])
            dur_cs = max(1, int(round((we - ws) * 100)))
            text = str(w["word"]).strip().replace("{", "(").replace("}", ")")
            if not text:
                continue
            pieces.append(f"{{\\k{dur_cs}}}{text}")
        if not pieces:
            continue
        line = " ".join(pieces)
        out.append(_ass_dialogue(start, end, f"{{\\fad(80,80)}}{line}"))
    return "".join(out)


def _probe_resolution(video_path: str) -> tuple[int, int]:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                video_path,
            ],
            text=True, timeout=15,
        ).strip()
        w, h = out.split("x")
        return int(w), int(h)
    except Exception:
        return 720, 1280


def burn_captions(
    video_path: str,
    words: list[dict],
    output_path: str,
    *,
    style: str = "modern",
    mode: str = "word_pop",
) -> bool:
    """Burn ASS subtitles onto a video using word-level timings.

    Args:
        video_path: source video file
        words: list of {"word": str, "start": float, "end": float}
        output_path: destination file
        style: one of STYLES keys
        mode: "word_pop" | "karaoke_line"

    Returns True on success.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"video not found: {video_path}")
    if not words:
        raise ValueError("no word timings provided")

    video_w, video_h = _probe_resolution(video_path)
    if mode == "karaoke_line":
        ass_content = _create_karaoke_line_ass(words, style, video_w, video_h)
    else:
        ass_content = _create_word_pop_ass(words, style, video_w, video_h)

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".ass", delete=False) as f:
        ass_path = f.name
        f.write(ass_content)

    try:
        # FFmpeg subtitles filter requires forward slashes and escaped colons on Windows
        escaped = ass_path.replace("\\", "/").replace(":", r"\:")
        vf = f"ass='{escaped}'"

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "copy",
            output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, text=True, timeout=600)
            return True
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "")[:500]
            print(f"[CAPTIONS] ffmpeg failed: {stderr}")
            return False
    finally:
        try:
            Path(ass_path).unlink(missing_ok=True)
        except Exception:
            pass
