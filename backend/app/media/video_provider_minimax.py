"""
MiniMax Hailuo Video Provider with Subject Reference (S2V-01)
Supports character consistency across multiple video generations
"""

import os
import httpx
import replicate
from replicate import Client
from typing import Optional
from app.core.config import settings
from app.core.retry import with_retry
from .video_provider_base import VideoProvider


class MiniMaxProvider(VideoProvider):
    """
    MiniMax Hailuo Video Provider with Subject Reference
    Uses S2V-01 model for character consistency when subject_reference is provided
    """

    def __init__(self):
        self.api_token = settings.REPLICATE_API_TOKEN or os.getenv("REPLICATE_API_TOKEN")
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token

        # Create client with extended timeout (5 minutes for video generation)
        self.client = Client(
            api_token=self.api_token,
            timeout=httpx.Timeout(300.0, connect=60.0)
        )

    def generate_clip(
        self,
        visual_prompt: str,
        duration_sec: int,
        *,
        aspect_ratio: str = "9:16",
        reference_image_url: Optional[str] = None,
        subject_reference_url: Optional[str] = None,
        resolution: str = "720p"
    ) -> str:
        """
        Generate video clip using MiniMax Hailuo with S2V-01 for character consistency

        Args:
            visual_prompt: Text description of the scene
            duration_sec: Duration in seconds (5 seconds for MiniMax)
            aspect_ratio: Video aspect ratio (9:16, 16:9, 1:1)
            reference_image_url: First frame image for I2V
            subject_reference_url: Character reference image for identity consistency (S2V-01)
            resolution: Not used by MiniMax, kept for interface compatibility

        Returns:
            URL of the generated video
        """
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN not set in environment variables")

        # MiniMax generates approximately 5 second videos
        # Duration parameter is not directly supported, but we accept it for interface compatibility

        # Prepare input
        input_data = {
            "prompt": visual_prompt,
            "prompt_optimizer": True  # Enable prompt optimization for better results
        }

        # Add subject reference for character consistency (S2V-01 mode)
        # This is the KEY feature for maintaining character identity
        if subject_reference_url:
            input_data["subject_reference"] = subject_reference_url
            print(f"[DEBUG MINIMAX] Using subject_reference for character consistency (S2V-01)")

        # Add first frame image for image-to-video
        if reference_image_url:
            input_data["first_frame_image"] = reference_image_url
            print(f"[DEBUG MINIMAX] Using first_frame_image for I2V")

        print(f"[DEBUG MINIMAX] Sending to video-01: prompt={visual_prompt[:50]}...")
        print(f"[DEBUG MINIMAX] subject_reference: {'Yes' if subject_reference_url else 'No'}, first_frame: {'Yes' if reference_image_url else 'No'}")

        def on_retry(attempt: int, error: Exception, delay: float):
            print(f"[DEBUG MINIMAX] Retry {attempt}: {error}, waiting {delay:.1f}s")

        def api_call():
            output = self.client.run(
                "minimax/video-01",
                input=input_data
            )

            print(f"[DEBUG MINIMAX] Output received, type: {type(output)}")

            # Get video URL from output
            if hasattr(output, 'url'):
                video_url = output.url
            elif isinstance(output, list) and len(output) > 0:
                video_url = output[0] if isinstance(output[0], str) else output[0].url
            else:
                video_url = str(output)

            print(f"[DEBUG MINIMAX] Video URL extracted: {video_url[:80] if video_url else 'None'}...")

            if not video_url:
                raise ValueError("No video URL returned from MiniMax API")

            return video_url

        try:
            # Run with retry (3 attempts, exponential backoff)
            return with_retry(max_attempts=3, base_delay=2.0, on_retry=on_retry)(api_call)
        except Exception as e:
            print(f"[DEBUG MINIMAX] Error during generation after retries: {e}")
            raise
