"""Deep pattern extraction from viral trends.

Pipeline per trend:
  1. Get transcript:
     - YouTube → youtube-transcript-api (free, official captions)
     - TikTok/Instagram → yt-dlp audio download → Whisper transcription (already in stack)
     - Fallback: use just title + description
  2. LLM call (structured JSON) extracts:
     - hook (first 3-5 sec)
     - story_beats (timeline)
     - characters (role / age / appearance)
     - title_formula (template with {placeholders})
     - cta_structure (for app ads)
     - visual_style
     - viral_mechanic (taxonomy)
     - adaptation_brief — ready-to-use idea for our generator
  3. Save as TrendPattern row.
"""
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


def get_transcript_via_whisper(url: str) -> tuple[Optional[str], str]:
    """Download video audio via yt-dlp and transcribe with our local Whisper.

    Note: This requires yt-dlp installed and Whisper model. Currently yt-dlp is NOT in
    requirements (we don't ship it yet). For Phase 2.0 this is a placeholder — falls back
    to title-only when yt-dlp is missing.
    """
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
    """Run full extraction: transcript → LLM → save TrendPattern. Upserts on (trend_id)."""
    transcript, source_tag = get_transcript(trend)

    llm = LLMClient()
    user_prompt = build_user_prompt(trend, transcript)
    result = llm.generate_structured_output(SYSTEM_PROMPT, user_prompt)

    existing = db.query(TrendPattern).filter(TrendPattern.trend_id == trend.id).first()
    pattern = existing or TrendPattern(trend_id=trend.id)

    pattern.transcript = transcript[:8000] if transcript else None
    pattern.transcript_source = source_tag
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
