"""
FLUX Schnell Image Provider — storyboard/keyframe generation via Replicate.
Uses black-forest-labs/flux-schnell ($0.003/image) for fast storyboard frames.

Requires: REPLICATE_API_TOKEN
"""

import os
import uuid
import requests
import replicate
from typing import Optional
from app.core.config import settings


class FluxImageProvider:
    """
    Generates storyboard keyframes via FLUX Schnell on Replicate.
    Same interface as GeminiImageProvider / SeedreamImageProvider.
    """

    def __init__(self):
        self.api_token = settings.REPLICATE_API_TOKEN or os.getenv("REPLICATE_API_TOKEN")
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN not set")
        os.environ["REPLICATE_API_TOKEN"] = self.api_token

        self.static_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "static", "storyboard",
        )
        os.makedirs(self.static_dir, exist_ok=True)

    KEYFRAME_SYSTEM = (
        "Professional photorealistic single keyframe image. "
        "NOT a collage, NOT a grid, NOT multiple panels — ONE image only. "
        "The character's clothing and appearance MUST match the description EXACTLY."
    )

    def generate_keyframe(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        seed: Optional[int] = None,
    ) -> str:
        """
        Generate a single storyboard keyframe via FLUX Schnell.

        Returns:
            URL path to the saved image on backend static server.
        """
        full_prompt = f"{self.KEYFRAME_SYSTEM}\n\n{prompt}"

        input_data = {
            "prompt": full_prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": "jpg",
            "output_quality": 90,
            "num_outputs": 1,
        }
        if seed is not None:
            input_data["seed"] = seed

        print(f"[FLUX] Generating keyframe: {prompt[:60]}...")

        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input=input_data,
        )

        if not output or len(output) == 0:
            raise ValueError("No images returned from FLUX Schnell")

        remote_url = str(output[0])
        print(f"[FLUX] Remote image: {remote_url[:80]}")

        # Download and save locally (Replicate URLs expire)
        resp = requests.get(remote_url, timeout=30)
        resp.raise_for_status()

        filename = f"sb_{uuid.uuid4().hex[:10]}.jpg"
        filepath = os.path.join(self.static_dir, filename)
        with open(filepath, "wb") as f:
            f.write(resp.content)

        backend_url = settings.BACKEND_URL or "http://localhost:8000"
        image_url = f"{backend_url}/static/storyboard/{filename}"

        print(f"[FLUX] Keyframe saved: {image_url}")
        return image_url

    def generate_storyboard(
        self,
        anchor_prompt: str,
        episode_prompts: list[str],
        aspect_ratio: str = "9:16",
        seed: Optional[int] = None,
        character_card: str = "",
        reference_image_urls: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Generate storyboard keyframes for all episodes.
        Same interface as GeminiImageProvider.generate_storyboard().
        """
        if seed is None:
            import random
            seed = random.randint(1, 999999)

        print(f"[FLUX] Generating storyboard: {len(episode_prompts)} frames, seed={seed}")
        if character_card:
            print(f"[FLUX] Character card: {character_card[:80]}")

        keyframes = []
        for i, variable_prompt in enumerate(episode_prompts):
            parts = []
            if character_card:
                parts.append(f"CHARACTER (keep EXACTLY this appearance in every frame): {character_card}")
            if anchor_prompt:
                parts.append(anchor_prompt)
            parts.append(variable_prompt)
            full_prompt = ". ".join(parts)

            try:
                url = self.generate_keyframe(
                    prompt=full_prompt,
                    aspect_ratio=aspect_ratio,
                    seed=seed,
                )
                keyframes.append(url)
                print(f"[FLUX] Frame {i+1}/{len(episode_prompts)} done")
            except Exception as e:
                print(f"[FLUX] Frame {i+1} failed: {e}")
                keyframes.append("")

        success_count = sum(1 for k in keyframes if k)
        print(f"[FLUX] Storyboard complete: {success_count}/{len(episode_prompts)} frames")
        return keyframes
