import os
import time
import requests
from typing import Optional
from app.core.config import settings
from .video_provider_base import VideoProvider

class PikaVideoProvider(VideoProvider):
    """
    Pika v2.2 Video Provider via fal.ai
    Supports both text-to-video and image-to-video generation
    """
    
    def __init__(self):
        self.api_key = settings.VIDEO_API_KEY or os.getenv("FAL_KEY")
        self.base_url = "https://queue.fal.run"
        
    def generate_clip(
        self, 
        visual_prompt: str, 
        duration_sec: int, 
        *, 
        aspect_ratio: str = "9:16",
        reference_image_url: Optional[str] = None
    ) -> str:
        """
        Generate video clip using Pika v2.2
        
        Args:
            visual_prompt: Text description of the scene
            duration_sec: Duration in seconds (Pika supports up to 5 seconds)
            aspect_ratio: Video aspect ratio (9:16 for vertical)
            reference_image_url: Optional reference image URL for image-to-video
            
        Returns:
            URL of the generated video
        """
        if not self.api_key:
            raise ValueError("FAL_KEY not set in environment variables")
        
        # Choose endpoint based on whether we have a reference image
        if reference_image_url:
            endpoint = "fal-ai/pika/v2.2/image-to-video"
            payload = {
                "image_url": reference_image_url,
                "prompt": visual_prompt,
                "aspect_ratio": aspect_ratio,
                "duration": min(duration_sec, 5)  # Pika max is 5 seconds
            }
        else:
            endpoint = "fal-ai/pika/v2.2/text-to-video"
            payload = {
                "prompt": visual_prompt,
                "aspect_ratio": aspect_ratio,
                "duration": min(duration_sec, 5)
            }
        
        # Submit job
        submit_url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(submit_url, json=payload, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        request_id = result.get("request_id")
        
        if not request_id:
            raise ValueError("No request_id returned from Pika API")
        
        # Poll for result
        status_url = f"{self.base_url}/{endpoint}/requests/{request_id}/status"
        
        max_attempts = 60  # 5 minutes max
        for attempt in range(max_attempts):
            time.sleep(5)  # Poll every 5 seconds
            
            status_response = requests.get(status_url, headers=headers)
            status_response.raise_for_status()
            status_data = status_response.json()
            
            status = status_data.get("status")
            
            if status == "COMPLETED":
                video_url = status_data.get("video", {}).get("url")
                if video_url:
                    return video_url
                raise ValueError("Video URL not found in completed response")
            
            elif status == "FAILED":
                error = status_data.get("error", "Unknown error")
                raise ValueError(f"Video generation failed: {error}")
        
        raise TimeoutError("Video generation timed out after 5 minutes")
