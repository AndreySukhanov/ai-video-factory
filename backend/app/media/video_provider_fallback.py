"""
Fallback Video Provider — chains primary → fal.ai on 503/Service Unavailable.

Usage:
    provider = FallbackVideoProvider(
        primary=SeedanceProvider(),
        fallback=FalKlingProvider(),
        label="seedance",
    )
    url = provider.generate_clip(...)  # auto-retries on 503

This is transparent to the caller: same generate_clip() signature.
"""

from typing import Optional, List
from .video_provider_base import VideoProvider

# Keywords that indicate a temporary backend outage → safe to retry via fallback
_FALLBACK_TRIGGERS = ("503", "service unavailable", "bad gateway", "502", "upstream")


def _is_fallback_error(error: Exception) -> bool:
    msg = str(error).lower()
    return any(kw in msg for kw in _FALLBACK_TRIGGERS)


class FallbackVideoProvider(VideoProvider):
    """
    Wraps two providers: primary and fallback.
    On any 503/gateway error from primary, transparently switches to fallback.
    """

    def __init__(self, primary: VideoProvider, fallback: VideoProvider, label: str = "primary"):
        self.primary = primary
        self.fallback = fallback
        self.label = label

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
        kwargs_full = dict(
            aspect_ratio=aspect_ratio,
            reference_image_url=reference_image_url,
            last_frame_image_url=last_frame_image_url,
            reference_images=reference_images,
            resolution=resolution,
            generate_audio=generate_audio,
            negative_prompt=negative_prompt,
        )

        try:
            return self.primary.generate_clip(visual_prompt, duration_sec, **kwargs_full)
        except Exception as e:
            if _is_fallback_error(e):
                print(f"[FALLBACK] {self.label} failed with 503/gateway error: {e}")
                print(f"[FALLBACK] Switching to fal.ai Kling 2.1...")
                return self.fallback.generate_clip(visual_prompt, duration_sec, **kwargs_full)
            raise
