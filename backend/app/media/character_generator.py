import os
import time
import replicate
from typing import Optional, Dict
from app.core.config import settings


class CharacterGenerator:
    """
    Generate consistent character images using Replicate FLUX model
    """

    def __init__(self):
        self.api_token = settings.REPLICATE_API_TOKEN or os.getenv("REPLICATE_API_TOKEN")
        if self.api_token:
            os.environ["REPLICATE_API_TOKEN"] = self.api_token

    def generate_character(
        self,
        name: str,
        description: str,
        style: str = "realistic",
        aspect_ratio: str = "9:16"
    ) -> Dict[str, str]:
        """
        Generate a consistent character image using Replicate FLUX

        Args:
            name: Character name
            description: Character description (appearance, clothing, etc.)
            style: Visual style (realistic, anime, cartoon, etc.)
            aspect_ratio: Image aspect ratio

        Returns:
            Dict with 'image_url' and 'prompt' used
        """
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN not set in environment variables")

        # Map aspect ratio to Replicate format
        aspect_ratio_map = {
            "9:16": "9:16",
            "16:9": "16:9",
            "1:1": "1:1"
        }
        replicate_aspect = aspect_ratio_map.get(aspect_ratio, "9:16")

        # Build enhanced character prompt for better quality
        prompt = f"""Professional {style} full body portrait photograph of {name}, {description}.
Standing pose, facing camera, clear facial features visible, sharp focus on face.
Studio quality, professional lighting, 8k resolution, highly detailed.
Photorealistic skin texture, natural expression, cinematic color grading."""

        print(f"[CHARACTER GENERATOR] Generating character: {name}")
        print(f"[CHARACTER GENERATOR] Prompt: {prompt[:200]}...")
        print(f"[CHARACTER GENERATOR] Aspect ratio: {replicate_aspect}")

        try:
            # Use FLUX Schnell for fast generation
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "aspect_ratio": replicate_aspect,
                    "output_format": "png",
                    "output_quality": 90,
                    "num_outputs": 1
                }
            )

            # Output is a list of FileOutput objects
            if output and len(output) > 0:
                image_url = str(output[0])
                print(f"[CHARACTER GENERATOR] Generated image: {image_url}")
                return {
                    "image_url": image_url,
                    "prompt": prompt
                }
            else:
                raise ValueError("No images returned from Replicate")

        except Exception as e:
            print(f"[CHARACTER GENERATOR] Error: {e}")
            raise ValueError(f"Character generation failed: {e}")

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
