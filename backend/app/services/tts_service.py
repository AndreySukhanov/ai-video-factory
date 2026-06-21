import json
import os
import subprocess
import uuid
from dataclasses import asdict
from pathlib import Path

from app.core.config import settings
from app.media.tts_provider_base import TTSProvider, TTSResult, WordTimestamp

GENERATED_TTS_DIR = Path(__file__).resolve().parents[2] / "static" / "generated" / "tts"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_provider(name: str | None = None, *, align: bool = True) -> TTSProvider:
    """Resolve a TTSProvider by name. Default: elevenlabs if configured, otherwise openai.

    When `align=True`, providers that don't return native word-timings (currently OpenAI)
    are wrapped in `AlignedTTSProvider` which runs Whisper forced alignment after synthesis.
    """
    resolved = (name or "").lower().strip()
    if not resolved:
        resolved = "elevenlabs" if settings.ELEVENLABS_API_KEY else "openai"

    if resolved == "elevenlabs":
        from app.media.tts_provider_elevenlabs import ElevenLabsTTS
        return ElevenLabsTTS()
    if resolved == "openai":
        from app.media.tts_provider_openai import OpenAITTS
        from app.media.tts_provider_aligned import AlignedTTSProvider
        inner = OpenAITTS()
        return AlignedTTSProvider(inner) if align else inner
    raise ValueError(f"Unknown TTS provider: {resolved}")


def synthesize(
    text: str,
    *,
    provider: str | None = None,
    voice_id: str | None = None,
    out_name: str | None = None,
) -> dict:
    """Generate TTS for `text`, write MP3 to /static/generated/tts/, return public URL + word timings.

    Returns:
        {
          "audio_url": "/static/generated/tts/<name>.mp3",
          "audio_path": "<absolute path>",
          "words": [{"word": str, "start": float, "end": float}, ...],
          "provider": "elevenlabs" | "openai",
          "duration_sec": float | None,
        }
    """
    if not text or not text.strip():
        raise ValueError("text is empty")

    _ensure_dir(GENERATED_TTS_DIR)

    p = get_provider(provider)
    result: TTSResult = p.generate(text.strip(), voice_id=voice_id)

    name = out_name or f"tts_{uuid.uuid4().hex[:12]}"
    audio_path = GENERATED_TTS_DIR / f"{name}.{result.audio_format}"
    audio_path.write_bytes(result.audio)

    duration = result.words[-1].end if result.words else _probe_audio_duration(audio_path)

    return {
        "audio_url": f"/static/generated/tts/{audio_path.name}",
        "audio_path": str(audio_path),
        "words": [asdict(w) for w in result.words],
        "provider": p.name,
        "duration_sec": duration,
    }


def mux_voiceover(
    video_path: str,
    voiceover_path: str,
    output_path: str,
    *,
    voiceover_volume: float = 1.0,
    mute_original: bool = True,
) -> bool:
    """Overlay a voiceover audio track on a video. By default mutes the original audio,
    since AI video providers (Veo/Seedance/etc.) bake speech into the video and TTS would
    play on top, producing double-voice. With mute_original=True the original audio is
    discarded and only the voiceover plays.

    Returns True on success.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"video not found: {video_path}")
    if not os.path.exists(voiceover_path):
        raise FileNotFoundError(f"voiceover not found: {voiceover_path}")

    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", voiceover_path]
    if mute_original:
        cmd.extend([
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
        ])
    else:
        cmd.extend([
            "-filter_complex",
            f"[0:a]volume=0.0[a0];[1:a]volume={voiceover_volume}[a1];[a0][a1]amix=inputs=2:duration=longest[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
        ])
    cmd.append(output_path)

    try:
        subprocess.run(cmd, capture_output=True, check=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[TTS_MUX] ffmpeg failed: {e.stderr[:500] if e.stderr else e}")
        return False


def words_to_json(words: list[WordTimestamp] | list[dict]) -> str:
    """Serialize word timings for DB storage. Accepts WordTimestamp instances or dicts."""
    if not words:
        return "[]"
    if isinstance(words[0], dict):
        return json.dumps(words, ensure_ascii=False)
    return json.dumps([asdict(w) for w in words], ensure_ascii=False)


def _probe_audio_duration(path: Path) -> float | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            text=True,
        )
        return float(out.strip())
    except Exception:
        return None
