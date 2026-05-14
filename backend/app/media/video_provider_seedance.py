"""
Seedance 2.0 Provider via LaoZhang API.
ByteDance's video generation model — cheapest option with multimodal references.

Docs: https://docs.laozhang.ai/api-capabilities/seedance2-video-generation
Endpoint: POST /v1/videos (submit), GET /v1/videos/{id} (poll)
Models:
  - doubao-seedance-2-0-fast-260128   (fast variant)
  - doubao-seedance-2-0-260128        (standard variant)

Pricing: $0.05 per video
Durations: 4, 5, 8, 10, 15 seconds
Aspect ratios: 16:9, 9:16, 1:1, 3:4, 4:3, 21:9
References: multimodal `content` array (image_url / video_url / audio_url)
"""

import time
import requests
from typing import Optional, List
from app.core.config import settings
from .video_provider_base import VideoProvider


SEEDANCE_VALID_RATIOS = {"16:9", "9:16", "1:1", "3:4", "4:3", "21:9"}
SEEDANCE_VALID_DURATIONS = [4, 5, 8, 10, 15]


class SeedanceProvider(VideoProvider):
    """
    Seedance 2.0 via LaoZhang API.
    Submit → poll → download pattern.
    """

    def __init__(self, aspect_ratio: str = "9:16", use_fast: bool = True):
        self.api_key = settings.LAOZHANG_API_KEY
        self.base_url = settings.LAOZHANG_BASE_URL.rstrip("/")
        self.default_aspect = aspect_ratio if aspect_ratio in SEEDANCE_VALID_RATIOS else "9:16"
        self.model_name = (
            "doubao-seedance-2-0-fast-260128" if use_fast
            else "doubao-seedance-2-0-260128"
        )

        if not self.api_key:
            raise ValueError("LAOZHANG_API_KEY not set (Seedance uses LaoZhang API)")

        print(f"[SEEDANCE] Initialized: model={self.model_name}, aspect={self.default_aspect}")

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
        resolution: str = "720p",  # ignored — not supported by Seedance
        generate_audio: bool = True,
        negative_prompt: Optional[str] = None,  # ignored — not supported by Seedance
    ) -> str:
        """
        Generate video via Seedance 2.0.
        Returns video download URL.
        """
        if duration_sec not in SEEDANCE_VALID_DURATIONS:
            duration_sec = min(SEEDANCE_VALID_DURATIONS, key=lambda x: abs(x - duration_sec))

        ratio = aspect_ratio if aspect_ratio in SEEDANCE_VALID_RATIOS else self.default_aspect

        payload = {
            "model": self.model_name,
            "prompt": visual_prompt,
            "ratio": ratio,
            "duration": duration_sec,
            "watermark": False,
            "generate_audio": generate_audio,
        }

        content = []
        if reference_image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": reference_image_url},
                "role": "reference_image",
            })
        if last_frame_image_url and last_frame_image_url != reference_image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": last_frame_image_url},
                "role": "reference_image",
            })
        if reference_images:
            seen = {reference_image_url, last_frame_image_url}
            for ref_url in reference_images:
                if ref_url and ref_url not in seen:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": ref_url},
                        "role": "reference_image",
                    })
                    seen.add(ref_url)
                    if len(content) >= 9:
                        break

        if content:
            payload["content"] = content[:9]
            print(f"[SEEDANCE] {len(payload['content'])} reference(s) attached")

        print(f"[SEEDANCE] Submitting: dur={duration_sec}s, ratio={ratio}, model={self.model_name}")
        print(f"[SEEDANCE] Prompt: {visual_prompt[:80]}...")

        submit_url = f"{self.base_url}/videos"
        resp = requests.post(submit_url, json=payload, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except ValueError:
                err = resp.text
            raise ValueError(f"Seedance submit failed: HTTP {resp.status_code} — {err}")
        result = resp.json()

        task_id = result.get("id") or result.get("task_id")
        if not task_id:
            video_url = result.get("video_url") or result.get("url")
            if video_url:
                return video_url
            raise ValueError(f"No task_id in Seedance response: {result}")

        print(f"[SEEDANCE] Task submitted: {task_id}")

        poll_url = f"{self.base_url}/videos/{task_id}"
        max_wait = 300
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = requests.get(poll_url, headers=self._headers(), timeout=15)
            if poll_resp.status_code >= 400:
                try:
                    err = poll_resp.json()
                except ValueError:
                    err = poll_resp.text
                raise ValueError(f"Seedance poll failed: HTTP {poll_resp.status_code} — {err}")
            poll_data = poll_resp.json()

            status = poll_data.get("status", "").lower()

            if status in ("completed", "succeeded", "success"):
                video_url = (
                    poll_data.get("video_url")
                    or poll_data.get("url")
                    or (poll_data.get("output") or {}).get("video_url")
                    or (poll_data.get("result") or {}).get("url")
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
