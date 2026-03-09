"""
Gemini API Veo Provider — direct Google API access for Veo 3.1 video generation.
No intermediaries (Replicate/LaoZhang). Uses Google AI Studio API key.

Async pattern: predictLongRunning → poll operation → download video.

Model matrix (Gemini API):
  veo-3.1-generate-preview       standard
  veo-3.1-fast-generate-preview  fast

Supports: text-to-video, I2V (first frame image), last frame, reference images, negative prompt.
"""

import time
import base64
import requests
from typing import Optional, List
from app.core.config import settings
from .video_provider_base import VideoProvider


class GeminiVeoProvider(VideoProvider):
    """
    Direct Google Gemini API provider for Veo 3.1.
    Submit predictLongRunning → poll → get video URI.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, use_fast: bool = True, use_fl: bool = False, aspect_ratio: str = "9:16"):
        self.api_key = settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")

        self.use_fast = use_fast
        self.use_fl = use_fl
        self.default_aspect = aspect_ratio

        # Pick model: fast or standard
        if use_fast:
            self.model_name = "veo-3.1-fast-generate-preview"
        else:
            self.model_name = "veo-3.1-generate-preview"

        print(f"[GEMINI-VEO] Initialized: model={self.model_name} (fast={use_fast}, fl={use_fl}, aspect={aspect_ratio})")

    def _download_image_as_base64(self, url: str) -> tuple[str, str]:
        """Download image from URL and return (base64_data, mime_type).
        Also handles data: URIs directly."""
        # Handle data: URIs (from convert_local_to_base64)
        if url.startswith("data:"):
            # Format: data:image/png;base64,<b64data>
            header, b64 = url.split(",", 1)
            mime = header.split(":")[1].split(";")[0]
            return b64, mime

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "image/png")
        if "jpeg" in content_type or "jpg" in content_type:
            mime = "image/jpeg"
        elif "webp" in content_type:
            mime = "image/webp"
        else:
            mime = "image/png"

        b64 = base64.b64encode(resp.content).decode("utf-8")

        # Validate size (< 20MB)
        if len(resp.content) > 20 * 1024 * 1024:
            raise ValueError(f"Image too large ({len(resp.content) / 1024 / 1024:.1f}MB). Max 20MB.")

        return b64, mime

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
        Generate video via Gemini API predictLongRunning.

        Returns:
            Video download URI (authenticated with API key).
        """
        # Validate duration
        valid_durations = [4, 6, 8]
        if duration_sec not in valid_durations:
            duration_sec = min(valid_durations, key=lambda x: abs(x - duration_sec))

        # FL mode requires 8s
        if self.use_fl and duration_sec != 8:
            print(f"[GEMINI-VEO] Frame chaining requires 8s, forcing from {duration_sec}")
            duration_sec = 8

        # Build instance
        instance = {"prompt": visual_prompt}

        # I2V: first frame image (bytesBase64Encoded format for predictLongRunning)
        if reference_image_url:
            try:
                b64, mime = self._download_image_as_base64(reference_image_url)
                instance["image"] = {"bytesBase64Encoded": b64, "mimeType": mime}
                print(f"[GEMINI-VEO] I2V mode: first frame image attached ({mime})")
            except Exception as e:
                print(f"[GEMINI-VEO] Warning: failed to attach image: {e}")

        # Build parameters
        parameters = {
            "aspectRatio": aspect_ratio,
            "durationSeconds": duration_sec,
        }

        if negative_prompt:
            parameters["negativePrompt"] = negative_prompt

        if reference_images and len(reference_images) > 0:
            ref_list = []
            for ref_url in reference_images[:3]:
                try:
                    b64, mime = self._download_image_as_base64(ref_url)
                    ref_list.append({"bytesBase64Encoded": b64, "mimeType": mime})
                except Exception as e:
                    print(f"[GEMINI-VEO] Warning: skipping reference image: {e}")
            if ref_list:
                parameters["referenceImages"] = ref_list
                parameters["aspectRatio"] = "16:9"  # R2V requires 16:9
                parameters["durationSeconds"] = 8
                print(f"[GEMINI-VEO] R2V mode: {len(ref_list)} reference images (forcing 16:9, 8s)")

        payload = {
            "instances": [instance],
            "parameters": parameters,
        }

        # Submit
        submit_url = f"{self.BASE_URL}/models/{self.model_name}:predictLongRunning?key={self.api_key}"
        print(f"[GEMINI-VEO] Submitting: model={self.model_name}, prompt={visual_prompt[:60]}...")
        print(f"[GEMINI-VEO] Params: duration={duration_sec}, aspect={aspect_ratio}, i2v={bool(reference_image_url)}")

        resp = requests.post(submit_url, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        operation_name = result.get("name")
        if not operation_name:
            raise ValueError(f"No operation name in response: {result}")

        print(f"[GEMINI-VEO] Operation submitted: {operation_name}")

        # Poll for completion (max 5 minutes)
        poll_url = f"{self.BASE_URL}/{operation_name}?key={self.api_key}"
        max_wait = 300
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = requests.get(poll_url, timeout=15)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()

            done = poll_data.get("done", False)

            if done:
                # Check for error
                error = poll_data.get("error")
                if error:
                    raise ValueError(f"Gemini Veo generation failed: {error.get('message', error)}")

                # Extract video URI
                response = poll_data.get("response", {})
                samples = response.get("generateVideoResponse", {}).get("generatedSamples", [])

                if samples:
                    video_uri = samples[0].get("video", {}).get("uri", "")
                    if video_uri:
                        # Append API key for authenticated download
                        download_url = f"{video_uri}&key={self.api_key}" if "?" in video_uri else f"{video_uri}?key={self.api_key}"
                        print(f"[GEMINI-VEO] Video ready ({elapsed}s): {download_url[:80]}...")
                        return download_url

                raise ValueError(f"Operation done but no video URI: {poll_data}")

            # Log progress
            if elapsed % 20 == 0:
                print(f"[GEMINI-VEO] Polling ({elapsed}s)...")

            # Increase interval after 60s
            if elapsed > 60:
                poll_interval = 10

        raise TimeoutError(f"Gemini Veo generation timed out after {max_wait}s ({operation_name})")
