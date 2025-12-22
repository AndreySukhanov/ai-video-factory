"""
API for generating episodes from prompt and reference image
"""
import os
import time
import tempfile
import subprocess
import uuid
import io
from typing import Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import requests
from PIL import Image

from app.core.config import settings
from app.media import VideoProviderMock, ReplicateVeoProvider
from app.media.video_provider_pika import PikaVideoProvider
from app.ai_orchestrator.agents import get_prompt_enhancer, get_story_generator


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
    current_ratio = width / height
    
    # If already correct aspect ratio (within 5% tolerance), return original
    if abs(current_ratio - target_ratio) / target_ratio < 0.05:
        return image_data
    
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
    
    # Save to bytes
    output = io.BytesIO()
    img_format = "PNG" if img.mode == "RGBA" else "JPEG"
    img.save(output, format=img_format, quality=95)
    return output.getvalue()


router = APIRouter()


# Request/Response models
class EpisodeGenerateRequest(BaseModel):
    """Request body for episode generation"""
    prompt: str = Field(..., min_length=10, max_length=2000, description="Visual prompt for video generation")
    duration: int = Field(default=4, description="Video duration in seconds (4, 6, or 8)")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio")
    reference_image_url: Optional[str] = Field(default=None, description="Optional reference image URL")


class EpisodeGenerateResponse(BaseModel):
    """Response body for episode generation"""
    success: bool
    video_url: Optional[str] = None
    status: str
    duration: Optional[int] = None
    generation_time: Optional[float] = None
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


