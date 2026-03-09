"""
LaoZhang Veo Provider - alternative Veo API proxy via LaoZhang.
Benefits: no charge on generation failure, batch support, 24h video lifetime.
Async: submit task, poll for result.

Full model matrix (LaoZhang supports ALL combos including landscape-fast):
  9:16 fast          -> veo-3.1-fast
  9:16 standard      -> veo-3.1
  9:16 fast fl       -> veo-3.1-fast-fl
  9:16 standard fl   -> veo-3.1-fl
  16:9 fast          -> veo-3.1-landscape-fast       (LaoZhang exclusive!)
  16:9 standard      -> veo-3.1-landscape
  16:9 fast fl       -> veo-3.1-landscape-fast-fl    (LaoZhang exclusive!)
  16:9 standard fl   -> veo-3.1-landscape-fl
"""

import time
import requests
from typing import Optional, List
from app.core.config import settings
from .video_provider_base import VideoProvider


class LaoZhangVeoProvider(VideoProvider):
    """
    LaoZhang proxy for Google Veo 3.1.
    Submit → poll → download pattern (async generation).
    Supports full model matrix including landscape-fast (not available on Replicate).
    Auto-retries on transient errors (internal server errors, overload, etc.).
    """

    # Transient error keywords — safe to retry (new task submission)
    TRANSIENT_KEYWORDS = ("内部异常", "internal", "server error", "overloaded", "capacity", "try again", "service unavailable")
    # Non-retryable error keywords — moderation / auth / invalid input
    NON_RETRYABLE_KEYWORDS = ("unsafe", "moderation", "invalid", "forbidden", "unauthorized", "blocked")

    MAX_RETRIES = 2       # total attempts = 1 original + 2 retries
    RETRY_DELAY = 10      # seconds between retry attempts

    def __init__(self, use_fast: bool = True, use_fl: bool = False, aspect_ratio: str = "9:16"):
        self.api_key = settings.LAOZHANG_API_KEY
        self.base_url = settings.LAOZHANG_BASE_URL.rstrip("/")
        self.use_fast = use_fast
        self.use_fl = use_fl
        self.default_aspect = aspect_ratio

        if not self.api_key:
            raise ValueError("LAOZHANG_API_KEY not set")

        # Build model name — LaoZhang supports full matrix including landscape-fast
        base = "veo-3.1"
        parts = [base]

        if aspect_ratio == "16:9":
            parts.append("landscape")

        if use_fast:
            parts.append("fast")

        if use_fl:
            parts.append("fl")

        self.model_name = "-".join(parts)

        print(f"[LAOZHANG] Initialized: model={self.model_name} (fast={use_fast}, fl={use_fl}, aspect={aspect_ratio})")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _is_transient(self, error_msg: str) -> bool:
        """Check if error is transient (safe to retry with a new task)."""
        msg_lower = error_msg.lower()
        # Explicit non-retryable errors — moderation, auth, invalid input
        if any(kw in msg_lower for kw in self.NON_RETRYABLE_KEYWORDS):
            return False
        # Known transient patterns
        if any(kw in msg_lower for kw in self.TRANSIENT_KEYWORDS):
            return True
        # Chinese error messages (server internal exception)
        if "内部" in error_msg or "重新" in error_msg or "重试" in error_msg:
            return True
        return False

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
        Submit generation task to LaoZhang, poll until complete.
        Auto-retries on transient errors by submitting a NEW task.

        Returns:
            URL of the generated video (valid for 24h)
        """
        valid_durations = [4, 6, 8]
        if duration_sec not in valid_durations:
            duration_sec = min(valid_durations, key=lambda x: abs(x - duration_sec))

        # Frame chaining (fl models) requires 8s duration
        if self.use_fl and duration_sec != 8:
            print(f"[LAOZHANG] Frame chaining requires 8s, forcing duration from {duration_sec} to 8")
            duration_sec = 8

        # Submit task (LaoZhang expects duration as string)
        payload = {
            "model": self.model_name,
            "prompt": visual_prompt,
            "duration": str(duration_sec),
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "generate_audio": generate_audio,
        }

        if reference_image_url:
            payload["image"] = reference_image_url
        if last_frame_image_url:
            payload["last_frame"] = last_frame_image_url
            payload["duration"] = "8"  # transitions require 8s
            print(f"[LAOZHANG] Transition mode: last frame attached, forcing 8s")
        if reference_images:
            payload["reference_images"] = reference_images[:3]
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        last_error: Optional[str] = None

        for attempt in range(1, self.MAX_RETRIES + 2):  # 1..MAX_RETRIES+1 (3 attempts total)
            if attempt > 1:
                print(f"[LAOZHANG] Retry {attempt-1}/{self.MAX_RETRIES}: waiting {self.RETRY_DELAY}s before new task...")
                time.sleep(self.RETRY_DELAY)

            try:
                video_url = self._submit_and_poll(payload, visual_prompt, attempt)
                if attempt > 1:
                    print(f"[LAOZHANG] Retry successful on attempt {attempt}")
                return video_url
            except (ValueError, TimeoutError) as e:
                last_error = str(e)
                if not self._is_transient(last_error) or attempt > self.MAX_RETRIES:
                    raise
                print(f"[LAOZHANG] Transient error: {last_error}")

        # Should not reach here, but just in case
        raise ValueError(f"LaoZhang generation failed after {self.MAX_RETRIES + 1} attempts: {last_error}")

    def _submit_and_poll(self, payload: dict, visual_prompt: str, attempt: int) -> str:
        """Submit a single task and poll until completion. Raises on failure."""
        print(f"[LAOZHANG] Submitting task (attempt {attempt}): model={self.model_name}, prompt={visual_prompt[:60]}...")

        # Submit
        submit_url = f"{self.base_url}/video/generations"
        resp = requests.post(submit_url, json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        result = resp.json()

        task_id = result.get("id") or result.get("task_id")
        if not task_id:
            # Some APIs return the video URL directly
            video_url = result.get("video_url") or result.get("url")
            if video_url:
                return video_url
            raise ValueError(f"No task_id in LaoZhang response: {result}")

        print(f"[LAOZHANG] Task submitted: {task_id}")

        # Poll for completion (max 5 minutes)
        poll_url = f"{self.base_url}/video/generations/{task_id}"
        max_wait = 300
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = requests.get(poll_url, headers=self._headers(), timeout=15)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()

            status = poll_data.get("status", "").lower()
            print(f"[LAOZHANG] Poll ({elapsed}s): status={status}")

            if status in ("completed", "succeeded", "success"):
                video_url = (
                    poll_data.get("video_url")
                    or poll_data.get("output", {}).get("video_url")
                    or poll_data.get("result", {}).get("url")
                )
                if video_url:
                    print(f"[LAOZHANG] Video ready: {video_url[:80]}...")
                    return video_url
                raise ValueError(f"Completed but no video URL: {poll_data}")

            if status in ("failed", "error", "cancelled"):
                error_msg = poll_data.get("error") or poll_data.get("message") or "Unknown error"
                raise ValueError(f"LaoZhang generation failed: {error_msg}")

            # Increase interval after 60s
            if elapsed > 60:
                poll_interval = 10

        raise TimeoutError(f"LaoZhang generation timed out after {max_wait}s (task_id={task_id})")
