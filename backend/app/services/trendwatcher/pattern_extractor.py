"""Deep pattern extraction from viral trends.

Pipeline per trend:
  1. Best path — multimodal: yt-dlp downloads the video → ffmpeg extracts 6 evenly-spaced
     keyframes (scaled 540w jpeg) → Opus 4.8 reads frames + transcript and returns
     structured pattern (character incl. hat/clothing/gender, app UI text overlays, CTA).
  2. Fallback path — transcript only:
     - YouTube → youtube-transcript-api (free captions)
     - TikTok/Instagram → yt-dlp audio + Whisper
     - Final fallback: title + description
  3. Save as TrendPattern row.
"""
import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.ai_orchestrator.llm_client import LLMClient
from app.models.trend import Trend
from app.models.trend_pattern import TrendPattern


SYSTEM_PROMPT = """You analyse viral short-form videos and extract their structural pattern.
Your output must be a single JSON object with the schema below. Be specific and concrete.
Never hallucinate — if a field cannot be inferred, set it to null or [].

Schema:
{
  "hook": str,                    // First 3-5 seconds — the opening phrase or visual gimmick
  "story_beats": [                // Timeline of what happens, max 8 beats
    {"start": float, "end": float, "what_happens": str, "emotion": str}
  ],
  "characters": [                 // Speakers / on-screen figures, max 4
    {"role": str, "gender": "male"|"female"|"unknown", "age_range": str, "appearance": str, "voice_tone": str}
  ],
  "title_formula": str,           // Template with {placeholders}, e.g. "POV: I tried {app} and {result}"
  "cta_structure": null | {       // ONLY if this is an app/product ad; otherwise null
    "app_name": str | null,
    "cta_phrase": str,            // e.g. "download in bio", "use code XXX"
    "position": "voiceover"|"caption"|"end_card"|"throughout"
  },
  "visual_style": {
    "lighting": str,              // e.g. "warm evening", "neon nightclub", "natural daylight"
    "location": str,              // e.g. "cozy bedroom", "outdoor cafe", "office desk"
    "framing": str,               // e.g. "selfie POV", "tripod static", "handheld dynamic"
    "color_palette": str          // dominant colors
  },
  "viral_mechanic": str,          // one of: "pov_story", "soulmate_sketch", "before_after", "tutorial", "list", "skit", "reveal", "other"
  "adaptation_brief": str,        // 2-3 sentences. Ready-to-use synopsis for AI-video generation (translate to English).
  "anchor_prompt": str,           // ANCHOR portion: style/setting/character base, English. Visual anchor that stays constant.
  "character_card": str           // <= 50 words English describing the main heroine/hero: appearance, age, clothing, vibe.
}

Rules:
- Be cinema-literate: think in beats, not bullet points.
- For the soulmate_sketch / app_ad genre — extract the app_name carefully and the moment of reveal.
- title_formula should be reusable: put variable parts in curly braces.
- adaptation_brief / anchor_prompt / character_card must be in English (so the video provider works correctly).
"""


