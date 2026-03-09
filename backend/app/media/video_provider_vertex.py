"""
Vertex AI Veo Provider — direct Google Cloud access for Veo 3.1 video generation.
Unlike Gemini API, Vertex AI supports generateAudio=false for cheaper no-audio generation.

Pricing (per second, 720p):
  Fast + audio:    $0.15/s  ($1.20 per 8s video)
  Fast + no audio: $0.10/s  ($0.80 per 8s video)  ← 33% cheaper
  Std + audio:     $0.40/s  ($3.20 per 8s video)
  Std + no audio:  $0.20/s  ($1.60 per 8s video)  ← 50% cheaper

Auth: Service Account JSON key → OAuth2 Bearer token.
Async: predictLongRunning → poll operation → download video.
"""

import os
import time
import base64
import requests
from typing import Optional, List
from google.oauth2 import service_account
from google.auth.transport.requests import Request as AuthRequest
from app.core.config import settings
from .video_provider_base import VideoProvider


# Vertex AI scopes
VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class VertexVeoProvider(VideoProvider):
    """
    Google Vertex AI provider for Veo 3.1.
    Supports generateAudio toggle for cost savings.
    """

    def __init__(
        self,
        use_fast: bool = True,
        use_fl: bool = False,
        aspect_ratio: str = "9:16",
        generate_audio: bool = True,
    ):
        self.project_id = settings.VERTEX_PROJECT_ID
        self.region = settings.VERTEX_REGION
        self.sa_key_path = settings.VERTEX_SA_KEY_PATH
        self.generate_audio = generate_audio
        self.use_fl = use_fl

        if not self.project_id or not self.sa_key_path:
            raise ValueError("VERTEX_PROJECT_ID and VERTEX_SA_KEY_PATH must be set")

        if not os.path.exists(self.sa_key_path):
            raise ValueError(f"Service account key not found: {self.sa_key_path}")

        # Pick model
        if use_fast:
            self.model_name = "veo-3.1-fast-generate-preview"
        else:
            self.model_name = "veo-3.1-generate-preview"

        # Base URL
        self.base_url = f"https://{self.region}-aiplatform.googleapis.com/v1"
        self.model_url = (
            f"{self.base_url}/projects/{self.project_id}/locations/{self.region}"
            f"/publishers/google/models/{self.model_name}"
        )

        # Load credentials
        self._credentials = service_account.Credentials.from_service_account_file(
            self.sa_key_path, scopes=VERTEX_SCOPES
        )

        price_tag = "no-audio" if not generate_audio else "audio"
        print(
            f"[VERTEX] Initialized: model={self.model_name}, "
            f"project={self.project_id}, region={self.region}, "
            f"audio={generate_audio} ({price_tag}), fl={use_fl}"
        )

    def _get_token(self) -> str:
        """Get fresh OAuth2 access token from service account."""
        if not self._credentials.valid:
            self._credentials.refresh(AuthRequest())
        return self._credentials.token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def _download_image_as_base64(self, url: str) -> tuple[str, str]:
        """Download image and return (base64_data, mime_type)."""
        if url.startswith("data:"):
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

        if len(resp.content) > 20 * 1024 * 1024:
            raise ValueError(f"Image too large ({len(resp.content) / 1024 / 1024:.1f}MB). Max 20MB.")

        b64 = base64.b64encode(resp.content).decode("utf-8")
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
        Generate video via Vertex AI predictLongRunning.
        Returns video download URI.
        """
        valid_durations = [4, 6, 8]
        if duration_sec not in valid_durations:
            duration_sec = min(valid_durations, key=lambda x: abs(x - duration_sec))

        if self.use_fl and duration_sec != 8:
            print(f"[VERTEX] Frame chaining requires 8s, forcing from {duration_sec}")
            duration_sec = 8

        # Build instance
        instance = {"prompt": visual_prompt}

        # I2V: first frame image
        if reference_image_url:
            try:
                b64, mime = self._download_image_as_base64(reference_image_url)
                instance["image"] = {"bytesBase64Encoded": b64, "mimeType": mime}
                print(f"[VERTEX] I2V mode: first frame image attached ({mime})")
            except Exception as e:
                print(f"[VERTEX] Warning: failed to attach image: {e}")

        # Last frame image for transition videos (-fl models)
        if last_frame_image_url:
            try:
                b64, mime = self._download_image_as_base64(last_frame_image_url)
                instance["lastFrame"] = {"bytesBase64Encoded": b64, "mimeType": mime}
                duration_sec = 8  # transitions require 8s
                print(f"[VERTEX] Transition mode: last frame attached ({mime}), forcing 8s")
            except Exception as e:
                print(f"[VERTEX] Warning: failed to attach last frame: {e}")

        # Build parameters
        parameters = {
            "aspectRatio": aspect_ratio,
            "durationSeconds": duration_sec,
            "generateAudio": self.generate_audio,
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
                    print(f"[VERTEX] Warning: skipping reference image: {e}")
            if ref_list:
                parameters["referenceImages"] = ref_list
                parameters["aspectRatio"] = "16:9"
                parameters["durationSeconds"] = 8
                print(f"[VERTEX] R2V mode: {len(ref_list)} reference images (forcing 16:9, 8s)")

        payload = {
            "instances": [instance],
            "parameters": parameters,
        }

        # Submit
        submit_url = f"{self.model_url}:predictLongRunning"
        audio_str = "audio" if self.generate_audio else "NO-AUDIO"
        print(f"[VERTEX] Submitting: model={self.model_name}, {audio_str}, prompt={visual_prompt[:60]}...")
        print(f"[VERTEX] Params: duration={duration_sec}, aspect={aspect_ratio}")

        resp = requests.post(submit_url, json=payload, headers=self._headers(), timeout=60)
        resp.raise_for_status()
        result = resp.json()

        operation_name = result.get("name")
        if not operation_name:
            raise ValueError(f"No operation name in response: {result}")

        print(f"[VERTEX] Operation submitted: {operation_name}")

        # Poll for completion (max 5 minutes)
        poll_url = f"{self.base_url}/{operation_name}"
        max_wait = 300
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            poll_resp = requests.get(poll_url, headers=self._headers(), timeout=15)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()

            done = poll_data.get("done", False)

            if done:
                error = poll_data.get("error")
                if error:
                    raise ValueError(f"Vertex Veo generation failed: {error.get('message', error)}")

                response = poll_data.get("response", {})
                samples = response.get("generateVideoResponse", {}).get("generatedSamples", [])

                if samples:
                    video_uri = samples[0].get("video", {}).get("uri", "")
                    if video_uri:
                        print(f"[VERTEX] Video ready ({elapsed}s): {video_uri[:80]}...")
                        return video_uri

                raise ValueError(f"Operation done but no video URI: {poll_data}")

            if elapsed % 20 == 0:
                print(f"[VERTEX] Polling ({elapsed}s)...")

            if elapsed > 60:
                poll_interval = 10

        raise TimeoutError(f"Vertex Veo generation timed out after {max_wait}s ({operation_name})")
