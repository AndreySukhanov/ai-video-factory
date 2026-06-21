"""Per-trend clone folder: organise extracted pattern, brief, transcript and (later)
generated videos in a single dir per trend.

Layout: backend/static/clones/trend-{id}/
  pattern.json         — TrendPattern as JSON
  brief.json           — clone-brief response (the wizard prefill)
  transcript.txt       — raw transcript used by LLM
  original_meta.json   — title / url / source / metrics from Trend row
  generated.mp4        — final stitched video, written by generation flow
  episodes/episode-N.mp4 — per-episode outputs

This module owns the directory + JSON writes. Video copying into the folder happens
later from the generation pipeline (link_generated_video).
"""
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from app.models.trend import Trend
from app.models.trend_pattern import TrendPattern

CLONES_ROOT = Path(__file__).resolve().parents[3] / "static" / "clones"


def folder_for_trend(trend_id: int) -> Path:
    return CLONES_ROOT / f"trend-{trend_id}"


def url_for_trend(trend_id: int) -> str:
    """Public URL prefix for browsing the trend clone folder via /static."""
    return f"/static/clones/trend-{trend_id}"


def save_pattern_artifacts(trend: Trend, pattern: TrendPattern, brief: dict) -> str:
    """Write pattern.json + brief.json + transcript.txt + original_meta.json into the
    trend's clone folder. Returns the folder URL.
    """
    folder = folder_for_trend(trend.id)
    folder.mkdir(parents=True, exist_ok=True)

    pattern_dict = {
        "id": pattern.id,
        "trend_id": pattern.trend_id,
        "transcript_source": pattern.transcript_source,
        "hook": pattern.hook,
        "story_beats": _safe_json(pattern.story_beats_json),
        "characters": _safe_json(pattern.characters_json),
        "title_formula": pattern.title_formula,
        "cta_structure": _safe_json(pattern.cta_structure_json),
        "visual_style": _safe_json(pattern.visual_style_json),
        "viral_mechanic": pattern.viral_mechanic,
        "adaptation_brief": pattern.adaptation_brief,
        "anchor_prompt": pattern.anchor_prompt,
        "character_card": pattern.character_card,
        "llm_model": pattern.llm_model,
        "extracted_at": pattern.extracted_at.isoformat() if pattern.extracted_at else None,
    }
    (folder / "pattern.json").write_text(
        json.dumps(pattern_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (folder / "brief.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if pattern.transcript:
        (folder / "transcript.txt").write_text(pattern.transcript, encoding="utf-8")

    original = {
        "trend_id": trend.id,
        "source": trend.source,
        "title": trend.title,
        "url": trend.url,
        "region": trend.region,
        "niche": trend.niche,
        "view_count": trend.view_count,
        "viral_coef": trend.viral_coef,
        "published_at": trend.published_at.isoformat() if trend.published_at else None,
        "thumbnail_url": trend.thumbnail_url,
    }
    (folder / "original_meta.json").write_text(
        json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Plain link to the original video — both as raw URL (.url) and a redirect HTML
    if trend.url:
        # Windows-style URL shortcut
        (folder / "original.url").write_text(
            f"[InternetShortcut]\nURL={trend.url}\n", encoding="utf-8"
        )
        # HTML redirect — works in any browser
        title_safe = (trend.title or "").replace("<", "&lt;").replace(">", "&gt;")
        html = (
            "<!doctype html><html><head>"
            f"<meta charset='utf-8'>"
            f"<title>Original: {title_safe[:120]}</title>"
            f"<meta http-equiv='refresh' content='0; url={trend.url}'>"
            "</head><body>"
            f"<p>Redirecting to <a href='{trend.url}'>{title_safe}</a> on {trend.source}…</p>"
            "</body></html>"
        )
        (folder / "original.html").write_text(html, encoding="utf-8")

    return url_for_trend(trend.id)


def link_generated_video(trend_id: int, source_video_path: str, episode_paths: list[str] | None = None) -> str:
    """Copy final stitched video and per-episode files into the trend's clone folder.
    Called from the generation pipeline once a clone-trend's project finishes."""
    folder = folder_for_trend(trend_id)
    folder.mkdir(parents=True, exist_ok=True)

    if os.path.exists(source_video_path):
        shutil.copy2(source_video_path, folder / "generated.mp4")

    if episode_paths:
        ep_dir = folder / "episodes"
        ep_dir.mkdir(exist_ok=True)
        for i, p in enumerate(episode_paths, start=1):
            if os.path.exists(p):
                ext = Path(p).suffix or ".mp4"
                shutil.copy2(p, ep_dir / f"episode-{i}{ext}")

    return url_for_trend(trend_id)


def _safe_json(text: Optional[str]):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None
