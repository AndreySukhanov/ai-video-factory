"""
API for generating episodes from prompt and reference image
"""
import os
import asyncio
import time
import tempfile
import subprocess
import uuid
import io
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
import requests
from PIL import Image

from app.core.config import settings
from app.core.security import (
    extract_local_upload_filename,
    is_internal_backend_asset_url,
    is_safe_outbound_url,
    resolve_upload_file_path,
)
from app.media import VideoProviderMock, ReplicateKlingProvider
from app.media.video_provider_pika import PikaVideoProvider
from app.media.video_provider_minimax import MiniMaxProvider
from app.media.character_generator import CharacterGenerator
from app.ai_orchestrator.agents import get_prompt_enhancer, get_story_generator
from app.api.v1.websocket import get_session_manager

# Catbox upload URL for external access
CATBOX_API_URL = "https://catbox.moe/user/api.php"
UPLOADS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "uploads",
)


def _allow_private_fetch(url: str) -> bool:
    return settings.ALLOW_PRIVATE_URL_FETCH or is_internal_backend_asset_url(url, settings.BACKEND_URL)


async def upload_to_catbox_from_url(image_url: str) -> Optional[str]:
    """
    Download image from URL and upload to catbox.moe for external access.
    This is needed because Replicate cannot access localhost URLs.

    Args:
        image_url: URL of the image to download and re-upload

    Returns:
        Public catbox.moe URL or None if failed
    """
    try:
        if not is_safe_outbound_url(image_url, allow_private=_allow_private_fetch(image_url)):
            print(f"[CATBOX] Blocked unsafe URL: {image_url}")
            return None

        def _upload_sync() -> Optional[str]:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            content = response.content

            filename = image_url.split("/")[-1] if "/" in image_url else "character.png"
            if not filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
                filename = "character.png"

            files = {"fileToUpload": (filename, content)}
            data = {"reqtype": "fileupload"}
            upload_response = requests.post(CATBOX_API_URL, files=files, data=data, timeout=60)

            if upload_response.status_code == 200 and upload_response.text.startswith("https://"):
                catbox_url = upload_response.text.strip()
                print(f"[CATBOX] Uploaded to: {catbox_url}")
                return catbox_url

            print(f"[CATBOX] Upload failed: {upload_response.text}")
            return None

        return await asyncio.to_thread(_upload_sync)

    except Exception as e:
        print(f"[CATBOX] Error uploading from URL: {e}")
        return None


