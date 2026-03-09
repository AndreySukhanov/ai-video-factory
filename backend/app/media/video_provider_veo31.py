"""
Google Veo 3.1 Video Provider with dynamic model routing.
Supports: I2V (first/last frame), R2V (reference images), landscape, fast/standard.

Model matrix (Replicate):
  9:16 fast          -> veo-3.1-fast              $0.15
  9:16 standard      -> veo-3.1                   $0.25
  9:16 fast fl       -> veo-3.1-fast-fl           $0.15
  9:16 standard fl   -> veo-3.1-fl                $0.25
  16:9 fast          -> veo-3.1-landscape-fast     (Replicate: N/A, LaoZhang: available)
  16:9 standard      -> veo-3.1-landscape          $0.25
  16:9 fast fl       -> veo-3.1-landscape-fast-fl  (Replicate: N/A, LaoZhang: available)
  16:9 standard fl   -> veo-3.1-landscape-fl       $0.25

Note: Replicate does NOT have landscape-fast variants; LaoZhang does.
This provider (Replicate) falls back to standard for 16:9.
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
    Google Veo 3.1 Video Provider with dynamic model selection.
    Automatically picks the correct model variant based on parameters.
    """

    def __init__(self, use_fast: bool = True, use_fl: bool = False, aspect_ratio: str = "9:16"):
        """
        Initialize Veo 3.1 provider with dynamic model routing.

        Args:
            use_fast: Use fast variant (cheaper $0.15 vs $0.25)
            use_fl: Use first/last frame variant (for I2V frame chaining)
            aspect_ratio: Target aspect ratio (affects model choice)
        """
        self.api_token = settings.REPLICATE_API_TOKEN or os.getenv("REPLICATE_API_TOKEN")
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token

        self.client = Client(
            api_token=self.api_token,
            timeout=httpx.Timeout(300.0, connect=60.0)
        )

        # Build model name dynamically from the matrix
        base = "veo-3.1"
        parts = [base]

        # Landscape for 16:9 (no fast-landscape variant exists!)
        if aspect_ratio == "16:9":
            parts.append("landscape")
            self.use_fast = False  # fast-landscape doesn't exist
        elif use_fast:
            parts.append("fast")

        self.use_fast = use_fast if aspect_ratio != "16:9" else False

        # First/Last frame for I2V chaining
        if use_fl:
            parts.append("fl")

        self.model_id = f"google/{'-'.join(parts)}"
        self.use_fl = use_fl
        self.default_aspect_ratio = aspect_ratio

        print(f"[VEO31] Initialized with model: {self.model_id} (fast={self.use_fast}, fl={use_fl}, aspect={aspect_ratio})")

    def generate_clip(
        self,
        visual_prompt: str,
        duration_sec: int,
        *,
        aspect_ratio: str = "16:9",
        reference_image_url: Optional[str] = None,
        reference_images: Optional[List[str]] = None,
        resolution: str = "720p",
        generate_audio: bool = True,
        negative_prompt: Optional[str] = None
    ) -> str:
        """
        Generate video clip using Google Veo 3.1.

        Args:
            visual_prompt: Text description of the scene
            duration_sec: Duration in seconds (4, 6, or 8)
            aspect_ratio: Video aspect ratio (16:9 or 9:16)
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

        # Frame chaining (fl models) requires 8s duration
        if self.use_fl and duration_sec != 8:
            print(f"[VEO31] Frame chaining requires 8s, forcing duration from {duration_sec} to 8")
            duration_sec = 8

        input_data = {
            "prompt": visual_prompt,
            "duration": duration_sec,
            "resolution": resolution,
            "generate_audio": generate_audio
        }

        # Determine which model to use (may override init model for R2V)
        model_to_use = self.model_id

        if reference_images and len(reference_images) > 0:
            # R2V mode - MUST use full version (fast doesn't support reference_images)
            model_to_use = "google/veo-3.1"
            input_data["reference_images"] = reference_images[:3]
            input_data["aspect_ratio"] = "16:9"  # R2V requires 16:9
            input_data["duration"] = 8  # R2V requires 8 seconds
            print(f"[VEO31] R2V mode with {len(reference_images)} reference images (forcing full version, 16:9, 8s)")
        else:
            # Standard / I2V mode
            input_data["aspect_ratio"] = aspect_ratio

            if reference_image_url:
                input_data["image"] = reference_image_url
                print(f"[VEO31] I2V mode with first frame image (model: {model_to_use})")

        # Add negative prompt
        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt

        print(f"[VEO31] Sending to {model_to_use}: prompt={visual_prompt[:60]}...")
        print(f"[VEO31] Parameters: duration={input_data.get('duration')}, aspect={input_data.get('aspect_ratio')}, r2v={bool(reference_images)}, i2v={bool(reference_image_url)}")

        def on_retry(attempt: int, error: Exception, delay: float):
            print(f"[VEO31] Retry {attempt}: {error}, waiting {delay:.1f}s")

        def api_call():
            output = self.client.run(
                model_to_use,
                input=input_data
            )

            print(f"[VEO31] Output received, type: {type(output)}")

            if hasattr(output, 'url'):
                video_url = output.url
            elif isinstance(output, list) and len(output) > 0:
                video_url = output[0] if isinstance(output[0], str) else output[0].url
            else:
                video_url = str(output)

            print(f"[VEO31] Video URL: {video_url[:80] if video_url else 'None'}...")

            if not video_url:
                raise ValueError("No video URL returned from Veo 3.1 API")

            return video_url

        try:
            return with_retry(max_attempts=3, base_delay=2.0, on_retry=on_retry)(api_call)
        except Exception as e:
            print(f"[VEO31] Error after retries: {e}")
            raise
