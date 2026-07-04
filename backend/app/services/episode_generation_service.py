"""
Single-episode generation service: provider routing, reference preparation,
prompt enhancement, moderation softening, Vertex→Gemini fallback, auto-download.

Extracted from api/v1/episodes.py::generate_episode (god-router split).
"""
import asyncio
import time
from typing import List, Optional

from app.core.config import settings
from app.media import VideoProviderMock, ReplicateKlingProvider
from app.media.video_provider_pika import PikaVideoProvider
from app.media.video_provider_minimax import MiniMaxProvider
from app.media.local_media import (
    convert_local_to_base64,
    download_video_locally,
    upload_local_to_catbox,
)
from app.ai_orchestrator.agents import get_prompt_enhancer
from app.schemas.episodes import EpisodeGenerateRequest, EpisodeGenerateResponse


def get_video_provider(model: str = "wavespeed", reference_image_url: str = None, aspect_ratio: str = "9:16", quality_mode: str = "fast", generate_audio: bool = True):
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

    # Seedance 2.0 via WaveSpeed AI (Bearer auth)
    if model == "wavespeed":
        from app.media.video_provider_wavespeed import WavespeedSeedanceProvider
        return WavespeedSeedanceProvider(aspect_ratio=aspect_ratio, use_fast=True)

    # Seedance 2.0 Standard via WaveSpeed (more expensive, higher quality)
    if model == "wavespeed-standard":
        from app.media.video_provider_wavespeed import WavespeedSeedanceProvider
        return WavespeedSeedanceProvider(aspect_ratio=aspect_ratio, use_fast=False)

    # Seedance v1.5-pro via WaveSpeed (cheaper at $0.26, previous generation)
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
        from app.api.v1.websocket import get_session_manager
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


# Models that need a public reference URL (catbox) instead of base64
_NEEDS_PUBLIC_URL = ("laozhang",)
# Models that support generate_audio
_AUDIO_CAPABLE = ("gemini", "vertex", "laozhang", "wavespeed", "wavespeed-standard", "wavespeed-v15")
# Models whose results expire quickly → download locally (Veo retention = 2 days)
_AUTO_DOWNLOAD = ("gemini", "vertex", "laozhang", "wavespeed", "wavespeed-standard", "wavespeed-v15")


async def generate_episode_flow(request: EpisodeGenerateRequest) -> EpisodeGenerateResponse:
    """Full episode generation flow. Never raises — errors go into the response."""
    start_time = time.time()
    session_id = request.session_id

    print(f"[DEBUG] Generate request: prompt={request.prompt[:50]}..., model={request.model}, ref_image={request.reference_image_url}, subject_ref={request.subject_reference_url}")

    await send_progress(session_id, "starting", 5, "Starting video generation...")

    try:
        video_provider = get_video_provider(
            model=request.model,
            reference_image_url=request.reference_image_url or request.last_frame_image_url,
            aspect_ratio=request.aspect_ratio,
            quality_mode=request.quality_mode,
            generate_audio=request.generate_audio,
        )

        # Process reference image URL (first frame for I2V)
        await send_progress(session_id, "processing", 10, "Processing reference images...")

        # LaoZhang route ("laozhang" Veo) needs a public URL → catbox.
        # WaveSpeed/Seedance 2.0 backend can't fetch catbox (geo-blocked), so feed it a
        # base64 data URI instead (works for v1.5 + 2.0 fast/standard, local and prod).
        if request.model in _NEEDS_PUBLIC_URL and request.reference_image_url:
            catbox_url = await upload_local_to_catbox(request.reference_image_url)
            reference_url = catbox_url or request.reference_image_url
        else:
            reference_url = convert_local_to_base64(request.reference_image_url, request.aspect_ratio, crop_aspect=True)

        # Process subject reference URL (character identity for MiniMax S2V-01)
        # Don't crop subject reference - keep original proportions for face detection
        subject_reference_url = convert_local_to_base64(request.subject_reference_url, request.aspect_ratio, crop_aspect=False)

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

        # Enhance prompt via LLM before sending to video provider
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
            last_frame_url = convert_local_to_base64(request.last_frame_image_url, request.aspect_ratio, crop_aspect=True)
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
        if request.model in _AUDIO_CAPABLE:
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
            if video_url and request.model in _AUTO_DOWNLOAD:
                try:
                    await send_progress(session_id, "downloading", 85, "Saving video locally...")
                    local_video_url = await asyncio.to_thread(download_video_locally, video_url)
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
