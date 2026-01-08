"""
Replicate Kling Video Provider
Supports text-to-video and image-to-video generation using Kuaishou's Kling model
"""

import os
import replicate
from typing import Optional
from app.core.config import settings
from .video_provider_base import VideoProvider


class ReplicateKlingProvider(VideoProvider):
    """
    Replicate Kling Video Provider
    Generates high-quality videos using Kuaishou's Kling model via Replicate
    """
    
    # Available Kling models on Replicate
    MODELS = {
        "kling-1.6": "kuaishou-video/kling-v1.6-pro",
        "kling-2.0": "kuaishou-video/kling-v2.0-pro", 
    }
    
    def __init__(self, model_version: str = "kling-1.6"):
        self.api_token = settings.REPLICATE_API_TOKEN or os.getenv("REPLICATE_API_TOKEN")
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token
        
        self.model_version = model_version
        self.model_id = self.MODELS.get(model_version, self.MODELS["kling-1.6"])
        
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
        
        # Prepare input
        input_data = {
            "prompt": visual_prompt,
            "duration": duration_sec,
            "aspect_ratio": kling_aspect,
        }
        
        # Add reference image for image-to-video
        if reference_image_url:
            input_data["image"] = reference_image_url
            print(f"[DEBUG KLING] Using reference image for image-to-video")
        
        print(f"[DEBUG KLING] Sending to Kling: prompt={visual_prompt[:50]}..., aspect_ratio={kling_aspect}, duration={duration_sec}")
        
        try:
            # Run prediction
            output = replicate.run(
                self.model_id,
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
        except Exception as e:
            print(f"[DEBUG KLING] Error during generation: {e}")
            raise
