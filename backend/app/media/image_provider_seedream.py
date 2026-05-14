"""
Seedream 5.0 Image Provider — storyboard/keyframe generation via LaoZhang API.

2K resolution, strong character consistency, superior text rendering.
Native ByteDance Volces backend (seedream-5-0-260128, released Jan 2026).

Uses OpenAI-compatible /v1/images/generations endpoint from LaoZhang.
Note: seedream-5 takes `aspect_ratio` (NOT `size`) — differs from seedream-4-5.
"""

import os
import uuid
import base64
import requests
from typing import Optional
from app.core.config import settings


class SeedreamImageProvider:
    """
    Generates storyboard keyframes via Seedream 5.0 (LaoZhang API).
    Same interface as GeminiImageProvider for drop-in replacement.
    """

    MODEL = "seedream-5-0-260128"

    def __init__(self):
        self.api_key = settings.LAOZHANG_API_KEY
        self.base_url = settings.LAOZHANG_BASE_URL.rstrip("/")

        if not self.api_key:
            raise ValueError("LAOZHANG_API_KEY not set (required for Seedream 4.5)")

        self.static_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "static", "storyboard",
        )
        os.makedirs(self.static_dir, exist_ok=True)

    KEYFRAME_SYSTEM = (
        "Generate exactly ONE single keyframe image — NOT a collage, NOT a grid, NOT multiple panels.\n"
        "STYLE LOCK: cinematic live-action photography, shot on Arri Alexa, 35mm lens, "
        "shallow depth of field, photorealistic skin texture, natural film grain, "
        "soft naturalistic lighting. EVERY frame in this series MUST share this EXACT same "
        "cinematic photographic style.\n"
        "STRICT NEGATIVE STYLES (do NOT produce): anime, manga, comic book, graphic novel, "
        "illustration, cartoon, 3D render, CGI animation, painterly, oil painting, watercolor, "
        "pixar style, disney style, cel-shaded, stylized art.\n"
        "IDENTITY LOCK: the character's face, age, ethnicity, hair, eye color, and outfit "
        "MUST match the description EXACTLY in every frame. Never restyle the character. "
        "Never age the character up or down. Never change the outfit color or cut."
    )

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_keyframe(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        seed: Optional[int] = None,
    ) -> str:
        """
        Generate a single storyboard keyframe via Seedream 4.5.

        Args:
            prompt: Full visual prompt (anchor + variable combined)
            aspect_ratio: Image aspect ratio
            seed: Fixed seed for consistency across frames

        Returns:
            URL path to the saved image (relative to backend)
        """
        full_prompt = f"{self.KEYFRAME_SYSTEM}\n\n{prompt}"

        url = f"{self.base_url}/images/generations"

        payload = {
            "model": self.MODEL,
            "prompt": full_prompt,
            "aspect_ratio": aspect_ratio,
            "response_format": "b64_json",
            "n": 1,
        }

        if seed is not None:
            payload["seed"] = seed

        print(f"[SEEDREAM] Generating keyframe: {prompt[:60]}...")

        last_err = None
        for attempt in range(2):
            try:
                resp = requests.post(url, json=payload, headers=self._headers(), timeout=180)
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.exceptions.Timeout as e:
                last_err = e
                print(f"[SEEDREAM] Timeout on attempt {attempt+1}, retrying...")
        else:
            raise last_err

        # Extract image from OpenAI-compatible response
        images = data.get("data", [])
        if not images:
            raise ValueError(f"No image in Seedream response: {data}")

        image_b64 = images[0].get("b64_json")
        if not image_b64:
            # Some APIs return URL instead
            image_url = images[0].get("url")
            if image_url:
                return self._download_and_save(image_url)
            raise ValueError(f"No b64_json or url in Seedream response: {images[0].keys()}")

        # Decode and save
        image_bytes = base64.b64decode(image_b64)
        filename = f"sd_{uuid.uuid4().hex[:10]}.png"
        filepath = os.path.join(self.static_dir, filename)

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        # Convert PNG → JPEG if > 4MB
        if len(image_bytes) > 4 * 1024 * 1024:
            try:
                from PIL import Image
                img = Image.open(filepath)
                jpeg_filename = filename.replace(".png", ".jpg")
                jpeg_path = os.path.join(self.static_dir, jpeg_filename)
                img.convert("RGB").save(jpeg_path, "JPEG", quality=90)
                os.unlink(filepath)
                filename = jpeg_filename
                print(f"[SEEDREAM] Converted PNG→JPEG (was {len(image_bytes)//1024}KB)")
            except ImportError:
                pass

        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        image_url = f"{backend_url}/static/storyboard/{filename}"

        print(f"[SEEDREAM] Keyframe saved: {image_url}")
        return image_url

    def _download_and_save(self, url: str) -> str:
        """Download image from URL and save locally."""
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        ext = "jpg" if "jpeg" in resp.headers.get("content-type", "") else "png"
        filename = f"sd_{uuid.uuid4().hex[:10]}.{ext}"
        filepath = os.path.join(self.static_dir, filename)

        with open(filepath, "wb") as f:
            f.write(resp.content)

        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        image_url = f"{backend_url}/static/storyboard/{filename}"
        print(f"[SEEDREAM] Keyframe downloaded & saved: {image_url}")
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

        print(f"[SEEDREAM] Generating storyboard: {len(episode_prompts)} frames, seed={seed}")
        if character_card:
            print(f"[SEEDREAM] Character card: {character_card[:80]}")

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
                print(f"[SEEDREAM] Frame {i+1}/{len(episode_prompts)} done")
            except Exception as e:
                print(f"[SEEDREAM] Frame {i+1} failed: {e}")
                keyframes.append("")  # Empty = failed

        success_count = sum(1 for k in keyframes if k)
        print(f"[SEEDREAM] Storyboard complete: {success_count}/{len(episode_prompts)} frames")
        return keyframes
