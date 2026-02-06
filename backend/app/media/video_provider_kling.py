"""
Replicate Kling Video Provider
Supports text-to-video and image-to-video generation using Kuaishou's Kling model
"""

import os
import httpx
import replicate
from replicate import Client
from typing import Optional
from app.core.config import settings
from app.core.retry import with_retry
from .video_provider_base import VideoProvider


class ReplicateKlingProvider(VideoProvider):
    """
    Replicate Kling Video Provider
    Generates high-quality videos using Kuaishou's Kling model via Replicate
    """
    
    # Available Kling models on Replicate (updated 2026)
    MODELS = {
        "kling-2.1": "kwaivgi/kling-v2.1",  # image-to-video
        "kling-2.5": "kling-ai/kling-v2.5",  # text-to-video
    }
    
    def __init__(self, model_version: str = "kling-2.1"):
        self.api_token = settings.REPLICATE_API_TOKEN or os.getenv("REPLICATE_API_TOKEN")
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token

        # Create client with extended timeout (5 minutes for video generation)
        self.client = Client(
            api_token=self.api_token,
            timeout=httpx.Timeout(300.0, connect=60.0)
        )

        self.model_version = model_version
        self.model_id = self.MODELS.get(model_version, self.MODELS["kling-2.1"])
        
    def generate_clip(
        self, 
        visual_prompt: str, 
        duration_sec: int, 
        *, 
        aspect_ratio: str = "9:16",
        reference_image_url: Optional[str] = None,
        resolution: str = "720p"
    ) -> str:
        """
        Generate video clip using Replicate Kling
        
        Args:
            visual_prompt: Text description of the scene
            duration_sec: Duration in seconds (5 or 10 seconds for Kling)
            aspect_ratio: Video aspect ratio (9:16, 16:9, 1:1)
            reference_image_url: Optional reference image URL for image-to-video
            resolution: Video resolution
            
        Returns:
            URL of the generated video
        """
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN not set in environment variables")
        
        # Kling supports 5 or 10 seconds
        valid_durations = [5, 10]
        if duration_sec not in valid_durations:
            duration_sec = min(valid_durations, key=lambda x: abs(x - duration_sec))
        
        # Map aspect ratio to Kling format
        aspect_map = {
            "9:16": "9:16",
            "16:9": "16:9",
            "1:1": "1:1",
        }
        kling_aspect = aspect_map.get(aspect_ratio, "9:16")
        
        # Choose model based on whether we have reference image
        if reference_image_url:
            # Image-to-video: use kling-v2.6 (best quality)
            model_id = "kwaivgi/kling-v2.6"
            input_data = {
                "prompt": visual_prompt,
                "image": reference_image_url,
                "duration": duration_sec,
            }
            print(f"[DEBUG KLING] Using kling-v2.6 image-to-video")
        else:
            # Text-to-video: use kling-v2.5-turbo-pro
            model_id = "kwaivgi/kling-v2.5-turbo-pro"
            input_data = {
                "prompt": visual_prompt,
                "duration": duration_sec,
                "aspect_ratio": kling_aspect,
            }
            print(f"[DEBUG KLING] Using kling-v2.5-turbo-pro text-to-video")

        print(f"[DEBUG KLING] Sending to {model_id}: prompt={visual_prompt[:50]}..., duration={duration_sec}")

        def on_retry(attempt: int, error: Exception, delay: float):
            print(f"[DEBUG KLING] Retry {attempt}: {error}, waiting {delay:.1f}s")

        def api_call():
            output = self.client.run(
                model_id,
                input=input_data
            )

            print(f"[DEBUG KLING] Output received, type: {type(output)}")

            # Get video URL from output
            if hasattr(output, 'url'):
                video_url = output.url
            elif isinstance(output, list) and len(output) > 0:
                # Some models return a list of outputs
                video_url = output[0] if isinstance(output[0], str) else output[0].url
            else:
                video_url = str(output)

            print(f"[DEBUG KLING] Video URL extracted: {video_url[:80] if video_url else 'None'}...")

            if not video_url:
                raise ValueError("No video URL returned from Replicate API")

            return video_url

        try:
            # Run with retry (3 attempts, exponential backoff)
            return with_retry(max_attempts=3, base_delay=2.0, on_retry=on_retry)(api_call)
        except Exception as e:
            print(f"[DEBUG KLING] Error during generation after retries: {e}")
            raise
