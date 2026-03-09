"""
Seedance 2.0 Provider via LaoZhang API.
ByteDance's video generation model — cheapest option with best reference support.

Pricing: $0.05 per video (any duration/resolution)
References: up to 9 images + 3 videos + 3 audio files with weight control
Durations: 4, 5, 8, 10, 15 seconds
Resolutions: 480p, 720p, 1080p, 2k
Aspect ratios: 16:9, 9:16, 4:3, 3:4, 21:9, 1:1
"""

import time
import requests
from typing import Optional, List
from app.core.config import settings
from .video_provider_base import VideoProvider


class SeedanceProvider(VideoProvider):
    """
    Seedance 2.0 via LaoZhang API.
    Submit → poll → download pattern.
    $0.05/video, up to 9 reference images with weight control.
    """

    def __init__(self, aspect_ratio: str = "9:16", resolution: str = "720p"):
        self.api_key = settings.LAOZHANG_API_KEY
        self.base_url = settings.LAOZHANG_BASE_URL.rstrip("/")
        self.default_aspect = aspect_ratio
        self.default_resolution = resolution

        if not self.api_key:
            raise ValueError("LAOZHANG_API_KEY not set (Seedance uses LaoZhang API)")

        print(f"[SEEDANCE] Initialized: model=seedance-2.0, aspect={aspect_ratio}, res={resolution}")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
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
    ) -> str:
        """
        Generate video via Seedance 2.0.
        Returns video download URL (valid ~24h).
        """
        valid_durations = [4, 5, 8, 10, 15]
        if duration_sec not in valid_durations:
            duration_sec = min(valid_durations, key=lambda x: abs(x - duration_sec))

        # Build input
        input_data = {
            "prompt": visual_prompt,
            "duration": duration_sec,
            "resolution": resolution or self.default_resolution,
            "aspect_ratio": aspect_ratio or self.default_aspect,
        }

        if negative_prompt:
            input_data["negative_prompt"] = negative_prompt

        # Build references array
        references = []

        # Single reference image (frame chaining)
        if reference_image_url:
            references.append({
                "type": "image",
                "url": reference_image_url,
                "weight": 0.9,
            })

        # Multiple reference images (character consistency)
        if reference_images:
            for ref_url in reference_images[:8]:  # max 9 total, 1 slot used above
                if ref_url != reference_image_url:
                    references.append({
                        "type": "image",
                        "url": ref_url,
                        "weight": 0.7,
                    })

        if references:
            input_data["references"] = references[:9]
            print(f"[SEEDANCE] {len(references)} reference(s) attached")

        payload = {
            "model": "seedance-2.0",
            "input": input_data,
        }

        ref_str = f", refs={len(references)}" if references else ""
        print(f"[SEEDANCE] Submitting: dur={duration_sec}s, {aspect_ratio}, {resolution}{ref_str}")
        print(f"[SEEDANCE] Prompt: {visual_prompt[:80]}...")

        # Submit
        submit_url = f"{self.base_url}/video/generations"
        resp = requests.post(submit_url, json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        result = resp.json()

        task_id = result.get("id") or result.get("task_id")
        if not task_id:
            video_url = result.get("video_url") or result.get("url")
            if video_url:
                return video_url
            raise ValueError(f"No task_id in Seedance response: {result}")

        print(f"[SEEDANCE] Task submitted: {task_id}")

        # Poll for completion (max 3 minutes — Seedance is fast, median 45-60s)
        poll_url = f"{self.base_url}/video/generations/{task_id}"
        max_wait = 180
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = requests.get(poll_url, headers=self._headers(), timeout=15)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()

            status = poll_data.get("status", "").lower()

            if status in ("completed", "succeeded", "success"):
                video_url = (
                    poll_data.get("video_url")
                    or poll_data.get("output", {}).get("video_url")
                    or poll_data.get("result", {}).get("url")
                )
                if video_url:
                    print(f"[SEEDANCE] Video ready ({elapsed}s): {video_url[:80]}...")
                    return video_url
                raise ValueError(f"Completed but no video URL: {poll_data}")

            if status in ("failed", "error", "cancelled"):
                error_msg = poll_data.get("error") or poll_data.get("message") or "Unknown error"
                raise ValueError(f"Seedance generation failed: {error_msg}")

            if elapsed % 15 == 0:
                progress = poll_data.get("progress", "?")
                print(f"[SEEDANCE] Poll ({elapsed}s): status={status}, progress={progress}%")

            if elapsed > 60:
                poll_interval = 10

        raise TimeoutError(f"Seedance generation timed out after {max_wait}s (task_id={task_id})")
