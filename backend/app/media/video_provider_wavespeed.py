"""
WaveSpeed AI — Seedance 2.0 (image-to-video / text-to-video).

Docs: https://wavespeed.ai/docs
Endpoints:
  POST {base}/bytedance/seedance-2.0-image-to-video
  POST {base}/bytedance/seedance-2.0-text-to-video
  GET  {base}/predictions/{task_id}

Auth: Bearer WAVESPEED_API_KEY.
Submit returns task id (`pred_*`), then poll until status=completed.
"""

import time
import requests
from typing import Optional, List
from app.core.config import settings
from .video_provider_base import VideoProvider


WAVESPEED_VALID_RATIOS = {"16:9", "9:16", "1:1", "3:4", "4:3", "21:9"}
WAVESPEED_VALID_DURATIONS = [4, 5, 8, 10, 15]


class WavespeedSeedanceProvider(VideoProvider):
    """Seedance 2.0 via WaveSpeed AI."""

    def __init__(self, aspect_ratio: str = "9:16", use_fast: bool = True):
        self.api_key = settings.WAVESPEED_API_KEY
        self.base_url = settings.WAVESPEED_BASE_URL.rstrip("/")
        self.default_aspect = aspect_ratio if aspect_ratio in WAVESPEED_VALID_RATIOS else "9:16"
        self.use_fast = use_fast

        if not self.api_key:
            raise ValueError("WAVESPEED_API_KEY not set")

        print(f"[WAVESPEED] Initialized: aspect={self.default_aspect}, fast={use_fast}")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _submit_url(self, has_image: bool) -> str:
        suffix = "image-to-video" if has_image else "text-to-video"
        return f"{self.base_url}/bytedance/seedance-2.0-{suffix}"

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
        seed: Optional[int] = None,
    ) -> str:
        if duration_sec not in WAVESPEED_VALID_DURATIONS:
            duration_sec = min(WAVESPEED_VALID_DURATIONS, key=lambda x: abs(x - duration_sec))

        ratio = aspect_ratio if aspect_ratio in WAVESPEED_VALID_RATIOS else self.default_aspect

        primary_image = reference_image_url or last_frame_image_url
        extra_images: List[str] = []
        if reference_images:
            seen = {primary_image}
            for url in reference_images:
                if url and url not in seen:
                    extra_images.append(url)
                    seen.add(url)
                    if len(extra_images) >= 8:
                        break

        payload = {
            "prompt": visual_prompt,
            "aspect_ratio": ratio,
            "duration": duration_sec,
            "resolution": resolution,
            "generate_audio": generate_audio,
        }
        if seed is not None:
            payload["seed"] = seed
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        if primary_image:
            payload["image_url"] = primary_image
            if extra_images:
                payload["reference_images"] = extra_images
            submit_url = self._submit_url(has_image=True)
        else:
            submit_url = self._submit_url(has_image=False)

        print(f"[WAVESPEED] Submitting: dur={duration_sec}s, ratio={ratio}, image={'yes' if primary_image else 'no'}")
        print(f"[WAVESPEED] Prompt: {visual_prompt[:80]}...")

        resp = requests.post(submit_url, json=payload, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except ValueError:
                err = resp.text
            raise ValueError(f"WaveSpeed submit failed: HTTP {resp.status_code} — {err}")

        data = resp.json()
        # Response shape: {"code": 200, "data": {"id": "pred_...", ...}} or flat {"id": ...}
        body = data.get("data") if isinstance(data.get("data"), dict) else data
        task_id = body.get("id") or body.get("task_id") or body.get("prediction_id")
        if not task_id:
            raise ValueError(f"No task_id in WaveSpeed response: {data}")

        print(f"[WAVESPEED] Task submitted: {task_id}")

        poll_url = f"{self.base_url}/predictions/{task_id}/result"
        # WaveSpeed also exposes /predictions/{id}; both return the same payload.
        max_wait = 600
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = requests.get(poll_url, headers=self._headers(), timeout=15)
            if poll_resp.status_code == 404:
                # fallback to /predictions/{id}
                poll_resp = requests.get(
                    f"{self.base_url}/predictions/{task_id}",
                    headers=self._headers(),
                    timeout=15,
                )
            if poll_resp.status_code >= 400:
                try:
                    err = poll_resp.json()
                except ValueError:
                    err = poll_resp.text
                raise ValueError(f"WaveSpeed poll failed: HTTP {poll_resp.status_code} — {err}")

            poll_data = poll_resp.json()
            body = poll_data.get("data") if isinstance(poll_data.get("data"), dict) else poll_data
            status = (body.get("status") or "").lower()

            if status in ("completed", "succeeded", "success"):
                outputs = body.get("outputs") or body.get("output") or []
                video_url = None
                if isinstance(outputs, list) and outputs:
                    video_url = outputs[0] if isinstance(outputs[0], str) else (
                        outputs[0].get("url") if isinstance(outputs[0], dict) else None
                    )
                video_url = video_url or body.get("video_url") or body.get("url")
                if video_url:
                    print(f"[WAVESPEED] Video ready ({elapsed}s): {video_url[:80]}...")
                    return video_url
                raise ValueError(f"Completed but no video URL: {body}")

            if status in ("failed", "error", "cancelled"):
                error_msg = body.get("error") or body.get("message") or "Unknown error"
                raise ValueError(f"WaveSpeed generation failed: {error_msg}")

            if elapsed % 15 == 0:
                print(f"[WAVESPEED] Poll ({elapsed}s): status={status or 'pending'}")

            if elapsed > 60:
                poll_interval = 10

        raise TimeoutError(f"WaveSpeed generation timed out after {max_wait}s (task_id={task_id})")
