"""
Replicate Veo 3 Fast Video Provider
Supports text-to-video and image-to-video generation using Google's Veo 3 model
"""

import os
import httpx
import replicate
from replicate import Client
from typing import Optional
from app.core.config import settings
from .video_provider_base import VideoProvider


class ReplicateVeoProvider(VideoProvider):
    """
    Replicate Veo 3 Fast Video Provider
    Generates high-quality videos using Google's Veo 3 model via Replicate
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
        resolution: str = "720p"
    ) -> str:
        """
        Generate video clip using Replicate Veo 3 Fast
        
        Args:
            visual_prompt: Text description of the scene
            duration_sec: Duration in seconds (4, 6, or 8 seconds supported)
            aspect_ratio: Video aspect ratio (9:16, 16:9, 1:1)
            reference_image_url: Optional reference image URL for image-to-video
            resolution: Video resolution (720p or 1080p)
            
        Returns:
            URL of the generated video
        """
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN not set in environment variables")
        
        # Validate duration (Replicate Veo 3 supports 4, 6, or 8 seconds)
        valid_durations = [4, 6, 8]
        if duration_sec not in valid_durations:
            # Find closest valid duration
            duration_sec = min(valid_durations, key=lambda x: abs(x - duration_sec))
        
        # Prepare input
        input_data = {
            "prompt": visual_prompt,
            "resolution": resolution,
            "duration": duration_sec,
            "aspect_ratio": aspect_ratio
        }
        
        # Add reference image for image-to-video
        if reference_image_url:
            input_data["image"] = reference_image_url
            print(f"[DEBUG REPLICATE] Using reference image for image-to-video")
        
        print(f"[DEBUG REPLICATE] Sending to Veo 3: prompt={visual_prompt[:50]}..., aspect_ratio={aspect_ratio}, duration={duration_sec}")
        
        try:
            # Run prediction with extended timeout
            output = self.client.run(
                "google/veo-3-fast",
                input=input_data
            )
            
            print(f"[DEBUG REPLICATE] Output received, type: {type(output)}")
            
            # Get video URL from output
            # Note: output could be a FileOutput object with .url property, or just a string
            if hasattr(output, 'url'):
                # FileOutput object - url is a property, not a method!
                video_url = output.url
            else:
                video_url = str(output)
            
            print(f"[DEBUG REPLICATE] Video URL extracted: {video_url[:80] if video_url else 'None'}...")
                
            if not video_url:
                raise ValueError("No video URL returned from Replicate API")
                
            return video_url
        except Exception as e:
            print(f"[DEBUG REPLICATE] Error during generation: {e}")
            raise

