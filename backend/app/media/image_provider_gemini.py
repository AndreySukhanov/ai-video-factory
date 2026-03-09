"""
Gemini Image Provider (Nano Banana) — keyframe/storyboard generation.
Uses Gemini 3.1 Flash Image Preview for fast, cheap storyboard frames.

Pipeline: anchor_prompt + variable per episode → consistent keyframe images.
Same seed for all frames → character/setting consistency.
"""

import os
import uuid
import base64
import requests
from typing import Optional
from app.core.config import settings


class GeminiImageProvider:
    """
    Generates storyboard keyframes via Gemini Image Generation (Nano Banana).
    Same API key as GeminiVeoProvider.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    MODEL = "gemini-3.1-flash-image-preview"

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")

        self.static_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "static", "storyboard",
        )
        os.makedirs(self.static_dir, exist_ok=True)

    # Root directory for resolving local paths (/uploads/xxx.jpg, /static/xxx.png)
    _BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    def _load_image_bytes(self, url: str) -> bytes | None:
        """Load image bytes from local file or URL. Prefers local files."""
        # Try local path first: /uploads/xxx.jpg or /static/storyboard/xxx.png
        if url.startswith("/uploads/") or url.startswith("/static/"):
            local_path = os.path.join(self._BACKEND_ROOT, url.lstrip("/"))
            if os.path.isfile(local_path):
                print(f"[NANO-BANANA] Reading local file: {local_path}")
                with open(local_path, "rb") as f:
                    return f.read()

        # Try to extract local path from backend URL (http://localhost:8000/uploads/xxx.jpg)
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        if url.startswith(backend_url):
            rel_path = url[len(backend_url):].lstrip("/")
            local_path = os.path.join(self._BACKEND_ROOT, rel_path)
            if os.path.isfile(local_path):
                print(f"[NANO-BANANA] Reading local file from backend URL: {local_path}")
                with open(local_path, "rb") as f:
                    return f.read()

        # Try catbox/external URL — extract filename and check uploads dir
        if "/uploads/" not in url:
            # Check if the catbox filename matches a local upload
            filename = url.rsplit("/", 1)[-1] if "/" in url else None
            if filename:
                local_path = os.path.join(self._BACKEND_ROOT, "uploads", filename)
                if os.path.isfile(local_path):
                    print(f"[NANO-BANANA] Found local match for external URL: {local_path}")
                    with open(local_path, "rb") as f:
                        return f.read()

        # Fallback: HTTP download
        print(f"[NANO-BANANA] Downloading reference via HTTP: {url[:60]}...")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content

    # System instruction to enforce single-frame output and character consistency
    KEYFRAME_SYSTEM = (
        "Generate exactly ONE single photorealistic keyframe image. "
        "NOT a collage, NOT a grid, NOT multiple panels — ONE image only. "
        "The character's clothing and appearance MUST match the description EXACTLY "
        "regardless of the action in the scene. Never change the character's outfit."
    )

    def generate_keyframe(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        seed: Optional[int] = None,
        reference_images: Optional[list[str]] = None,
    ) -> str:
        """
        Generate a single storyboard keyframe image.

        Args:
            prompt: Full visual prompt (anchor + variable combined)
            aspect_ratio: Image aspect ratio
            seed: Fixed seed for consistency across frames

        Returns:
            URL path to the saved image (relative to backend)
        """
        url = f"{self.BASE_URL}/models/{self.MODEL}:generateContent?key={self.api_key}"

        # Build multimodal parts: reference images first, then text prompt
        content_parts = []
        if reference_images:
            for img_url in reference_images:
                try:
                    img_bytes = self._load_image_bytes(img_url)
                    if img_bytes:
                        img_b64 = base64.b64encode(img_bytes).decode()
                        content_type = "image/jpeg"
                        if img_url.endswith(".png"):
                            content_type = "image/png"
                        elif img_url.endswith(".webp"):
                            content_type = "image/webp"
                        content_parts.append({
                            "inlineData": {"mimeType": content_type, "data": img_b64}
                        })
                        print(f"[NANO-BANANA] Reference loaded: {img_url[:60]} ({len(img_bytes)//1024}KB)")
                except Exception as e:
                    print(f"[NANO-BANANA] Failed to load reference {img_url[:40]}: {e}")

        content_parts.append({"text": f"{self.KEYFRAME_SYSTEM}\n\n{prompt}"})

        payload = {
            "contents": [{"parts": content_parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                },
            },
        }

        if seed is not None:
            payload["generationConfig"]["seed"] = seed

        print(f"[NANO-BANANA] Generating keyframe: {prompt[:60]}...")

        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # Extract image from response
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        image_data = None
        mime_type = "image/png"

        for part in parts:
            if "inlineData" in part:
                image_data = part["inlineData"]["data"]
                mime_type = part["inlineData"].get("mimeType", "image/png")
                break

        if not image_data:
            raise ValueError(f"No image in Nano Banana response: {data.get('candidates', [{}])[0].get('finishReason', 'unknown')}")

        # Decode and save
        image_bytes = base64.b64decode(image_data)
        ext = "png" if "png" in mime_type else "jpg"
        filename = f"sb_{uuid.uuid4().hex[:10]}.{ext}"
        filepath = os.path.join(self.static_dir, filename)

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        # Convert PNG→JPEG if > 4MB (prevent 413 on future I2V usage)
        if ext == "png" and len(image_bytes) > 4 * 1024 * 1024:
            try:
                from PIL import Image
                img = Image.open(filepath)
                jpeg_filename = filename.replace(".png", ".jpg")
                jpeg_path = os.path.join(self.static_dir, jpeg_filename)
                img.convert("RGB").save(jpeg_path, "JPEG", quality=90)
                os.unlink(filepath)
                filename = jpeg_filename
                print(f"[NANO-BANANA] Converted PNG→JPEG (was {len(image_bytes)//1024}KB)")
            except ImportError:
                pass  # PIL not available, keep PNG

        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        image_url = f"{backend_url}/static/storyboard/{filename}"

        print(f"[NANO-BANANA] Keyframe saved: {image_url}")
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
        Uses character_card + anchor_prompt + each episode's variable prompt for consistency.

        Priority order in prompt: character_card → anchor_prompt → episode action.
        Character card goes FIRST to force the model to render consistent appearance.

        Args:
            anchor_prompt: Shared visual description (camera, character, setting, lighting)
            episode_prompts: List of variable prompts (one per episode)
            aspect_ratio: Image aspect ratio
            seed: Fixed seed for all frames (auto-generated if None)
            character_card: Fixed character appearance description (<=50 words)

        Returns:
            List of image URLs (one per episode)
        """
        if seed is None:
            import random
            seed = random.randint(1, 999999)

        valid_refs = [u for u in (reference_image_urls or []) if u and u.strip()]
        print(f"[NANO-BANANA] Generating storyboard: {len(episode_prompts)} frames, seed={seed}, refs={len(valid_refs)}")
        if character_card:
            print(f"[NANO-BANANA] Character card: {character_card[:80]}")

        keyframes = []
        for i, variable_prompt in enumerate(episode_prompts):
            # Build prompt: character_card FIRST (appearance lock) → anchor → action
            parts = []
            if character_card:
                parts.append(f"CHARACTER (keep EXACTLY this appearance in every frame): {character_card}")
            if anchor_prompt:
                parts.append(anchor_prompt)
            parts.append(variable_prompt)
            full_prompt = ". ".join(parts)

            for attempt in range(2):
                try:
                    url = self.generate_keyframe(
                        prompt=full_prompt,
                        aspect_ratio=aspect_ratio,
                        seed=seed,
                        reference_images=valid_refs if valid_refs else None,
                    )
                    keyframes.append(url)
                    print(f"[NANO-BANANA] Frame {i+1}/{len(episode_prompts)} done")
                    break
                except Exception as e:
                    if attempt == 0:
                        print(f"[NANO-BANANA] Frame {i+1} attempt 1 failed: {e}, retrying...")
                    else:
                        print(f"[NANO-BANANA] Frame {i+1} failed after retry: {e}")
                        keyframes.append("")  # Empty = failed

        success_count = sum(1 for k in keyframes if k)
        print(f"[NANO-BANANA] Storyboard complete: {success_count}/{len(episode_prompts)} frames")
        return keyframes
