"""
Google Veo 3.1 Video Provider with Reference Images (R2V)
Supports character consistency through reference_images parameter
"""

import os
import httpx
from replicate import Client
from typing import Optional, List
from app.core.config import settings
from app.core.retry import with_retry
from .video_provider_base import VideoProvider


class Veo31Provider(VideoProvider):
    """
    Google Veo 3.1 Video Provider with Reference-to-Video (R2V)
    Uses reference_images for character consistency across videos
    """

    def __init__(self, use_fast: bool = True):
        """
        Initialize Veo 3.1 provider.

        Args:
            use_fast: If True, use veo-3.1-fast (cheaper, faster).
                     If False, use veo-3.1 (higher quality, slower).
        """
        self.api_token = settings.REPLICATE_API_TOKEN or os.getenv("REPLICATE_API_TOKEN")
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token

        # Create client with extended timeout (5 minutes for video generation)
        self.client = Client(
            api_token=self.api_token,
            timeout=httpx.Timeout(300.0, connect=60.0)
        )

        self.use_fast = use_fast
        self.model_id = "google/veo-3.1-fast" if use_fast else "google/veo-3.1"

    def generate_clip(
        self,
        visual_prompt: str,
        duration_sec: int,
        *,
        aspect_ratio: str = "16:9",
        reference_image_url: Optional[str] = None,
        reference_images: Optional[List[str]] = None,
        resolution: str = "1080p",
        generate_audio: bool = True,
        negative_prompt: Optional[str] = None
    ) -> str:
        """
        Generate video clip using Google Veo 3.1 with optional R2V (Reference-to-Video)

        Args:
            visual_prompt: Text description of the scene
            duration_sec: Duration in seconds (4, 6, or 8)
            aspect_ratio: Video aspect ratio (16:9 or 9:16). R2V only supports 16:9
            reference_image_url: Single reference image for I2V (first frame)
            reference_images: List of 1-3 reference images for R2V character consistency
            resolution: Video resolution (720p or 1080p)
            generate_audio: Whether to generate audio
            negative_prompt: What to avoid in the video

        Returns:
            URL of the generated video
        """
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN not set in environment variables")

        # Validate duration (Veo 3.1 supports 4, 6, or 8 seconds)
        valid_durations = [4, 6, 8]
        if duration_sec not in valid_durations:
            duration_sec = min(valid_durations, key=lambda x: abs(x - duration_sec))

        # Prepare input
        input_data = {
            "prompt": visual_prompt,
            "duration": duration_sec,
            "resolution": resolution,
            "generate_audio": generate_audio
        }

        # R2V (Reference-to-Video) for character consistency
        # Note: R2V only works with full version (not fast), 16:9 aspect ratio, and 8 second duration
        # Determine which model to use
        model_to_use = self.model_id
        if reference_images and len(reference_images) > 0:
            # R2V mode - MUST use full version (fast doesn't support reference_images)
            model_to_use = "google/veo-3.1"  # Force full version for R2V
            input_data["reference_images"] = reference_images[:3]  # Max 3 images
            input_data["aspect_ratio"] = "16:9"  # R2V requires 16:9
            input_data["duration"] = 8  # R2V requires 8 seconds
            print(f"[DEBUG VEO31] Using R2V mode with {len(reference_images)} reference images (full version required)")
        else:
            # Standard mode
            input_data["aspect_ratio"] = aspect_ratio

            # Add single reference image for I2V (first frame)
            if reference_image_url:
                input_data["image"] = reference_image_url
                print(f"[DEBUG VEO31] Using I2V mode with first frame image")

        # Add negative prompt if provided
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt

        print(f"[DEBUG VEO31] Sending to {model_to_use}: prompt={visual_prompt[:50]}...")
        print(f"[DEBUG VEO31] Parameters: duration={input_data.get('duration')}, aspect={input_data.get('aspect_ratio')}, r2v={bool(reference_images)}")

        def on_retry(attempt: int, error: Exception, delay: float):
            print(f"[DEBUG VEO31] Retry {attempt}: {error}, waiting {delay:.1f}s")

        def api_call():
            output = self.client.run(
                model_to_use,
                input=input_data
            )

            print(f"[DEBUG VEO31] Output received, type: {type(output)}")

            # Get video URL from output
            if hasattr(output, 'url'):
                video_url = output.url
            elif isinstance(output, list) and len(output) > 0:
                video_url = output[0] if isinstance(output[0], str) else output[0].url
            else:
                video_url = str(output)

            print(f"[DEBUG VEO31] Video URL extracted: {video_url[:80] if video_url else 'None'}...")

            if not video_url:
                raise ValueError("No video URL returned from Veo 3.1 API")

            return video_url

        try:
            # Run with retry (3 attempts, exponential backoff)
            return with_retry(max_attempts=3, base_delay=2.0, on_retry=on_retry)(api_call)
        except Exception as e:
            print(f"[DEBUG VEO31] Error during generation after retries: {e}")
            raise