# Initialize video provider
def get_video_provider():
    """Get the configured video provider"""
    if settings.REPLICATE_API_TOKEN:
        return ReplicateVeoProvider()
    elif settings.VIDEO_API_KEY or settings.FAL_KEY:
        return PikaVideoProvider()
    else:
        return VideoProviderMock()


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
    
    print(f"[DEBUG] Generate request: prompt={request.prompt[:50]}..., ref_image={request.reference_image_url}")
    
    try:
        video_provider = get_video_provider()
        
        # Build full reference URL if it's a local upload
        reference_url = request.reference_image_url
        
        # Check if it's a local upload (either relative path or localhost URL)
        is_local_upload = False
        file_name = None
        
        if reference_url:
            if reference_url.startswith("/uploads/"):
                is_local_upload = True
                file_name = reference_url.replace("/uploads/", "")
            elif "/uploads/" in reference_url and ("localhost" in reference_url or "127.0.0.1" in reference_url):
                is_local_upload = True
                file_name = reference_url.split("/uploads/")[-1]
        
        if is_local_upload and file_name:
            # Local file - need to convert to base64 data URI for Replicate
            # (localhost URLs are inaccessible from external API)
            # Path: episodes.py -> v1 -> api -> app -> backend -> uploads
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads")
            file_path = os.path.join(uploads_dir, file_name)
            
            print(f"[DEBUG] Looking for file: {file_path}")
            print(f"[DEBUG] File exists: {os.path.exists(file_path)}")
            
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    image_data = f.read()
                
                # Crop image to match target aspect ratio (center crop)
                original_size = len(image_data)
                image_data = crop_image_to_aspect_ratio(image_data, request.aspect_ratio)
                print(f"[DEBUG] Cropped image from {original_size} to {len(image_data)} bytes for aspect_ratio={request.aspect_ratio}")
                
                # Determine mime type
                if file_path.lower().endswith(".png"):
                    mime_type = "image/png"
                elif file_path.lower().endswith((".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                else:
                    mime_type = "image/png"
                
                # Convert to data URI
                b64_data = base64.b64encode(image_data).decode("utf-8")
                reference_url = f"data:{mime_type};base64,{b64_data}"
                print(f"[DEBUG] Converted to base64, length: {len(reference_url)}")
            else:
                # File not found, proceed without reference
                print(f"[DEBUG] File not found, proceeding without reference")
                reference_url = None
        
        print(f"[DEBUG] Calling video provider with ref_url type: {type(reference_url)}, has_ref: {reference_url is not None}")
        
        # Enhance prompt via GPT before sending to video provider
        prompt_enhancer = get_prompt_enhancer()
        enhanced_prompt = prompt_enhancer.enhance_prompt(
            user_prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            duration=request.duration
        )
        
        # Generate video with enhanced prompt
        video_url = video_provider.generate_clip(
            visual_prompt=enhanced_prompt,
            duration_sec=request.duration,
            aspect_ratio=request.aspect_ratio,
            reference_image_url=reference_url
        )
        
        print(f"[DEBUG] Generated video_url: {video_url[:100] if video_url else 'None'}...")
        
        generation_time = round(time.time() - start_time, 2)
        
        return EpisodeGenerateResponse(
            success=True,
            video_url=video_url,
            status="completed",
            duration=request.duration,
            generation_time=generation_time
        )
        
    except ValueError as e:
        return EpisodeGenerateResponse(
            success=False,
            status="failed",
            error=str(e)
        )
    except Exception as e:
        return EpisodeGenerateResponse(
            success=False,
            status="error",
            error=f"Generation failed: {str(e)}"
        )


@router.get("/status")
async def get_generation_status():
    """
    Get the current status of the video generation service.
    
    Returns information about which video provider is configured.
    """
    provider_name = "mock"
    provider_status = "ready"
    
    if settings.REPLICATE_API_TOKEN:
        provider_name = "replicate_veo3"
        provider_status = "ready"
    elif settings.FAL_KEY:
        provider_name = "pika_fal"
        provider_status = "ready"
    elif settings.VIDEO_API_KEY:
        provider_name = "pika"
        provider_status = "ready"
    
    return {
        "provider": provider_name,
        "status": provider_status,
        "supported_durations": [4, 6, 8],
        "supported_aspect_ratios": ["9:16", "16:9", "1:1"]
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
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = os.path.join(temp_dir, "video.mp4")
            response = requests.get(request.video_url, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(video_path, 'wb') as f:
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
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            frame_path = os.path.join(uploads_dir, frame_filename)
            
            # Extract frame with FFmpeg
            cmd = f'ffmpeg -y -ss {last_frame_time} -i "{video_path}" -vframes 1 -q:v 2 "{frame_path}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0 or not os.path.exists(frame_path):
                print(f"[DEBUG] FFmpeg extract failed: {result.stderr[:200]}")
                return ExtractFrameResponse(
                    success=False,
                    error="Failed to extract frame"
                )
            
            # Return URL
            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            frame_url = f"{base_url}/uploads/{frame_filename}"
            
            print(f"[DEBUG] Extracted frame: {frame_url}")
            
            return ExtractFrameResponse(
                success=True,
                frame_url=frame_url
            )
            
    except Exception as e:
        print(f"[DEBUG] Extract frame error: {str(e)}")
        return ExtractFrameResponse(
            success=False,
            error=str(e)
        )

@router.post("/merge", response_model=MergeResponse)
async def merge_episodes(request: MergeRequest):
    """
    Merge multiple video episodes into a single video using simple concatenation.
    """
    print(f"[DEBUG MERGE] Starting merge with {len(request.video_urls)} videos")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_files = []
            
            # Download all videos
            for i, url in enumerate(request.video_urls):
                video_path = os.path.join(temp_dir, f"video_{i}.mp4")
                
                print(f"[DEBUG MERGE] Downloading video {i}: {url[:60]}...")
                
                response = requests.get(url, stream=True, timeout=120)
                response.raise_for_status()
                
                with open(video_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print(f"[DEBUG MERGE] Downloaded video {i}: {os.path.getsize(video_path)} bytes")
                video_files.append(video_path)
            
            output_filename = f"merged_{uuid.uuid4().hex[:8]}.mp4"
            # Use dynamic path that works both locally and in Docker
            static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "static")
            output_dir = os.path.join(static_dir, "merged")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            if len(video_files) == 1:
                import shutil
                shutil.copy(video_files[0], output_path)
            else:
                # Simple concat - no transitions
                concat_list_path = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_list_path, 'w') as f:
                    for vf in video_files:
                        f.write(f"file '{vf}'\n")
                
                cmd = f'ffmpeg -y -f concat -safe 0 -i "{concat_list_path}" -c:v libx264 -preset fast -crf 23 -c:a aac "{output_path}"'
                
                print(f"[DEBUG MERGE] Running concat...")
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
            
            return MergeResponse(
                success=True,
                merged_video_url=merged_url,
                total_duration=total_duration
            )
            
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


class EpisodePromptData(BaseModel):
    """Generated episode with prompt"""
    number: int
    title: str
    synopsis: str
    prompt: str


class SeriesGenerateResponse(BaseModel):
    """Response body for series generation"""
    success: bool
    series_title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
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
    print(f"[SERIES GENERATOR] Request: idea={request.idea[:50]}..., genre={request.genre}, episodes={request.episodes_count}")
    
    try:
        story_generator = get_story_generator()
        
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
                prompt=ep.visual_prompt
            )
            for ep in series.episodes
        ]
        
        print(f"[SERIES GENERATOR] Generated series: {series.series_title} with {len(episodes)} episodes")
        
        return SeriesGenerateResponse(
            success=True,
            series_title=series.series_title,
            logline=series.logline,
            genre=series.genre,
            episodes=episodes
        )
        
    except Exception as e:
        print(f"[SERIES GENERATOR] Error: {str(e)}")
        return SeriesGenerateResponse(
            success=False,
            error=f"Series generation failed: {str(e)}"
        )
