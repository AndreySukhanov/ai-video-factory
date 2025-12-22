import os
import time
import requests
from typing import Optional, Dict
from app.core.config import settings

class CharacterGenerator:
    """
    Generate consistent character images using fal.ai Instant Character
    """
    
    def __init__(self):
        self.api_key = settings.VIDEO_API_KEY or os.getenv("FAL_KEY")
        self.base_url = "https://queue.fal.run"
        
    def generate_character(
        self,
        name: str,
        description: str,
        style: str = "realistic",
        aspect_ratio: str = "9:16"
    ) -> Dict[str, str]:
        """
        Generate a consistent character image
        
        Args:
            name: Character name
            description: Character description (appearance, clothing, etc.)
            style: Visual style (realistic, anime, cartoon, etc.)
            aspect_ratio: Image aspect ratio
            
        Returns:
            Dict with 'image_url' and 'prompt' used
        """
        if not self.api_key:
            raise ValueError("FAL_KEY not set in environment variables")
        
        # Build character prompt
        prompt = f"{style} portrait of {name}, {description}, 9:16 vertical format, high quality, detailed"
        
        endpoint = "fal-ai/instant-character"
        payload = {
            "prompt": prompt,
            "image_size": {
                "width": 720,
                "height": 1280
            },
            "num_images": 1
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
            raise ValueError("No request_id returned from Character API")
        
        # Poll for result
        status_url = f"{self.base_url}/{endpoint}/requests/{request_id}/status"
        
        max_attempts = 60
        for attempt in range(max_attempts):
            time.sleep(3)
            
            status_response = requests.get(status_url, headers=headers)
            status_response.raise_for_status()
            status_data = status_response.json()
            
            status = status_data.get("status")
            
            if status == "COMPLETED":
                images = status_data.get("images", [])
                if images and len(images) > 0:
                    image_url = images[0].get("url")
                    return {
                        "image_url": image_url,
                        "prompt": prompt
                    }
                raise ValueError("No images in completed response")
            
            elif status == "FAILED":
                error = status_data.get("error", "Unknown error")
                raise ValueError(f"Character generation failed: {error}")
        
        raise TimeoutError("Character generation timed out")
    
    def generate_character_variation(
        self,
        reference_image_url: str,
        new_pose: str = "standing",
        new_expression: str = "neutral"
    ) -> str:
        """
        Generate a variation of an existing character with different pose/expression
        
        Args:
            reference_image_url: URL of the original character image
            new_pose: Desired pose
            new_expression: Desired expression
            
        Returns:
            URL of the new character variation
        """
        # This would use image-to-image with the reference
        # For now, return the reference as-is
        # TODO: Implement variation generation
        return reference_image_url
