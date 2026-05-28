"""
WaveSpeed AI — Seedance 2.0 (image-to-video / text-to-video).

Docs: https://wavespeed.ai/docs   Model catalog: GET /api/v3/models
Endpoints (verified against the live catalog):
  POST {base}/bytedance/seedance-2.0/image-to-video        ($0.6)
  POST {base}/bytedance/seedance-2.0/text-to-video         ($0.6)
  POST {base}/bytedance/seedance-2.0-fast/image-to-video   ($0.5)
  POST {base}/bytedance/seedance-2.0-fast/text-to-video    ($0.5)
  GET  {base}/predictions/{id}/result   (poll; submit returns this in data.urls.get)

Auth: Bearer WAVESPEED_API_KEY.
Submit → {data:{id, status:"created", urls:{get}, outputs:[]}}.
Poll until data.status=="completed", video in data.outputs[0].

Schema notes (per /api/v3/models):
  image-to-video required: prompt, image. optional: last_image, aspect_ratio,
    duration, resolution, generate_audio, enable_web_search.
  text-to-video required: prompt. optional: reference_images (array),
    aspect_ratio, duration, resolution, generate_audio, ...
  No seed / negative_prompt fields on Seedance 2.0 — do not send them.
"""

import time
import requests
from typing import Optional, List
from app.core.config import settings
from .video_provider_base import VideoProvider


WAVESPEED_VALID_RATIOS = {"16:9", "9:16", "4:3", "3:4", "1:1", "21:9"}
WAVESPEED_VALID_DURATIONS = [4, 5, 8, 10, 15]
WAVESPEED_VALID_RESOLUTIONS = {"480p", "720p", "1080p"}


class WavespeedSeedanceProvider(VideoProvider):
    """Seedance 2.0 via WaveSpeed AI."""

    def __init__(self, aspect_ratio: str = "9:16", use_fast: bool = True):
        self.api_key = settings.WAVESPEED_API_KEY
        self.base_url = settings.WAVESPEED_BASE_URL.rstrip("/")
        self.default_aspect = aspect_ratio if aspect_ratio in WAVESPEED_VALID_RATIOS else "9:16"
        self.model_slug = "seedance-2.0-fast" if use_fast else "seedance-2.0"

        if not self.api_key:
            raise ValueError("WAVESPEED_API_KEY not set")

        print(f"[WAVESPEED] Initialized: model={self.model_slug}, aspect={self.default_aspect}")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _submit_url(self, has_image: bool) -> str:
        suffix = "image-to-video" if has_image else "text-to-video"
        return f"{self.base_url}/bytedance/{self.model_slug}/{suffix}"

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
        negative_prompt: Optional[str] = None,  # ignored — Seedance 2.0 has no negative prompt
        seed: Optional[int] = None,             # ignored — Seedance 2.0 has no seed field
    ) -> str:
        if duration_sec not in WAVESPEED_VALID_DURATIONS:
            duration_sec = min(WAVESPEED_VALID_DURATIONS, key=lambda x: abs(x - duration_sec))

        ratio = aspect_ratio if aspect_ratio in WAVESPEED_VALID_RATIOS else self.default_aspect
        res = resolution if resolution in WAVESPEED_VALID_RESOLUTIONS else "720p"

        primary_image = reference_image_url or last_frame_image_url

        payload = {
            "prompt": visual_prompt,
            "aspect_ratio": ratio,
            "duration": int(duration_sec),
            "resolution": res,
            "generate_audio": generate_audio,
        }

        if primary_image:
            # image-to-video: `image` (required) + optional distinct `last_image`
            payload["image"] = primary_image
            if last_frame_image_url and last_frame_image_url != primary_image:
                payload["last_image"] = last_frame_image_url
            submit_url = self._submit_url(has_image=True)
        else:
            # text-to-video: extra refs go into `reference_images` array (max ~8)
            if reference_images:
                refs = [u for u in reference_images if u][:8]
                if refs:
                    payload["reference_images"] = refs
            submit_url = self._submit_url(has_image=False)

        print(f"[WAVESPEED] Submitting: dur={duration_sec}s, ratio={ratio}, res={res}, "
              f"image={'yes' if primary_image else 'no'}")
        print(f"[WAVESPEED] Prompt: {visual_prompt[:80]}...")

        resp = requests.post(submit_url, json=payload, headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except ValueError:
                err = resp.text
            raise ValueError(f"WaveSpeed submit failed: HTTP {resp.status_code} — {err}")

        data = resp.json()
        body = data.get("data") if isinstance(data.get("data"), dict) else data
        task_id = body.get("id") or body.get("task_id")
        if not task_id:
            raise ValueError(f"No task_id in WaveSpeed response: {data}")

        # Prefer the poll URL the API hands back; fall back to the documented path.
        poll_url = (body.get("urls") or {}).get("get") or f"{self.base_url}/predictions/{task_id}/result"
        print(f"[WAVESPEED] Task submitted: {task_id}")

        max_wait = 600
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
                raise ValueError(f"WaveSpeed poll failed: HTTP {poll_resp.status_code} — {err}")

            poll_data = poll_resp.json()
            pb = poll_data.get("data") if isinstance(poll_data.get("data"), dict) else poll_data
            status = (pb.get("status") or "").lower()

            if status in ("completed", "succeeded", "success"):
                outputs = pb.get("outputs") or []
                video_url = None
                if isinstance(outputs, list) and outputs:
                    first = outputs[0]
                    video_url = first if isinstance(first, str) else (
                        first.get("url") if isinstance(first, dict) else None
                    )
                video_url = video_url or pb.get("video_url") or pb.get("url")
                if video_url:
                    print(f"[WAVESPEED] Video ready ({elapsed}s): {video_url[:80]}...")
                    return video_url
                raise ValueError(f"Completed but no video URL: {pb}")

            if status in ("failed", "error", "cancelled"):
                error_msg = pb.get("error") or pb.get("message") or "Unknown error"
                raise ValueError(f"WaveSpeed generation failed: {error_msg}")

            if elapsed % 15 == 0:
                print(f"[WAVESPEED] Poll ({elapsed}s): status={status or 'pending'}")

            if elapsed > 60:
                poll_interval = 10

        raise TimeoutError(f"WaveSpeed generation timed out after {max_wait}s (task_id={task_id})")
