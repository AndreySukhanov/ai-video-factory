"""Background music service.

Auto-discovers tracks in `backend/static/music/` (mp3/wav/m4a/ogg), reads optional
`manifest.json` for metadata overrides (display name, mood, credit), and mixes a
chosen track onto a video via FFmpeg `amix` with volume control and loop.

To add tracks: drop royalty-free files into `backend/static/music/`. Filename
convention `<mood>_<slug>.mp3` (e.g. `tense_chase.mp3`) is auto-parsed; override
in manifest.json for non-conforming names.

Lyria 3 Pro generation is planned for Phase 3.1 — out of scope here.
"""
import json
import os
import subprocess
from pathlib import Path

MUSIC_DIR = Path(__file__).resolve().parents[2] / "static" / "music"
MANIFEST_PATH = MUSIC_DIR / "manifest.json"
ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac"}


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return data.get("tracks", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def _probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            text=True, timeout=10,
        ).strip()
        return float(out) if out else None
    except Exception:
        return None


def _infer_mood_from_filename(filename: str) -> str:
    stem = Path(filename).stem.lower()
    parts = stem.replace("-", "_").split("_")
    return parts[0] if parts else "ambient"


def list_tracks(mood: str | None = None) -> list[dict]:
    """Discover tracks. Returns [{id, display_name, mood, url, duration_sec, credit?}]."""
    if not MUSIC_DIR.exists():
        return []

    manifest = _load_manifest()
    tracks = []
    for entry in sorted(MUSIC_DIR.iterdir()):
        if not entry.is_file() or entry.suffix.lower() not in ALLOWED_EXT:
            continue
        meta = manifest.get(entry.name, {}) if isinstance(manifest, dict) else {}
        track_mood = (meta.get("mood") or _infer_mood_from_filename(entry.name)).lower()
        if mood and track_mood != mood.lower():
            continue
        display = meta.get("display_name") or entry.stem.replace("_", " ").title()
        tracks.append({
            "id": entry.name,
            "display_name": display,
            "mood": track_mood,
            "url": f"/static/music/{entry.name}",
            "duration_sec": _probe_duration(entry),
            "credit": meta.get("credit"),
        })
    return tracks


def resolve_track_path(track_id: str) -> Path | None:
    """Resolve `track_id` (a filename) to absolute path. Rejects traversal."""
    safe = os.path.basename(track_id)
    if not safe:
        return None
    candidate = MUSIC_DIR / safe
    try:
        candidate.resolve().relative_to(MUSIC_DIR.resolve())
    except ValueError:
        return None
    if candidate.suffix.lower() not in ALLOWED_EXT or not candidate.is_file():
        return None
    return candidate


def add_music(
    video_path: str,
    music_path: str,
    output_path: str,
    *,
    music_volume: float = 0.15,
    loop_music: bool = True,
    fade_in: float = 1.0,
    fade_out: float = 1.5,
) -> bool:
    """Mix background music onto a video. Loops music to cover full video duration
    if `loop_music=True`. Original video audio (voiceover/diegetic) is preserved at
    full volume; music is added underneath at `music_volume` (default 15%)."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"video not found: {video_path}")
    if not os.path.exists(music_path):
        raise FileNotFoundError(f"music not found: {music_path}")

    video_dur = _probe_duration(Path(video_path)) or 30.0
    fade_out_start = max(0.0, video_dur - fade_out)

    music_input = ["-stream_loop", "-1", "-i", music_path] if loop_music else ["-i", music_path]

    filter_complex = (
        f"[1:a]volume={music_volume},"
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={fade_out_start}:d={fade_out}[music];"
        f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        *music_input,
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True, text=True, timeout=600)
        return True
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "")[:500]
        print(f"[MUSIC] ffmpeg mix failed: {stderr}")
        return False