def _resolve_local_file_path(url: str) -> Optional[str]:
    """Resolve a localhost URL to a local file path. Supports /uploads/ and /static/."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path if parsed.scheme else url

    # /uploads/xxx.jpg
    if path.startswith("/uploads/"):
        file_name = extract_local_upload_filename(url)
        if file_name:
            try:
                return str(resolve_upload_file_path(UPLOADS_DIR, file_name))
            except ValueError:
                return None

    # /static/storyboard/xxx.png, /static/generated/xxx.mp4
    if path.startswith("/static/"):
        rel = path.lstrip("/")
        if ".." in rel or "\\" in rel:
            return None
        full_path = os.path.join(STATIC_DIR, rel.replace("static/", "", 1))
        if os.path.isfile(full_path):
            return full_path

    return None


async def upload_local_to_catbox(url: str) -> Optional[str]:
    """If URL points to a local file, upload it to catbox and return public URL."""
    local_path = _resolve_local_file_path(url)
    if not local_path:
        return None

    def _upload_sync() -> Optional[str]:
        with open(local_path, "rb") as f:
            content = f.read()
        filename = os.path.basename(local_path)
        files = {"fileToUpload": (filename, content)}
        data = {"reqtype": "fileupload"}
        resp = requests.post(CATBOX_API_URL, files=files, data=data, timeout=60)
        if resp.status_code == 200 and resp.text.startswith("https://"):
            catbox_url = resp.text.strip()
            print(f"[CATBOX] Local file uploaded: {local_path} → {catbox_url}")
            return catbox_url
        print(f"[CATBOX] Upload failed for {local_path}: {resp.text[:100]}")
        return None

    try:
        return await asyncio.to_thread(_upload_sync)
    except Exception as e:
        print(f"[CATBOX] Error uploading local file: {e}")
        return None


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


def crop_image_to_aspect_ratio(image_data: bytes, target_aspect_ratio: str) -> bytes:
    """
    Crop image to target aspect ratio using center crop.
    This preserves the main subject which is typically centered.
    """
    # Parse target aspect ratio
    if target_aspect_ratio == "9:16":
        target_ratio = 9 / 16  # 0.5625 - vertical
    elif target_aspect_ratio == "16:9":
        target_ratio = 16 / 9  # 1.777 - horizontal
    elif target_aspect_ratio == "1:1":
        target_ratio = 1.0
    else:
        # Unknown, return original
        return image_data
    
    # Open image
    img = Image.open(io.BytesIO(image_data))
    width, height = img.size

    # Downscale large images so base64 data URIs stay small (some providers reject big payloads)
    MAX_DIM = 1280
    if max(width, height) > MAX_DIM:
        scale = MAX_DIM / max(width, height)
        img = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
        width, height = img.size

    current_ratio = width / height
    needs_crop = abs(current_ratio - target_ratio) / target_ratio >= 0.05
    if needs_crop:
        if current_ratio > target_ratio:
            # Image is too wide - crop horizontally (center crop)
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            img = img.crop((left, 0, left + new_width, height))
        else:
            # Image is too tall - crop vertically (center crop)
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            img = img.crop((0, top, width, top + new_height))

    # Save to bytes (always re-encode so downscale/crop take effect)
    output = io.BytesIO()
    img_format = "PNG" if img.mode == "RGBA" else "JPEG"
    img.save(output, format=img_format, quality=90)
    return output.getvalue()


def _download_video_locally(video_url: str) -> str:
    """Download video from remote URL to local static dir (Veo retention = 2 days)."""
    video_filename = f"gen_{uuid.uuid4().hex[:12]}.mp4"
    generated_dir = os.path.join(STATIC_DIR, "generated")
    os.makedirs(generated_dir, exist_ok=True)
    local_path = os.path.join(generated_dir, video_filename)

    resp = requests.get(video_url, timeout=120)
    resp.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(resp.content)

    base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    local_url = f"{base_url}/static/generated/{video_filename}"
    print(f"[AUTO-DOWNLOAD] Saved {len(resp.content)} bytes to {local_url}")
    return local_url


router = APIRouter()


# Whitelisted video models — unknown values are rejected (422) instead of
# silently falling through to a fallback provider.
ALLOWED_VIDEO_MODELS = {
    "seedance", "wavespeed", "wavespeed-standard", "wavespeed-v15", "laozhang",
    "vertex", "gemini", "kling", "minimax", "pika", "fal", "mock",
}


# Request/Response models
class EpisodeGenerateRequest(BaseModel):
    """Request body for episode generation"""
    prompt: str = Field(..., min_length=10, max_length=2000, description="Visual prompt for video generation")
    duration: int = Field(default=4, description="Video duration in seconds (4/6/8 for Veo; 5/10 for Kling; 6 for MiniMax)")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio")
    reference_image_url: Optional[str] = Field(default=None, description="Optional reference image URL (first frame for I2V)")
    last_frame_image_url: Optional[str] = Field(default=None, description="Last frame image URL for transition videos (Veo 3.1 -fl models)")
    subject_reference_url: Optional[str] = Field(default=None, description="Character reference for identity consistency (MiniMax S2V-01)")
    reference_images: Optional[List[str]] = Field(default=None, description="1-3 reference images for Veo 3.1 R2V character consistency")
    model: str = Field(default="laozhang", description="Video model: seedance, wavespeed, laozhang, vertex, gemini, kling, or minimax")
    session_id: Optional[str] = Field(default=None, description="WebSocket session ID for progress updates")
    seed: Optional[int] = Field(default=None, description="Fixed seed for visual stability")
    negative_prompt: Optional[str] = Field(default=None, description="Negative prompt (noun format: text overlays, subtitles, cartoon)")
    quality_mode: str = Field(default="fast", description="Quality mode: fast or standard. For gemini/vertex.")
    generate_audio: bool = Field(default=True, description="Generate audio with video. Disable for cheaper LaoZhang ($0.10/s vs $0.15/s)")
    variants_count: int = Field(default=1, ge=1, le=4, description="Number of variants to generate (for standard mode)")
    use_timestamps: bool = Field(default=False, description="Use multi-shot timestamp prompting (gemini/vertex, duration>=6)")
    narrative_structure: Optional[str] = Field(default=None, description="Narrative structure for timestamp prompting")

    @field_validator("model")
    @classmethod
    def _validate_model(cls, v: str) -> str:
        if v not in ALLOWED_VIDEO_MODELS:
            raise ValueError(f"Unknown model '{v}'. Allowed: {sorted(ALLOWED_VIDEO_MODELS)}")
        return v


class EpisodeGenerateResponse(BaseModel):
    """Response body for episode generation"""
    success: bool
    video_url: Optional[str] = None
    variants: Optional[List[str]] = None  # Multiple video URLs when variants_count > 1
    status: str
    duration: Optional[int] = None
    generation_time: Optional[float] = None
    quality_mode: Optional[str] = None
    error: Optional[str] = None


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


# Static dir for auto-downloaded videos
STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "static",
)


# Initialize video provider
def get_video_provider(model: str = "seedance", reference_image_url: str = None, aspect_ratio: str = "9:16", quality_mode: str = "fast", generate_audio: bool = True):
    """Get the configured video provider based on model choice"""
    # Vertex AI provider (Google Cloud — supports generateAudio=false for cheaper no-audio)
    if model == "vertex":
        from app.media.video_provider_vertex import VertexVeoProvider
        has_ref = bool(reference_image_url)
        use_fast = (quality_mode == "fast")
        return VertexVeoProvider(use_fast=use_fast, use_fl=has_ref, aspect_ratio=aspect_ratio, generate_audio=generate_audio)

    # Gemini API provider (direct Google access, no intermediary)
    if model == "gemini":
        from app.media.video_provider_gemini import GeminiVeoProvider
        has_ref = bool(reference_image_url)
        use_fast = (quality_mode == "fast")
        return GeminiVeoProvider(use_fast=use_fast, use_fl=has_ref, aspect_ratio=aspect_ratio)

    # Seedance 2.0 via LaoZhang ($0.05/video, up to 9 reference images)
    if model == "seedance":
        from app.media.video_provider_seedance import SeedanceProvider
        return SeedanceProvider(aspect_ratio=aspect_ratio)

    # Seedance 2.0 via WaveSpeed AI (альтернативный путь, Bearer auth)
    if model == "wavespeed":
        from app.media.video_provider_wavespeed import WavespeedSeedanceProvider
        return WavespeedSeedanceProvider(aspect_ratio=aspect_ratio, use_fast=True)

    # Seedance 2.0 Standard via WaveSpeed (дороже, выше качество)
    if model == "wavespeed-standard":
        from app.media.video_provider_wavespeed import WavespeedSeedanceProvider
        return WavespeedSeedanceProvider(aspect_ratio=aspect_ratio, use_fast=False)

    # Seedance v1.5-pro via WaveSpeed (дешевле $0.26, прошлое поколение)
    if model == "wavespeed-v15":
        from app.media.video_provider_wavespeed import WavespeedSeedanceProvider
        return WavespeedSeedanceProvider(aspect_ratio=aspect_ratio, model_slug="seedance-v1.5-pro")

    # LaoZhang provider (opt-in, requires API key)
    # Supports full matrix including landscape-fast (cheaper 16:9!)
    # NOTE: LaoZhang does NOT support -fl models (403), but accepts image param on standard models
    if model == "laozhang":
        from app.media.video_provider_laozhang import LaoZhangVeoProvider
        return LaoZhangVeoProvider(use_fast=(quality_mode == "fast"), use_fl=False, aspect_ratio=aspect_ratio)

    if settings.REPLICATE_API_TOKEN:
        if model == "minimax":
            return MiniMaxProvider()
        elif model == "kling":
            return ReplicateKlingProvider()
        else:
            return MiniMaxProvider()
    elif settings.VIDEO_API_KEY or settings.FAL_KEY:
        return PikaVideoProvider()
    else:
        return VideoProviderMock()


async def send_progress(session_id: Optional[str], stage: str, progress: int, message: str, video_url: Optional[str] = None):
    """Helper to send progress updates via WebSocket"""
    if not session_id:
        return
    try:
        session_mgr = get_session_manager()
        await session_mgr.send_progress(session_id, {
            "type": "progress",
            "stage": stage,
            "progress": progress,
            "message": message,
            "video_url": video_url
        })
    except Exception as e:
        print(f"[WS] Progress send error: {e}")


@router.post("/generate", response_model=EpisodeGenerateResponse)
async def generate_episode(request: EpisodeGenerateRequest):
    """
    Generate a video episode from a text prompt and optional reference image.

    This endpoint directly generates a video clip using the configured video provider
    (Replicate Veo 3, Pika, or Mock for testing).

    Args:
        request: EpisodeGenerateRequest with prompt, duration, and optional reference image

    Returns:
        EpisodeGenerateResponse with video URL or error message
    """
    import base64
    start_time = time.time()
    session_id = request.session_id

    print(f"[DEBUG] Generate request: prompt={request.prompt[:50]}..., model={request.model}, ref_image={request.reference_image_url}, subject_ref={request.subject_reference_url}")

    # Send initial progress
    await send_progress(session_id, "starting", 5, "Starting video generation...")

    try:
        video_provider = get_video_provider(
            model=request.model,
            reference_image_url=request.reference_image_url or request.last_frame_image_url,
            aspect_ratio=request.aspect_ratio,
            quality_mode=request.quality_mode,
            generate_audio=request.generate_audio,
        )

        # Helper function to convert local uploads/static assets to base64 data URI
        def convert_local_to_base64(url: Optional[str], crop_aspect: bool = True) -> Optional[str]:
            if not url:
                return None

            # Try /uploads/ path first
            file_name = extract_local_upload_filename(url)
            if file_name:
                try:
                    file_path = resolve_upload_file_path(UPLOADS_DIR, file_name)
                except ValueError:
                    print(f"[DEBUG] Rejected unsafe upload path: {file_name}")
                    return None
            else:
                # Try /static/ paths (storyboard frames, extracted frames)
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = parsed.path if parsed.scheme else url
                if path.startswith("/static/"):
                    from pathlib import Path
                    rel = path.lstrip("/")
                    # Validate: only allow known subdirs, no ..
                    if ".." in rel or "\\" in rel:
                        print(f"[DEBUG] Rejected unsafe static path: {rel}")
                        return None
                    file_path = Path(STATIC_DIR) / rel.replace("static/", "", 1)
                else:
                    return url  # Return as-is if not local

            print(f"[DEBUG] Looking for file: {file_path}")
            print(f"[DEBUG] File exists: {os.path.exists(file_path)}")

            if not os.path.exists(file_path):
                print(f"[DEBUG] File not found, returning None")
                return None

            with open(file_path, "rb") as f:
                image_data = f.read()

            # Crop image to match target aspect ratio (center crop) if requested
            if crop_aspect:
                original_size = len(image_data)
                image_data = crop_image_to_aspect_ratio(image_data, request.aspect_ratio)
                print(f"[DEBUG] Cropped image from {original_size} to {len(image_data)} bytes for aspect_ratio={request.aspect_ratio}")

            # Determine mime type
            suffix = file_path.suffix.lower()
            if suffix == ".png":
                mime_type = "image/png"
            elif suffix in {".jpg", ".jpeg"}:
                mime_type = "image/jpeg"
            else:
                mime_type = "image/png"

            # Convert to data URI
            b64_data = base64.b64encode(image_data).decode("utf-8")
            data_uri = f"data:{mime_type};base64,{b64_data}"
            print(f"[DEBUG] Converted to base64, length: {len(data_uri)}")
            return data_uri

        # Process reference image URL (first frame for I2V)
        await send_progress(session_id, "processing", 10, "Processing reference images...")

        # LaoZhang routes ("seedance" $0.05, "laozhang") need a public URL → catbox.
        # WaveSpeed/Seedance 2.0 backend can't fetch catbox (geo-blocked), so feed it a
        # base64 data URI instead (works for v1.5 + 2.0 fast/standard, local and prod).
        needs_public_url = request.model in ("seedance", "laozhang")

        if needs_public_url and request.reference_image_url:
            # Upload local file to catbox for external API access
            catbox_url = await upload_local_to_catbox(request.reference_image_url)
            reference_url = catbox_url or request.reference_image_url
        else:
            reference_url = convert_local_to_base64(request.reference_image_url, crop_aspect=True)

        # Process subject reference URL (character identity for MiniMax S2V-01)
        # Don't crop subject reference - keep original proportions for face detection
        subject_reference_url = convert_local_to_base64(request.subject_reference_url, crop_aspect=False)

        print(f"[DEBUG] Calling video provider with ref_url: {reference_url is not None}, subject_ref: {subject_reference_url is not None}")

        # Timestamp prompting: convert to multi-shot format if requested
        prompt_text = request.prompt
        if request.use_timestamps and request.model in ("gemini", "vertex", "laozhang") and request.duration >= 6:
            from app.ai_orchestrator.agents.timestamp_prompt_builder import get_timestamp_builder
            ts_builder = get_timestamp_builder()
            prompt_text = await asyncio.to_thread(
                ts_builder.build_timestamp_prompt,
                scene_description=request.prompt,
                character_card="",
                duration=request.duration,
                narrative_structure=request.narrative_structure or "hook_conflict_twist_cta",
                aspect_ratio=request.aspect_ratio,
            )
            print(f"[DEBUG] Timestamp prompt built: {prompt_text[:120]}...")

        # Enhance prompt via GPT before sending to video provider
        # I2V mode: if reference image provided, prompt should describe motion only
        is_i2v = bool(reference_url)
        await send_progress(session_id, "enhancing", 20, "Enhancing prompt with AI...")
        prompt_enhancer = get_prompt_enhancer()
        enhanced_prompt = await asyncio.to_thread(
            prompt_enhancer.enhance_prompt,
            user_prompt=prompt_text,
            aspect_ratio=request.aspect_ratio,
            duration=request.duration,
            is_i2v=is_i2v,
        )

        # Append negative prompt if provided by client
        if request.negative_prompt and 'negative prompt:' not in enhanced_prompt.lower():
            enhanced_prompt = enhanced_prompt.rstrip('.') + f'. Negative prompt: {request.negative_prompt}.'

        await send_progress(session_id, "generating", 35, f"Generating video with {request.model.upper()}...")

        # Generate video with enhanced prompt
        clip_kwargs = {
            "visual_prompt": enhanced_prompt,
            "duration_sec": request.duration,
            "aspect_ratio": request.aspect_ratio,
            "reference_image_url": reference_url,
        }

        # Last frame for transition videos (Veo 3.1 -fl models)
        if request.last_frame_image_url:
            last_frame_url = convert_local_to_base64(request.last_frame_image_url, crop_aspect=True)
            if last_frame_url:
                clip_kwargs["last_frame_image_url"] = last_frame_url
                clip_kwargs["duration_sec"] = 8  # transitions require 8s
                print(f"[DEBUG] Transition mode: first+last frame, forcing 8s duration")

        # Reference images for character/style consistency (up to 3)
        if request.reference_images:
            valid_refs = [url for url in request.reference_images if url and url.strip()]
            if valid_refs:
                clip_kwargs["reference_images"] = valid_refs[:3]
                print(f"[DEBUG] {len(valid_refs[:3])} reference images attached")

        # MiniMax with subject_reference for character consistency (S2V-01)
        if request.model == "minimax" and subject_reference_url:
            clip_kwargs["subject_reference_url"] = subject_reference_url
        # Pass negative prompt to provider
        if request.negative_prompt:
            clip_kwargs["negative_prompt"] = request.negative_prompt

        # Pass audio preference only to providers that support it
        if request.model in ("gemini", "vertex", "laozhang", "seedance", "wavespeed", "wavespeed-standard", "wavespeed-v15"):
            clip_kwargs["generate_audio"] = request.generate_audio

        variants_count = 1
        variant_urls: List[str] = []

        for variant_idx in range(variants_count):
            if variants_count > 1:
                await send_progress(session_id, "generating", 35 + (variant_idx * 50 // variants_count),
                                    f"Generating variant {variant_idx + 1}/{variants_count}...")

            video_url = None
            try:
                video_url = await asyncio.to_thread(video_provider.generate_clip, **clip_kwargs)
                if not video_url:
                    raise ValueError("Empty video_url returned")
            except Exception as gen_err:
                # === Prompt Softening: detect moderation rejection → LLM rewrite → retry once ===
                from app.ai_orchestrator.agents.prompt_softener import is_moderation_error, get_prompt_softener
                error_str = str(gen_err)
                if is_moderation_error(error_str):
                    print(f"[SOFTENER] Moderation rejection detected: {error_str[:120]}")
                    await send_progress(session_id, "softening", 50, "Prompt blocked by moderation, softening...")
                    softener = get_prompt_softener()
                    softened_prompt = await softener.soften(clip_kwargs.get("visual_prompt", ""), error_str)
                    clip_kwargs["visual_prompt"] = softened_prompt
                    try:
                        video_url = await asyncio.to_thread(video_provider.generate_clip, **clip_kwargs)
                        if not video_url:
                            raise ValueError("Empty video_url after softening")
                        print(f"[SOFTENER] Retry succeeded after softening")
                    except Exception as soft_err:
                        print(f"[SOFTENER] Retry after softening also failed: {soft_err}")
                        gen_err = soft_err

                # Vertex → Gemini API fallback
                if not video_url and request.model == "vertex" and settings.GEMINI_API_KEY:
                    print(f"[FALLBACK] Vertex failed ({gen_err}), switching to Gemini API...")
                    await send_progress(session_id, "generating", 40, "Vertex error, switching to Gemini API fallback...")
                    from app.media.video_provider_gemini import GeminiVeoProvider
                    has_ref = bool(request.reference_image_url)
                    use_fast = (request.quality_mode == "fast")
                    fallback = GeminiVeoProvider(use_fast=use_fast, use_fl=has_ref, aspect_ratio=request.aspect_ratio)
                    video_url = await asyncio.to_thread(fallback.generate_clip, **clip_kwargs)
                    print(f"[FALLBACK] Gemini API succeeded: {video_url[:80] if video_url else 'None'}")
                elif not video_url:
                    raise

            print(f"[DEBUG] Generated video_url (variant {variant_idx + 1}): {video_url[:100] if video_url else 'None'}...")

            # Auto-download video to local server (Veo retention = 2 days!)
            local_video_url = video_url
            if video_url and request.model in ("gemini", "vertex", "seedance", "laozhang", "wavespeed", "wavespeed-standard", "wavespeed-v15"):
                try:
                    await send_progress(session_id, "downloading", 85, "Saving video locally...")
                    local_video_url = await asyncio.to_thread(_download_video_locally, video_url)
                    print(f"[DEBUG] Video saved locally: {local_video_url}")
                except Exception as dl_err:
                    print(f"[DEBUG] Video auto-download failed (using remote URL): {dl_err}")
                    local_video_url = video_url

            variant_urls.append(local_video_url)

        generation_time = round(time.time() - start_time, 2)

        primary_url = variant_urls[0] if variant_urls else None
        await send_progress(session_id, "completed", 100, "Video generation complete!", primary_url)

        return EpisodeGenerateResponse(
            success=True,
            video_url=primary_url,
            variants=variant_urls if len(variant_urls) > 1 else None,
            status="completed",
            duration=request.duration,
            generation_time=generation_time,
            quality_mode=None
        )
        
    except ValueError as e:
        await send_progress(session_id, "error", 0, f"Error: {str(e)}")
        return EpisodeGenerateResponse(
            success=False,
            status="failed",
            error=str(e)
        )
    except Exception as e:
        await send_progress(session_id, "error", 0, f"Generation failed: {str(e)}")
        return EpisodeGenerateResponse(
            success=False,
            status="error",
            error=f"Generation failed: {str(e)}"
        )


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
        available.extend(["seedance", "laozhang"])
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
    provider: Optional[str] = Field(None, description="elevenlabs | openai (auto if omitted)")
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
    otherwise falls back to OpenAI TTS. ElevenLabs returns native word timings; OpenAI returns
    audio only (word-level alignment will be added in Phase 1.1 via Whisper).
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
