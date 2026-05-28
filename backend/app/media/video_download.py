"""Download remote videos into the local static dir for persistence.

External provider URLs (replicate.delivery, Veo, WaveSpeed cachecloud) expire
within hours/days. Persisting to /static/generated keeps review/publish working.
"""

import os
import uuid
import requests

# /app/static  (this file lives at /app/app/media/video_download.py)
STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "static",
)


def is_local_url(url: str) -> bool:
    """True if the URL already points at our own /static or /uploads."""
    return ("/static/" in url) or ("/uploads/" in url) or url.startswith("/")


def download_video_locally(video_url: str, timeout: int = 120) -> str:
    """Download a remote video into /static/generated and return its local URL.

    Raises on network/HTTP failure — callers decide whether to fall back to the
    original URL.
    """
    video_filename = f"gen_{uuid.uuid4().hex[:12]}.mp4"
    generated_dir = os.path.join(STATIC_DIR, "generated")
    os.makedirs(generated_dir, exist_ok=True)
    local_path = os.path.join(generated_dir, video_filename)

    resp = requests.get(video_url, timeout=timeout)
    resp.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(resp.content)

    base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    local_url = f"{base_url}/static/generated/{video_filename}"
    print(f"[VIDEO-DOWNLOAD] Saved {len(resp.content)} bytes -> {local_url}")
    return local_url
