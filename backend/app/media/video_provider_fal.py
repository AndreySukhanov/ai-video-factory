"""
fal.ai Video Provider — Kling 2.1 via fal.ai REST queue API.
Used as fallback when LaoZhang/Seedance returns 503.

Pricing: ~$0.13/video (5s), ~$0.26/video (10s)
Uptime: 99.99% (no contractual SLA but historically very stable)
API: https://queue.fal.run/{model-id}
Auth: Authorization: Key {FAL_KEY}
"""

import time
import requests
from typing import Optional, List
from app.core.config import settings
from .video_provider_base import VideoProvider


class FalKlingProvider(VideoProvider):
    """
    fal.ai Kling 2.1 — used as fallback for LaoZhang 503 errors.
    Submit → poll → result pattern (same as LaoZhang).
    Supports text-to-video and image-to-video.
    """

    TEXT_TO_VIDEO = "fal-ai/kling-video/v2.1/standard/text-to-video"
    IMAGE_TO_VIDEO = "fal-ai/kling-video/v2.1/standard/image-to-video"

    FAL_BASE = "https://queue.fal.run"

    def __init__(self, aspect_ratio: str = "9:16"):
        self.api_key = settings.FAL_KEY
        self.default_aspect = aspect_ratio

        if not self.api_key:
            raise ValueError("FAL_KEY not set")

        print(f"[FAL] Initialized: model=kling-v2.1, aspect={aspect_ratio}")

    def _headers(self):
        return {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_clip(
        self,
        visual_prompt: str,
        duration_sec: int,
        *,
        aspect_ratio: str = "9:16",
        reference_image_url: Optional[str] = None,
        last_frame_image_url: Optional[str] = None,
        reference_images: Optional[List[str]] = None,
        resolution: str = "720p",
        generate_audio: bool = True,
        negative_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Submit generation task to fal.ai Kling 2.1, poll until complete.
        Returns URL of the generated video.
        """
        # Kling supports 5 or 10 seconds
        valid_durations = [5, 10]
        if duration_sec not in valid_durations:
            duration_sec = min(valid_durations, key=lambda x: abs(x - duration_sec))

        # Choose endpoint: image-to-video if reference provided
        ref_url = reference_image_url or (reference_images[0] if reference_images else None)
        if ref_url:
            model_id = self.IMAGE_TO_VIDEO
            payload = {
                "prompt": visual_prompt,
                "image_url": ref_url,
                "duration": str(duration_sec),
                "aspect_ratio": aspect_ratio or self.default_aspect,
            }
            print(f"[FAL] Image-to-video: dur={duration_sec}s, {aspect_ratio}")
        else:
            model_id = self.TEXT_TO_VIDEO
            payload = {
                "prompt": visual_prompt,
                "duration": str(duration_sec),
                "aspect_ratio": aspect_ratio or self.default_aspect,
            }
            print(f"[FAL] Text-to-video: dur={duration_sec}s, {aspect_ratio}")

        print(f"[FAL] Prompt: {visual_prompt[:80]}...")

        # Submit to fal.ai queue
        submit_url = f"{self.FAL_BASE}/{model_id}"
        resp = requests.post(submit_url, json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        result = resp.json()

        request_id = result.get("request_id")
        if not request_id:
            raise ValueError(f"No request_id in fal.ai response: {result}")

        print(f"[FAL] Task submitted: {request_id}")

        # Poll status (max 5 minutes)
        status_url = f"{self.FAL_BASE}/{model_id}/requests/{request_id}/status"
        result_url = f"{self.FAL_BASE}/{model_id}/requests/{request_id}"
        max_wait = 300
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            status_resp = requests.get(status_url, headers=self._headers(), timeout=15)
            status_resp.raise_for_status()
            status_data = status_resp.json()

            status = status_data.get("status", "").lower()
            print(f"[FAL] Poll ({elapsed}s): status={status}")

            if status == "completed":
                # Fetch actual result
                res_resp = requests.get(result_url, headers=self._headers(), timeout=15)
                res_resp.raise_for_status()
                res_data = res_resp.json()

                video_url = (
                    res_data.get("video", {}).get("url")
                    or res_data.get("video_url")
                    or res_data.get("url")
                )
                if video_url:
                    print(f"[FAL] Video ready ({elapsed}s): {video_url[:80]}...")
                    return video_url
                raise ValueError(f"Completed but no video URL: {res_data}")

            if status in ("failed", "error"):
                error_msg = status_data.get("error") or status_data.get("detail") or "Unknown error"
                raise ValueError(f"fal.ai generation failed: {error_msg}")

            if elapsed > 60:
                poll_interval = 10

        raise TimeoutError(f"fal.ai generation timed out after {max_wait}s (request_id={request_id})")