def get_youtube_transcript(url: str) -> tuple[Optional[str], str]:
    """Fetch YT transcript via youtube-transcript-api. Returns (text, source_tag)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None, "missing-pkg"

    # Extract video ID from URL
    video_id = None
    if "youtu" in url:
        if "shorts/" in url:
            video_id = url.split("shorts/")[-1].split("?")[0].split("/")[0]
        elif "watch?v=" in url:
            video_id = url.split("watch?v=")[-1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[-1].split("?")[0]

    if not video_id:
        return None, "no-video-id"

    try:
        api = YouTubeTranscriptApi()
        # Try multiple languages
        fetched = api.fetch(video_id, languages=["en", "ru", "es", "de", "ja", "pt", "hi"])
        text = " ".join(snippet.text for snippet in fetched.snippets)
        return text, "youtube-captions"
    except Exception as e:
        print(f"[PATTERN] YouTube transcript fetch failed for {video_id}: {e}")
        return None, "yt-error"


def download_video(url: str, out_dir: str) -> Optional[str]:
    """Use yt-dlp to download a TikTok/Instagram/YouTube video. Returns local file path."""
    out_template = os.path.join(out_dir, "video.%(ext)s")
    try:
        subprocess.run(
            ["yt-dlp", "-f", "b", "-o", out_template, "--no-warnings", "--no-playlist", url],
            capture_output=True, check=True, timeout=180,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[PATTERN] yt-dlp download failed: {e}")
        return None
    for ext in ("mp4", "webm", "mov", "mkv"):
        path = os.path.join(out_dir, f"video.{ext}")
        if os.path.exists(path):
            return path
    return None


def extract_keyframes(video_path: str, out_dir: str, count: int = 6) -> list[str]:
    """Extract `count` evenly-spaced JPEG keyframes (scaled to 540 wide) from a video."""
    duration = _probe_duration(video_path)
    if not duration or duration <= 0:
        return []
    step = duration / (count + 1)
    paths: list[str] = []
    for i in range(1, count + 1):
        ts = step * i
        out = os.path.join(out_dir, f"frame_{i}.jpg")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", video_path,
                    "-frames:v", "1", "-q:v", "5", "-vf", "scale=540:-1",
                    "-update", "1", out,
                ],
                capture_output=True, check=True, timeout=30,
            )
            if os.path.exists(out) and os.path.getsize(out) > 1024:
                paths.append(out)
        except subprocess.CalledProcessError:
            continue
    return paths


def _probe_duration(video_path: str) -> Optional[float]:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path,
            ],
            text=True, timeout=15,
        ).strip()
        return float(out) if out else None
    except Exception:
        return None


def get_transcript_via_whisper(url: str) -> tuple[Optional[str], str]:
    """Download video audio via yt-dlp and transcribe with our local Whisper."""
    try:
        # Try yt-dlp to download the audio
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "audio.mp3")
            try:
                subprocess.run(
                    [
                        "yt-dlp", "-f", "bestaudio", "--extract-audio",
                        "--audio-format", "mp3", "-o", audio_path, url,
                    ],
                    capture_output=True, check=True, timeout=120,
                )
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                print(f"[PATTERN] yt-dlp not available or failed: {e}. Skipping Whisper transcription.")
                return None, "yt-dlp-missing"

            if not os.path.exists(audio_path):
                return None, "no-audio-file"

            from app.services.whisper_aligner import WhisperAligner
            from faster_whisper import WhisperModel
            from app.core.config import settings as st

            model = WhisperModel(st.WHISPER_MODEL, device=st.WHISPER_DEVICE, compute_type=st.WHISPER_COMPUTE_TYPE)
            segments, _ = model.transcribe(audio_path, beam_size=1)
            text = " ".join(seg.text.strip() for seg in segments)
            return text, "whisper"
    except Exception as e:
        print(f"[PATTERN] Whisper transcription error: {e}")
        return None, "whisper-error"


def get_transcript(trend: Trend) -> tuple[str, str]:
    """Try YouTube captions first, then Whisper, then fall back to title."""
    if trend.source == "youtube" and trend.url:
        text, tag = get_youtube_transcript(trend.url)
        if text:
            return text, tag

    if trend.source in ("tiktok", "instagram") and trend.url:
        text, tag = get_transcript_via_whisper(trend.url)
        if text:
            return text, tag

    # Fallback — title + description
    fallback = f"{trend.title}\n\n{trend.description or ''}".strip()
    return fallback, "title-only"


def build_user_prompt(trend: Trend, transcript: str) -> str:
    """Compose the LLM user prompt with all available trend context."""
    keywords_csv = ""
    if trend.keywords_json:
        try:
            kws = json.loads(trend.keywords_json)
            if isinstance(kws, list):
                keywords_csv = ", ".join(str(k) for k in kws[:10])
        except Exception:
            pass

    return (
        f"Source platform: {trend.source}\n"
        f"Region: {trend.region}\n"
        f"Niche: {trend.niche or 'unspecified'}\n"
        f"Title: {trend.title}\n"
        f"Hashtags: {keywords_csv}\n"
        f"View count: {trend.view_count or 'unknown'}\n"
        f"Duration: {trend.duration_sec or 'unknown'} seconds\n"
        f"Viral coefficient (views/subs): {trend.viral_coef or 'unknown'}\n"
        f"\n--- TRANSCRIPT ---\n{transcript[:4000]}\n"
    )


def extract_pattern(trend: Trend, db) -> TrendPattern:
    """Run full extraction with multimodal-first strategy:
      1. yt-dlp downloads the trend video
      2. ffmpeg extracts 6 keyframes
      3. Opus 4.8 sees frames + transcript → structured pattern (character, app UI, CTA)
      4. Fallback to transcript-only if download/frames fail
    """
    transcript, transcript_source = get_transcript(trend)

    llm = LLMClient()
    images_b64: list[str] = []
    used_source = transcript_source

    # Try multimodal path: download + keyframes
    try:
        with tempfile.TemporaryDirectory() as tmp:
            video_path = download_video(trend.url, tmp) if trend.url else None
            if video_path:
                frames = extract_keyframes(video_path, tmp, count=6)
                for f in frames:
                    with open(f, "rb") as fp:
                        images_b64.append(base64.b64encode(fp.read()).decode("ascii"))
                if images_b64:
                    used_source = "multimodal+" + transcript_source
                    print(f"[PATTERN] Multimodal: {len(images_b64)} keyframes for trend-{trend.id}")
    except Exception as e:
        print(f"[PATTERN] Multimodal prep failed: {e}. Continuing transcript-only.")

    user_prompt = build_user_prompt(trend, transcript)
    if images_b64:
        user_prompt += (
            "\n\nAttached: 6 evenly-spaced keyframes from the video. Describe ONLY what you see "
            "in the frames — gender, hair, hats/headwear, accessories, clothing, on-screen "
            "text overlays, smartphone screens, app UI, percentages, zodiac symbols. Do not "
            "guess what is not visible."
        )

    result = llm.generate_structured_output(
        SYSTEM_PROMPT, user_prompt, images_base64=images_b64 or None,
    )

    existing = db.query(TrendPattern).filter(TrendPattern.trend_id == trend.id).first()
    pattern = existing or TrendPattern(trend_id=trend.id)

    pattern.transcript = transcript[:8000] if transcript else None
    pattern.transcript_source = used_source
    pattern.hook = result.get("hook")
    pattern.story_beats_json = json.dumps(result.get("story_beats", []), ensure_ascii=False)
    pattern.characters_json = json.dumps(result.get("characters", []), ensure_ascii=False)
    pattern.title_formula = result.get("title_formula")
    pattern.cta_structure_json = json.dumps(result.get("cta_structure"), ensure_ascii=False) if result.get("cta_structure") else None
    pattern.visual_style_json = json.dumps(result.get("visual_style", {}), ensure_ascii=False)
    pattern.viral_mechanic = result.get("viral_mechanic")
    pattern.adaptation_brief = result.get("adaptation_brief")
    pattern.anchor_prompt = result.get("anchor_prompt")
    pattern.character_card = result.get("character_card")
    pattern.llm_model = getattr(llm, "model", None)

    if not existing:
        db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern
