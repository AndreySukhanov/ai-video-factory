"""
API for generating episodes from prompt and reference image.

Бизнес-логика вынесена в сервисный слой:
- генерация эпизода → app/services/episode_generation_service.py
- медиа-утилиты (catbox, base64, кроп, скачивание) → app/media/local_media.py
- схемы запроса/ответа генерации → app/schemas/episodes.py
"""
import os
import asyncio
import tempfile
import subprocess
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import requests

from app.core.config import settings
from app.core.security import is_safe_outbound_url
from app.media.character_generator import CharacterGenerator
from app.media.local_media import (
    allow_private_fetch as _allow_private_fetch,
    upload_to_catbox_from_url,
)
from app.ai_orchestrator.agents import get_story_generator
from app.schemas.episodes import EpisodeGenerateRequest, EpisodeGenerateResponse
from app.services.episode_generation_service import generate_episode_flow


def extract_character_name(description: str) -> str:
    """Extract character name from description (first word or name pattern)."""
    if not description:
        return "Main Character"

    # Try to find name pattern like "Maya Chen" or "Detective Maya"
    words = description.split()
    if len(words) >= 2:
        # Check if first two words look like a name (capitalized)
        if words[0][0].isupper() and words[1][0].isupper():
            return f"{words[0]} {words[1]}"

    # Return first word if it's capitalized
    if words and words[0][0].isupper():
        return words[0]

    return "Main Character"


router = APIRouter()


class MergeRequest(BaseModel):
    """Request body for merging videos"""
    video_urls: List[str] = Field(..., min_length=2, description="List of video URLs to merge")
    transition: str = Field(default="crossfade", description="Transition type: crossfade, fade, none")
    transition_duration: float = Field(default=0.5, ge=0.1, le=2.0, description="Transition duration in seconds")


class MergeResponse(BaseModel):
    """Response body for merge operation"""
    success: bool
    merged_video_url: Optional[str] = None
    total_duration: Optional[float] = None
    error: Optional[str] = None


@router.post("/generate", response_model=EpisodeGenerateResponse)
async def generate_episode(request: EpisodeGenerateRequest):
    """
    Generate a video episode from a text prompt and optional reference image.

    Вся логика — в episode_generation_service.generate_episode_flow.
    """
    return await generate_episode_flow(request)


@router.get("/status")
async def get_generation_status():
    """
    Get the current status of the video generation service.
    
    Returns the video models actually available given configured API keys.
    """
    # Map each selectable model to the API key that enables it
    available = []
    if settings.WAVESPEED_API_KEY:
        available.extend(["wavespeed", "wavespeed-standard", "wavespeed-v15"])
    if settings.LAOZHANG_API_KEY:
        available.extend(["laozhang"])
    if settings.VERTEX_PROJECT_ID and settings.VERTEX_SA_KEY_PATH:
        available.append("vertex")
    if settings.GEMINI_API_KEY:
        available.append("gemini")
    if settings.REPLICATE_API_TOKEN:
        available.extend(["minimax", "kling"])
    if settings.FAL_KEY or settings.VIDEO_API_KEY:
        available.append("pika")
    if not available:
        available.append("mock")

    return {
        "provider": available[0],            # primary (highest priority configured)
        "available_models": available,        # all models the user can actually pick
        "status": "ready",
        "supported_durations": [4, 6, 8],
        "supported_aspect_ratios": ["9:16", "16:9"],
        "model_restrictions": {},
    }


class ExtractFrameRequest(BaseModel):
    """Request for extracting last frame from video"""
    video_url: str = Field(..., description="URL of the video to extract frame from")


class ExtractFrameResponse(BaseModel):
    """Response with extracted frame URL"""
    success: bool
    frame_url: Optional[str] = None
    error: Optional[str] = None


@router.post("/extract-last-frame", response_model=ExtractFrameResponse)
async def extract_last_frame(request: ExtractFrameRequest):
    """
    Extract the last frame from a video and save it as an image.
    Used for episode continuity - generate next episode from where previous ended.
    """
    print(f"[DEBUG] Extracting last frame from: {request.video_url[:60]}...")

    def _extract_sync() -> ExtractFrameResponse:
        if not is_safe_outbound_url(request.video_url, allow_private=_allow_private_fetch(request.video_url)):
            return ExtractFrameResponse(success=False, error="Unsafe video URL")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = os.path.join(temp_dir, "video.mp4")
            response = requests.get(request.video_url, stream=True, timeout=120)
            response.raise_for_status()

            with open(video_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Get video duration
            probe_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
            probe_result = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
            duration = float(probe_result.stdout.strip()) if probe_result.stdout.strip() else 4.0

            # Extract last frame (0.1 sec before end to avoid black frames)
            last_frame_time = max(0, duration - 0.1)

            # Save to uploads directory
            frame_filename = f"frame_{uuid.uuid4().hex[:12]}.png"
            uploads_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "uploads",
            )
            os.makedirs(uploads_dir, exist_ok=True)
            frame_path = os.path.join(uploads_dir, frame_filename)

            # Extract frame with FFmpeg
            cmd = f'ffmpeg -y -ss {last_frame_time} -i "{video_path}" -vframes 1 -q:v 2 "{frame_path}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)

            if result.returncode != 0 or not os.path.exists(frame_path):
                print(f"[DEBUG] FFmpeg extract failed: {result.stderr[:200]}")
                return ExtractFrameResponse(success=False, error="Failed to extract frame")

            # Return URL
            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            frame_url = f"{base_url}/uploads/{frame_filename}"

            print(f"[DEBUG] Extracted frame: {frame_url}")
            return ExtractFrameResponse(success=True, frame_url=frame_url)

    try:
        return await asyncio.to_thread(_extract_sync)
    except Exception as e:
        print(f"[DEBUG] Extract frame error: {str(e)}")
        return ExtractFrameResponse(success=False, error=str(e))

class ExtendRequest(BaseModel):
    """Request for extending a video"""
    video_url: str = Field(..., description="URL of the video to extend")
    prompt: str = Field(default="Continue the scene with natural motion", description="Motion prompt for continuation")
    extensions_count: int = Field(default=1, ge=1, le=20, description="Number of 7s extensions (1-20)")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio")
    quality_mode: str = Field(default="fast", description="Quality mode: fast or standard")


class ExtendResponse(BaseModel):
    """Response for video extension"""
    success: bool
    extended_video_url: Optional[str] = None
    total_duration: Optional[float] = None
    segments_count: Optional[int] = None
    error: Optional[str] = None


@router.post("/extend", response_model=ExtendResponse)
async def extend_video(request: ExtendRequest):
    """
    Extend a video by generating continuation clips from the last frame.
    Each extension adds ~7 seconds. Max 20 extensions (148s total).
    Uses Veo 3.1 frame chaining (-fl model).
    """
    print(f"[EXTEND] Request: {request.extensions_count} extensions for {request.video_url[:60]}...")

    try:
        from app.media.video_extender import VeoVideoExtender
        extender = VeoVideoExtender()

        result = await asyncio.to_thread(
            extender.extend_video,
            video_url=request.video_url,
            prompt=request.prompt,
            extensions_count=request.extensions_count,
            aspect_ratio=request.aspect_ratio,
            quality_mode=request.quality_mode,
        )

        return ExtendResponse(
            success=True,
            extended_video_url=result["extended_video_url"],
            total_duration=result.get("total_duration"),
            segments_count=result.get("segments_count"),
        )
    except Exception as e:
        print(f"[EXTEND] Error: {str(e)}")
        return ExtendResponse(success=False, error=str(e))


class StoryboardRequest(BaseModel):
    """Request for generating storyboard keyframes"""
    anchor_prompt: str = Field(default="", description="Shared visual anchor (camera, character, setting)")
    character_card: str = Field(default="", description="Fixed character appearance (<=50 words)")
    episode_prompts: List[str] = Field(..., description="Visual prompts per episode (variable parts)")
    aspect_ratio: str = Field(default="9:16", description="Image aspect ratio")
    seed: Optional[int] = Field(default=None, description="Fixed seed for consistency (auto if None)")
    image_model: str = Field(default="gemini", description="Image provider: 'gemini' (Nano Banana $0.003), 'seedream' (Seedream 5.0), or 'flux' (FLUX Schnell $0.003)")
    reference_image_urls: List[str] = Field(default_factory=list, description="User-uploaded reference photos (character, location)")
    visual_audit: bool = Field(default=True, description="Run VLM consistency check after generation and auto-regenerate low-score frames")


class FrameAuditReport(BaseModel):
    index: int
    score: int
    mismatches: List[str] = []
    regenerated: bool = False


class StoryboardResponse(BaseModel):
    """Response with storyboard keyframe URLs"""
    success: bool
    keyframes: List[str] = Field(default_factory=list, description="Image URLs per episode")
    seed: Optional[int] = None
    audit: List[FrameAuditReport] = Field(default_factory=list, description="Per-frame VLM audit reports")
    error: Optional[str] = None


@router.post("/storyboard", response_model=StoryboardResponse)
async def generate_storyboard(request: StoryboardRequest):
    """
    Generate storyboard keyframes for episodes.
    Supports three providers: Gemini Flash (cheap), Seedream 4.5 (higher quality), FLUX Schnell (Replicate).
    """
    print(f"[STORYBOARD] Request: {len(request.episode_prompts)} frames, model={request.image_model}, seed={request.seed}")

    try:
        if request.image_model == "seedream":
            if not settings.LAOZHANG_API_KEY:
                return StoryboardResponse(success=False, error="LAOZHANG_API_KEY not configured (required for Seedream)")
            from app.media.image_provider_seedream import SeedreamImageProvider
            provider = SeedreamImageProvider()
        elif request.image_model == "flux":
            if not settings.REPLICATE_API_TOKEN:
                return StoryboardResponse(success=False, error="REPLICATE_API_TOKEN not configured (required for FLUX)")
            from app.media.image_provider_flux import FluxImageProvider
            provider = FluxImageProvider()
        else:
            if not settings.GEMINI_API_KEY:
                return StoryboardResponse(success=False, error="GEMINI_API_KEY not configured")
            from app.media.image_provider_gemini import GeminiImageProvider
            provider = GeminiImageProvider()

        import random
        seed = request.seed or random.randint(1, 999999)

        # Filter valid reference URLs
        valid_refs = [u for u in request.reference_image_urls if u and u.strip()]

        keyframes = await asyncio.to_thread(
            provider.generate_storyboard,
            anchor_prompt=request.anchor_prompt,
            episode_prompts=request.episode_prompts,
            aspect_ratio=request.aspect_ratio,
            seed=seed,
            character_card=request.character_card,
            reference_image_urls=valid_refs if valid_refs else None,
        )

        valid_count = sum(1 for k in keyframes if k)
        if valid_count == 0:
            return StoryboardResponse(
                success=False,
                keyframes=[],
                error=f"All {len(keyframes)} frames failed to generate. Try a different image model.",
            )

        # VLM consistency audit — flag, regen, re-audit, keep best
        audit_reports: List[FrameAuditReport] = []
        if request.visual_audit and request.character_card and settings.GEMINI_API_KEY:
            from app.ai_orchestrator.agents.visual_consistency_checker import get_visual_consistency_checker
            checker = get_visual_consistency_checker()
            reports = await asyncio.to_thread(
                checker.check_storyboard,
                keyframes,
                request.character_card,
            )
            for rep in reports:
                if not rep.needs_regen:
                    audit_reports.append(FrameAuditReport(
                        index=rep.index, score=rep.score, mismatches=rep.mismatches, regenerated=False,
                    ))
                    continue

                original_url = keyframes[rep.index]
                original_score = rep.score
                original_mismatches = rep.mismatches

                reinforcement = checker.build_reinforcement(original_mismatches)
                ep_prompt = request.episode_prompts[rep.index] if rep.index < len(request.episode_prompts) else ""
                regen_prompt = f"{ep_prompt}{reinforcement}"
                print(f"[STORYBOARD] Regenerating frame {rep.index + 1} due to score {original_score}")

                new_url = None
                try:
                    new_url = await asyncio.to_thread(
                        provider.generate_keyframe,
                        prompt=f"{request.character_card}. {request.anchor_prompt}. {regen_prompt}".strip(". "),
                        aspect_ratio=request.aspect_ratio,
                        seed=seed,
                    )
                except Exception as e:
                    print(f"[STORYBOARD] Regen failed for frame {rep.index + 1}: {e}")

                if not new_url:
                    audit_reports.append(FrameAuditReport(
                        index=rep.index, score=original_score, mismatches=original_mismatches, regenerated=False,
                    ))
                    continue

                # Re-audit the regenerated frame
                second = await asyncio.to_thread(checker.check_frame, new_url, request.character_card)
                if second is None:
                    # Re-audit failed — trust regen, keep new
                    keyframes[rep.index] = new_url
                    audit_reports.append(FrameAuditReport(
                        index=rep.index, score=original_score, mismatches=original_mismatches, regenerated=True,
                    ))
                    continue

                new_score = int(second.get("score", 0))
                new_mismatches = [str(m) for m in (second.get("mismatches") or []) if m]
                print(f"[STORYBOARD] Frame {rep.index + 1} regen score: {original_score} -> {new_score}")
                if new_score > original_score:
                    keyframes[rep.index] = new_url
                    audit_reports.append(FrameAuditReport(
                        index=rep.index, score=new_score, mismatches=new_mismatches, regenerated=True,
                    ))
                else:
                    # Rollback — regen made it worse or equal
                    print(f"[STORYBOARD] Frame {rep.index + 1} rollback: regen not better, keeping original")
                    keyframes[rep.index] = original_url
                    audit_reports.append(FrameAuditReport(
                        index=rep.index, score=original_score, mismatches=original_mismatches, regenerated=False,
                    ))

        return StoryboardResponse(
            success=True,
            keyframes=keyframes,
            seed=seed,
            audit=audit_reports,
        )
    except Exception as e:
        print(f"[STORYBOARD] Error: {str(e)}")
        return StoryboardResponse(success=False, error=str(e))


class StoryboardFrameRequest(BaseModel):
    """Request for regenerating a single storyboard frame"""
    anchor_prompt: str = Field(default="", description="Shared visual anchor")
    character_card: str = Field(default="", description="Fixed character appearance")
    episode_prompt: str = Field(..., description="Single episode visual prompt")
    aspect_ratio: str = Field(default="9:16")
    seed: Optional[int] = Field(default=None, description="Optional seed (random if None)")
    image_model: str = Field(default="gemini")
    reference_image_urls: List[str] = Field(default_factory=list)


class StoryboardFrameResponse(BaseModel):
    success: bool
    frame_url: Optional[str] = None
    seed: Optional[int] = None
    error: Optional[str] = None


@router.post("/storyboard/frame", response_model=StoryboardFrameResponse)
async def regenerate_storyboard_frame(request: StoryboardFrameRequest):
    """
    Regenerate a single storyboard keyframe (e.g. user wants to redo just one frame).
    Reuses the same provider as /storyboard but for a single prompt.
    """
    print(f"[STORYBOARD-FRAME] model={request.image_model}, seed={request.seed}")

    try:
        if request.image_model == "seedream":
            if not settings.LAOZHANG_API_KEY:
                return StoryboardFrameResponse(success=False, error="LAOZHANG_API_KEY not configured")
            from app.media.image_provider_seedream import SeedreamImageProvider
            provider = SeedreamImageProvider()
        elif request.image_model == "flux":
            if not settings.REPLICATE_API_TOKEN:
                return StoryboardFrameResponse(success=False, error="REPLICATE_API_TOKEN not configured")
            from app.media.image_provider_flux import FluxImageProvider
            provider = FluxImageProvider()
        else:
            if not settings.GEMINI_API_KEY:
                return StoryboardFrameResponse(success=False, error="GEMINI_API_KEY not configured")
            from app.media.image_provider_gemini import GeminiImageProvider
            provider = GeminiImageProvider()

        import random
        seed = request.seed or random.randint(1, 999999)
        valid_refs = [u for u in request.reference_image_urls if u and u.strip()]

        keyframes = await asyncio.to_thread(
            provider.generate_storyboard,
            anchor_prompt=request.anchor_prompt,
            episode_prompts=[request.episode_prompt],
            aspect_ratio=request.aspect_ratio,
            seed=seed,
            character_card=request.character_card,
            reference_image_urls=valid_refs if valid_refs else None,
        )

        if not keyframes or not keyframes[0]:
            return StoryboardFrameResponse(success=False, error="Frame generation failed", seed=seed)

        return StoryboardFrameResponse(success=True, frame_url=keyframes[0], seed=seed)
    except Exception as e:
        print(f"[STORYBOARD-FRAME] Error: {str(e)}")
        return StoryboardFrameResponse(success=False, error=str(e))


@router.post("/merge", response_model=MergeResponse)
async def merge_episodes(request: MergeRequest):
    """
    Merge multiple video episodes into a single video using simple concatenation.
    """
    print(f"[DEBUG MERGE] Starting merge with {len(request.video_urls)} videos")

    def _merge_sync() -> MergeResponse:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_files = []

            # Download all videos
            for i, url in enumerate(request.video_urls):
                video_path = os.path.join(temp_dir, f"video_{i}.mp4")

                print(f"[DEBUG MERGE] Downloading video {i}: {url[:60]}...")
                if not is_safe_outbound_url(url, allow_private=_allow_private_fetch(url)):
                    return MergeResponse(success=False, error=f"Unsafe video URL at index {i}")

                response = requests.get(url, stream=True, timeout=120)
                response.raise_for_status()

                with open(video_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"[DEBUG MERGE] Downloaded video {i}: {os.path.getsize(video_path)} bytes")
                video_files.append(video_path)

            output_filename = f"merged_{uuid.uuid4().hex[:8]}.mp4"
            # Use dynamic path that works both locally and in Docker
            static_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "static",
            )
            output_dir = os.path.join(static_dir, "merged")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)

            if len(video_files) == 1:
                import shutil
                shutil.copy(video_files[0], output_path)
            else:
                # Simple concat - no transitions
                concat_list_path = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for vf in video_files:
                        f.write(f"file '{vf}'\n")

                cmd = f'ffmpeg -y -f concat -safe 0 -i "{concat_list_path}" -c:v libx264 -preset fast -crf 23 -c:a aac "{output_path}"'

                print("[DEBUG MERGE] Running concat...")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    print(f"[DEBUG MERGE] Concat failed: {result.stderr[:300]}")
                    return MergeResponse(success=False, error=f"FFmpeg error: {result.stderr[:200]}")

            if not os.path.exists(output_path):
                return MergeResponse(success=False, error="Output file was not created")

            # Get duration
            probe_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{output_path}"'
            duration_result = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
            total_duration = float(duration_result.stdout.strip()) if duration_result.stdout.strip() else None

            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            merged_url = f"{base_url}/static/merged/{output_filename}"

            print(f"[DEBUG MERGE] Success! {merged_url}")
            return MergeResponse(success=True, merged_video_url=merged_url, total_duration=total_duration)

    try:
        return await asyncio.to_thread(_merge_sync)
    except requests.RequestException as e:
        return MergeResponse(success=False, error=f"Download failed: {str(e)}")
    except subprocess.TimeoutExpired:
        return MergeResponse(success=False, error="FFmpeg timeout")
    except Exception as e:
        print(f"[DEBUG MERGE] Error: {str(e)}")
        return MergeResponse(success=False, error=f"Merge failed: {str(e)}")


# ==================== SERIES GENERATION ====================

class SeriesGenerateRequest(BaseModel):
    """Request body for series generation"""
    idea: str = Field(..., min_length=10, max_length=1000, description="Main idea for the series")
    genre: str = Field(default="drama", description="Genre: drama, comedy, thriller, fantasy, romance, action")
    episodes_count: int = Field(default=5, ge=1, le=10, description="Number of episodes to generate")
    duration: int = Field(default=4, description="Duration per episode in seconds (4, 6, or 8)")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio")
    llm_model: Optional[str] = Field(default=None, description="LLM preset for prompt writer: 'deepseek' | 'opus' | 'opus-4.7' (None = auto)")


class EpisodePromptData(BaseModel):
    """Generated episode with prompt"""
    number: int
    title: str
    synopsis: str
    prompt: str
    anchor_prompt: Optional[str] = None
    variable_prompt: Optional[str] = None


class SeriesGenerateResponse(BaseModel):
    """Response body for series generation"""
    success: bool
    series_title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    character_card: Optional[str] = None
    voice_description: Optional[str] = None
    anchor_prompt: Optional[str] = None
    episodes: List[EpisodePromptData] = []
    error: Optional[str] = None


@router.post("/generate-series", response_model=SeriesGenerateResponse)
async def generate_series(request: SeriesGenerateRequest):
    """
    Generate a complete series structure from a single idea.
    
    Uses GPT to create:
    - Series title and logline
    - Episode titles and synopses
    - Detailed visual prompts for each episode
    
    The prompts can be reviewed/edited before generating videos.
    
    Args:
        request: SeriesGenerateRequest with idea, genre, episodes_count
        
    Returns:
        SeriesGenerateResponse with series structure and prompts
    """
    print(f"[SERIES GENERATOR] Request: idea={request.idea[:50]}..., genre={request.genre}, episodes={request.episodes_count}, llm={request.llm_model or 'auto'}")

    try:
        story_generator = get_story_generator(llm_preset=request.llm_model)

        series = story_generator.generate_series(
            idea=request.idea,
            genre=request.genre,
            episodes_count=request.episodes_count,
            duration=request.duration,
            aspect_ratio=request.aspect_ratio
        )
        
        # Convert to response format
        episodes = [
            EpisodePromptData(
                number=ep.number,
                title=ep.title,
                synopsis=ep.synopsis,
                prompt=ep.visual_prompt,
                anchor_prompt=ep.anchor_prompt or None,
                variable_prompt=ep.variable_prompt or None
            )
            for ep in series.episodes
        ]

        print(f"[SERIES GENERATOR] Generated series: {series.series_title} with {len(episodes)} episodes")

        return SeriesGenerateResponse(
            success=True,
            series_title=series.series_title,
            logline=series.logline,
            genre=series.genre,
            character_card=series.character_card or None,
            voice_description=series.voice_description or None,
            anchor_prompt=series.anchor_prompt or None,
            episodes=episodes
        )
        
    except Exception as e:
        print(f"[SERIES GENERATOR] Error: {str(e)}")
        return SeriesGenerateResponse(
            success=False,
            error=f"Series generation failed: {str(e)}"
        )


# ==================== CONSISTENT STORY GENERATION (Character Consistency) ====================

class ConsistentStoryRequest(BaseModel):
    """Request body for consistent story generation with character image"""
    idea: str = Field(..., min_length=10, max_length=1000, description="Main idea for the series")
    genre: str = Field(default="drama", description="Genre: drama, comedy, thriller, fantasy, romance, action")
    episodes_count: int = Field(default=5, ge=1, le=10, description="Number of episodes to generate")
    duration: int = Field(default=5, description="Duration per episode in seconds (5 or 10 for Kling)")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio")
    model: str = Field(default="kling", description="Video model (kling required for I2V)")


class ConsistentStoryResponse(BaseModel):
    """Response body for consistent story generation"""
    success: bool
    series_title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    character_name: Optional[str] = None
    character_description: Optional[str] = None
    character_image_url: Optional[str] = None  # Public catbox URL for Replicate
    episodes: List[EpisodePromptData] = []
    error: Optional[str] = None


@router.post("/generate-story-consistent", response_model=ConsistentStoryResponse)
async def generate_consistent_story(request: ConsistentStoryRequest):
    """
    Generate a story structure with a base character image for consistent multi-episode generation.

    This endpoint:
    1. Generates story structure via LLM (same as /generate-series)
    2. Extracts main character description
    3. Generates a base character image via T2I (fal.ai Instant Character)
    4. Uploads character image to catbox for Replicate access

    The character image serves as reference for I2V generation,
    ensuring the same character appears across all episodes.

    Args:
        request: ConsistentStoryRequest with idea, genre, episodes_count

    Returns:
        ConsistentStoryResponse with story structure + character image URL
    """
    print(f"[CONSISTENT STORY] Request: idea={request.idea[:50]}..., genre={request.genre}, episodes={request.episodes_count}")

    try:
        # 1. Generate story structure via LLM
        story_generator = get_story_generator()

        series = story_generator.generate_series(
            idea=request.idea,
            genre=request.genre,
            episodes_count=request.episodes_count,
            duration=request.duration,
            aspect_ratio=request.aspect_ratio
        )

        # 2. Get main character description from the series data
        # The story generator now includes main_character in SeriesStructure
        main_character = series.main_character or ""
        character_name = "Main Character"

        # If main_character is available from LLM, use it
        if main_character:
            character_name = extract_character_name(main_character)
        # Fallback: Try to extract from first episode prompt (character description is at the start)
        elif series.episodes and series.episodes[0].visual_prompt:
            first_prompt = series.episodes[0].visual_prompt
            # Character descriptions usually end with a comma after clothing description
            # Look for pattern like "Name, age, description... wearing..."
            parts = first_prompt.split(",")
            if len(parts) >= 3:
                # Take first 4-5 parts as character description
                main_character = ", ".join(parts[:min(5, len(parts))])
                character_name = extract_character_name(main_character)

        print(f"[CONSISTENT STORY] Extracted character: {character_name}")
        print(f"[CONSISTENT STORY] Character description: {main_character[:100]}...")

        # 3. Generate base character image via T2I
        character_image_url = None
        try:
            char_generator = CharacterGenerator()

            # Build style based on genre
            genre_styles = {
                "drama": "cinematic, dramatic lighting, emotional",
                "comedy": "bright, vibrant colors, expressive",
                "thriller": "moody, film noir, atmospheric",
                "fantasy": "magical, ethereal, vibrant",
                "romance": "soft, warm golden hour lighting, dreamy",
                "action": "dynamic, high contrast, intense",
                "horror": "dark, atmospheric, unsettling",
                "scifi": "futuristic, neon, sleek",
                "mystery": "shadowy, mysterious, intriguing",
                "melodrama": "dramatic, emotional, intense colors"
            }
            style = genre_styles.get(request.genre.lower(), "photorealistic, cinematic lighting")

            print(f"[CONSISTENT STORY] Generating character image with style: {style}")

            char_result = char_generator.generate_character(
                name=character_name,
                description=main_character,
                style=style,
                aspect_ratio=request.aspect_ratio
            )

            if char_result and char_result.get("image_url"):
                local_image_url = char_result["image_url"]
                print(f"[CONSISTENT STORY] Character image generated: {local_image_url}")

                # 4. Upload to catbox for external access (Replicate requirement)
                external_url = await upload_to_catbox_from_url(local_image_url)
                if external_url:
                    character_image_url = external_url
                    print(f"[CONSISTENT STORY] Character image uploaded to catbox: {character_image_url}")
                else:
                    # Fallback to original URL (may not work with Replicate)
                    character_image_url = local_image_url
                    print(f"[CONSISTENT STORY] Using original URL (catbox upload failed)")

        except Exception as e:
            print(f"[CONSISTENT STORY] Character image generation failed: {e}")
            # Continue without character image - will use text prompts only

        # 5. Convert episodes to response format
        episodes = [
            EpisodePromptData(
                number=ep.number,
                title=ep.title,
                synopsis=ep.synopsis,
                prompt=ep.visual_prompt
            )
            for ep in series.episodes
        ]

        print(f"[CONSISTENT STORY] Generated series: {series.series_title} with {len(episodes)} episodes")
        print(f"[CONSISTENT STORY] Character image URL: {character_image_url}")

        return ConsistentStoryResponse(
            success=True,
            series_title=series.series_title,
            logline=series.logline,
            genre=series.genre,
            character_name=character_name,
            character_description=main_character,
            character_image_url=character_image_url,
            episodes=episodes
        )

    except Exception as e:
        print(f"[CONSISTENT STORY] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return ConsistentStoryResponse(
            success=False,
            error=f"Consistent story generation failed: {str(e)}"
        )


# ─── TTS / Voiceover (Phase 1) ────────────────────────────────────────────────

class VoiceoverRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize")
    provider: Optional[str] = Field(None, description="elevenlabs | edge | openai (auto if omitted)")
    voice_id: Optional[str] = None
    episode_id: Optional[int] = Field(None, description="If set, save voiceover to this episode")
    video_url: Optional[str] = Field(None, description="If set, mux voiceover onto this video")
    mute_original: bool = Field(True, description="When muxing, mute the video's original audio")


class WordTimingDTO(BaseModel):
    word: str
    start: float
    end: float


class VoiceoverResponse(BaseModel):
    success: bool
    audio_url: Optional[str] = None
    words: List[WordTimingDTO] = []
    duration_sec: Optional[float] = None
    provider: Optional[str] = None
    video_with_voiceover_url: Optional[str] = None
    error: Optional[str] = None


@router.post("/voiceover", response_model=VoiceoverResponse)
async def generate_voiceover(request: VoiceoverRequest):
    """Synthesize voiceover for text, optionally mux onto a video and persist to an episode.

    Provider routing: if `provider` omitted, picks ElevenLabs when ELEVENLABS_API_KEY is set,
    otherwise falls back to Edge TTS (free, no key required, native word timings via
    WordBoundary events). OpenAI TTS is also available — pass `provider="openai"` to use
    it; word-level alignment is added afterwards via Whisper forced alignment.
    """
    from app.services import tts_service
    from app.core.db import SessionLocal
    from app.models.episode import Episode

    def _run() -> VoiceoverResponse:
        try:
            tts = tts_service.synthesize(
                request.text,
                provider=request.provider,
                voice_id=request.voice_id,
            )
        except Exception as e:
            return VoiceoverResponse(success=False, error=f"TTS synthesis failed: {e}")

        video_with_url: Optional[str] = None
        if request.video_url:
            if not is_safe_outbound_url(request.video_url, allow_private=_allow_private_fetch(request.video_url)):
                return VoiceoverResponse(success=False, error="Unsafe video_url", audio_url=tts["audio_url"], words=tts["words"], provider=tts["provider"])

            with tempfile.TemporaryDirectory() as tmp:
                src_video = os.path.join(tmp, "src.mp4")
                resp = requests.get(request.video_url, stream=True, timeout=120)
                resp.raise_for_status()
                with open(src_video, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                out_name = f"voiced_{uuid.uuid4().hex[:10]}.mp4"
                static_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                    "static",
                )
                out_dir = os.path.join(static_dir, "generated", "voiced")
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, out_name)

                ok = tts_service.mux_voiceover(
                    src_video, tts["audio_path"], out_path,
                    mute_original=request.mute_original,
                )
                if not ok:
                    return VoiceoverResponse(
                        success=False,
                        audio_url=tts["audio_url"],
                        words=tts["words"],
                        provider=tts["provider"],
                        duration_sec=tts["duration_sec"],
                        error="FFmpeg mux failed",
                    )

                base_url = settings.BACKEND_URL or os.getenv("BACKEND_URL", "http://localhost:8000")
                video_with_url = f"{base_url}/static/generated/voiced/{out_name}"

        if request.episode_id is not None:
            db = SessionLocal()
            try:
                ep = db.query(Episode).filter(Episode.id == request.episode_id).first()
                if ep:
                    ep.voiceover_url = tts["audio_url"]
                    ep.voiceover_words_json = tts_service.words_to_json(tts["words"])
                    ep.voiceover_provider = tts["provider"]
                    if video_with_url:
                        ep.video_with_voiceover_url = video_with_url
                    db.commit()
            finally:
                db.close()

        return VoiceoverResponse(
            success=True,
            audio_url=tts["audio_url"],
            words=[WordTimingDTO(**w) for w in tts["words"]],
            duration_sec=tts["duration_sec"],
            provider=tts["provider"],
            video_with_voiceover_url=video_with_url,
        )

    return await asyncio.to_thread(_run)


# ─── Captions burn-in (Phase 2) ───────────────────────────────────────────────

class CaptionsRequest(BaseModel):
    video_url: str = Field(..., description="Video to burn captions onto")
    words: List[WordTimingDTO] = Field(..., min_length=1, description="Word-level timings")
    style: str = Field("modern", description="modern | neon | bold | minimal | cinematic")
    mode: str = Field("word_pop", description="word_pop | karaoke_line")
    episode_id: Optional[int] = None


class CaptionsResponse(BaseModel):
    success: bool
    video_with_captions_url: Optional[str] = None
    error: Optional[str] = None


@router.post("/captions", response_model=CaptionsResponse)
async def burn_captions(request: CaptionsRequest):
    """Burn TikTok-style word-level captions onto a video using ASS subtitles.

    Pass any video URL and the word timings from `/voiceover` (or any source). The endpoint
    downloads the video, builds an ASS subtitle track via `captions_service`, runs FFmpeg
    to bake it into the pixels, and returns the new video URL.
    """
    from app.services import captions_service
    from app.core.db import SessionLocal
    from app.models.episode import Episode

    if request.style not in captions_service.STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style '{request.style}'")
    if request.mode not in ("word_pop", "karaoke_line"):
        raise HTTPException(status_code=400, detail=f"Unknown mode '{request.mode}'")

    def _run() -> CaptionsResponse:
        if not is_safe_outbound_url(request.video_url, allow_private=_allow_private_fetch(request.video_url)):
            return CaptionsResponse(success=False, error="Unsafe video_url")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                src_video = os.path.join(tmp, "src.mp4")
                resp = requests.get(request.video_url, stream=True, timeout=120)
                resp.raise_for_status()
                with open(src_video, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                out_name = f"captions_{uuid.uuid4().hex[:10]}.mp4"
                static_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                    "static",
                )
                out_dir = os.path.join(static_dir, "generated", "captions")
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, out_name)

                ok = captions_service.burn_captions(
                    src_video,
                    [w.model_dump() for w in request.words],
                    out_path,
                    style=request.style,
                    mode=request.mode,
                )
                if not ok:
                    return CaptionsResponse(success=False, error="FFmpeg captions burn failed")

                base_url = settings.BACKEND_URL or os.getenv("BACKEND_URL", "http://localhost:8000")
                captions_url = f"{base_url}/static/generated/captions/{out_name}"

                if request.episode_id is not None:
                    db = SessionLocal()
                    try:
                        ep = db.query(Episode).filter(Episode.id == request.episode_id).first()
                        if ep:
                            ep.video_with_captions_url = captions_url
                            db.commit()
                    finally:
                        db.close()

                return CaptionsResponse(success=True, video_with_captions_url=captions_url)
        except Exception as e:
            return CaptionsResponse(success=False, error=f"captions burn failed: {e}")

    return await asyncio.to_thread(_run)


# ─── Background music (Phase 3) ───────────────────────────────────────────────

class MusicTrackDTO(BaseModel):
    id: str
    display_name: str
    mood: str
    url: str
    duration_sec: Optional[float] = None
    credit: Optional[str] = None


class MusicTracksResponse(BaseModel):
    tracks: List[MusicTrackDTO]


class AddMusicRequest(BaseModel):
    video_url: str = Field(..., description="Video to mix music onto")
    track_id: str = Field(..., description="Track filename from /music/tracks list")
    volume: float = Field(0.15, ge=0.0, le=1.0, description="Music volume relative to 1.0")
    loop_music: bool = True
    fade_in: float = Field(1.0, ge=0.0, le=10.0)
    fade_out: float = Field(1.5, ge=0.0, le=10.0)
    episode_id: Optional[int] = None


class AddMusicResponse(BaseModel):
    success: bool
    video_with_music_url: Optional[str] = None
    error: Optional[str] = None


@router.get("/music/tracks", response_model=MusicTracksResponse)
async def list_music_tracks(mood: Optional[str] = None):
    """List royalty-free background tracks discovered in backend/static/music/.
    Optionally filter by `mood` (matched against manifest.json or filename prefix)."""
    from app.services import music_service
    tracks = music_service.list_tracks(mood=mood)
    return MusicTracksResponse(tracks=[MusicTrackDTO(**t) for t in tracks])


@router.post("/music", response_model=AddMusicResponse)
async def add_music_to_video(request: AddMusicRequest):
    """Mix a background music track onto a video. Preserves the original audio
    (voiceover etc.) and adds music underneath at `volume` (default 0.15). Loops
    the track to cover the full video duration when `loop_music=True`."""
    from app.services import music_service
    from app.core.db import SessionLocal
    from app.models.episode import Episode

    track_path = music_service.resolve_track_path(request.track_id)
    if track_path is None:
        raise HTTPException(status_code=404, detail=f"Track '{request.track_id}' not found")

    def _run() -> AddMusicResponse:
        if not is_safe_outbound_url(request.video_url, allow_private=_allow_private_fetch(request.video_url)):
            return AddMusicResponse(success=False, error="Unsafe video_url")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                src_video = os.path.join(tmp, "src.mp4")
                resp = requests.get(request.video_url, stream=True, timeout=120)
                resp.raise_for_status()
                with open(src_video, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                out_name = f"music_{uuid.uuid4().hex[:10]}.mp4"
                static_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                    "static",
                )
                out_dir = os.path.join(static_dir, "generated", "music")
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, out_name)

                ok = music_service.add_music(
                    src_video, str(track_path), out_path,
                    music_volume=request.volume,
                    loop_music=request.loop_music,
                    fade_in=request.fade_in,
                    fade_out=request.fade_out,
                )
                if not ok:
                    return AddMusicResponse(success=False, error="FFmpeg music mix failed")

                base_url = settings.BACKEND_URL or os.getenv("BACKEND_URL", "http://localhost:8000")
                music_url = f"{base_url}/static/generated/music/{out_name}"

                if request.episode_id is not None:
                    db = SessionLocal()
                    try:
                        ep = db.query(Episode).filter(Episode.id == request.episode_id).first()
                        if ep:
                            ep.video_with_music_url = music_url
                            db.commit()
                    finally:
                        db.close()

                return AddMusicResponse(success=True, video_with_music_url=music_url)
        except Exception as e:
            return AddMusicResponse(success=False, error=f"music mix failed: {e}")

    return await asyncio.to_thread(_run)
