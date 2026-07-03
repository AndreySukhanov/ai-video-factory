"""
Локальные медиа-утилиты, общие для эндпоинтов и сервисов генерации:
резолв локальных /uploads//static путей, загрузка на catbox, кроп под
aspect ratio, конвертация в base64 data URI, скачивание видео в /static.

Вынесено из app/api/v1/episodes.py (распил god-router'а).
"""
import asyncio
import base64
import io
import os
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from PIL import Image

from app.core.config import settings
from app.core.security import (
    extract_local_upload_filename,
    is_internal_backend_asset_url,
    is_safe_outbound_url,
    resolve_upload_file_path,
)

# Catbox upload URL for external access
CATBOX_API_URL = "https://catbox.moe/user/api.php"

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UPLOADS_DIR = os.path.join(_BACKEND_ROOT, "uploads")
STATIC_DIR = os.path.join(_BACKEND_ROOT, "static")


def allow_private_fetch(url: str) -> bool:
    return settings.ALLOW_PRIVATE_URL_FETCH or is_internal_backend_asset_url(url, settings.BACKEND_URL)


async def upload_to_catbox_from_url(image_url: str) -> Optional[str]:
    """
    Download image from URL and upload to catbox.moe for external access.
    This is needed because Replicate cannot access localhost URLs.
    """
    try:
        if not is_safe_outbound_url(image_url, allow_private=allow_private_fetch(image_url)):
            print(f"[CATBOX] Blocked unsafe URL: {image_url}")
            return None

        def _upload_sync() -> Optional[str]:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            content = response.content

            filename = image_url.split("/")[-1] if "/" in image_url else "character.png"
            if not filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
                filename = "character.png"

            files = {"fileToUpload": (filename, content)}
            data = {"reqtype": "fileupload"}
            upload_response = requests.post(CATBOX_API_URL, files=files, data=data, timeout=60)

            if upload_response.status_code == 200 and upload_response.text.startswith("https://"):
                catbox_url = upload_response.text.strip()
                print(f"[CATBOX] Uploaded to: {catbox_url}")
                return catbox_url

            print(f"[CATBOX] Upload failed: {upload_response.text}")
            return None

        return await asyncio.to_thread(_upload_sync)

    except Exception as e:
        print(f"[CATBOX] Error uploading from URL: {e}")
        return None


def resolve_local_file_path(url: str) -> Optional[str]:
    """Resolve a localhost URL to a local file path. Supports /uploads/ and /static/."""
    parsed = urlparse(url)
    path = parsed.path if parsed.scheme else url

    # /uploads/xxx.jpg
    if path.startswith("/uploads/"):
        file_name = extract_local_upload_filename(url)
        if file_name:
            try:
                return str(resolve_upload_file_path(UPLOADS_DIR, file_name))
            except ValueError:
                return None

    # /static/storyboard/xxx.png, /static/generated/xxx.mp4
    if path.startswith("/static/"):
        rel = path.lstrip("/")
        if ".." in rel or "\\" in rel:
            return None
        full_path = os.path.join(STATIC_DIR, rel.replace("static/", "", 1))
        if os.path.isfile(full_path):
            return full_path

    return None


async def upload_local_to_catbox(url: str) -> Optional[str]:
    """If URL points to a local file, upload it to catbox and return public URL."""
    local_path = resolve_local_file_path(url)
    if not local_path:
        return None

    def _upload_sync() -> Optional[str]:
        with open(local_path, "rb") as f:
            content = f.read()
        filename = os.path.basename(local_path)
        files = {"fileToUpload": (filename, content)}
        data = {"reqtype": "fileupload"}
        resp = requests.post(CATBOX_API_URL, files=files, data=data, timeout=60)
        if resp.status_code == 200 and resp.text.startswith("https://"):
            catbox_url = resp.text.strip()
            print(f"[CATBOX] Local file uploaded: {local_path} → {catbox_url}")
            return catbox_url
        print(f"[CATBOX] Upload failed for {local_path}: {resp.text[:100]}")
        return None

    try:
        return await asyncio.to_thread(_upload_sync)
    except Exception as e:
        print(f"[CATBOX] Error uploading local file: {e}")
        return None


def crop_image_to_aspect_ratio(image_data: bytes, target_aspect_ratio: str) -> bytes:
    """
    Crop image to target aspect ratio using center crop.
    This preserves the main subject which is typically centered.
    """
    if target_aspect_ratio == "9:16":
        target_ratio = 9 / 16  # 0.5625 - vertical
    elif target_aspect_ratio == "16:9":
        target_ratio = 16 / 9  # 1.777 - horizontal
    elif target_aspect_ratio == "1:1":
        target_ratio = 1.0
    else:
        # Unknown, return original
        return image_data

    img = Image.open(io.BytesIO(image_data))
    width, height = img.size

    # Downscale large images so base64 data URIs stay small (some providers reject big payloads)
    MAX_DIM = 1280
    if max(width, height) > MAX_DIM:
        scale = MAX_DIM / max(width, height)
        img = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
        width, height = img.size

    current_ratio = width / height
    needs_crop = abs(current_ratio - target_ratio) / target_ratio >= 0.05
    if needs_crop:
        if current_ratio > target_ratio:
            # Image is too wide - crop horizontally (center crop)
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            img = img.crop((left, 0, left + new_width, height))
        else:
            # Image is too tall - crop vertically (center crop)
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            img = img.crop((0, top, width, top + new_height))

    # Save to bytes (always re-encode so downscale/crop take effect)
    output = io.BytesIO()
    img_format = "PNG" if img.mode == "RGBA" else "JPEG"
    img.save(output, format=img_format, quality=90)
    return output.getvalue()


def convert_local_to_base64(url: Optional[str], aspect_ratio: str = "9:16", crop_aspect: bool = True) -> Optional[str]:
    """Convert local uploads/static asset URL to a base64 data URI.

    Non-local URLs are returned as-is; missing/unsafe paths return None.
    """
    if not url:
        return None

    # Try /uploads/ path first
    file_name = extract_local_upload_filename(url)
    if file_name:
        try:
            file_path = resolve_upload_file_path(UPLOADS_DIR, file_name)
        except ValueError:
            print(f"[DEBUG] Rejected unsafe upload path: {file_name}")
            return None
    else:
        # Try /static/ paths (storyboard frames, extracted frames)
        parsed = urlparse(url)
        path = parsed.path if parsed.scheme else url
        if path.startswith("/static/"):
            rel = path.lstrip("/")
            # Validate: only allow known subdirs, no ..
            if ".." in rel or "\\" in rel:
                print(f"[DEBUG] Rejected unsafe static path: {rel}")
                return None
            file_path = Path(STATIC_DIR) / rel.replace("static/", "", 1)
        else:
            return url  # Return as-is if not local

    if not os.path.exists(file_path):
        print(f"[DEBUG] File not found: {file_path}")
        return None

    with open(file_path, "rb") as f:
        image_data = f.read()

    # Crop image to match target aspect ratio (center crop) if requested
    if crop_aspect:
        original_size = len(image_data)
        image_data = crop_image_to_aspect_ratio(image_data, aspect_ratio)
        print(f"[DEBUG] Cropped image from {original_size} to {len(image_data)} bytes for aspect_ratio={aspect_ratio}")

    suffix = Path(file_path).suffix.lower()
    if suffix == ".png":
        mime_type = "image/png"
    elif suffix in {".jpg", ".jpeg"}:
        mime_type = "image/jpeg"
    else:
        mime_type = "image/png"

    b64_data = base64.b64encode(image_data).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{b64_data}"
    print(f"[DEBUG] Converted to base64, length: {len(data_uri)}")
    return data_uri


def download_video_locally(video_url: str) -> str:
    """Download video from remote URL to local static dir (Veo retention = 2 days)."""
    video_filename = f"gen_{uuid.uuid4().hex[:12]}.mp4"
    generated_dir = os.path.join(STATIC_DIR, "generated")
    os.makedirs(generated_dir, exist_ok=True)
    local_path = os.path.join(generated_dir, video_filename)

    resp = requests.get(video_url, timeout=120)
    resp.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(resp.content)

    base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    local_url = f"{base_url}/static/generated/{video_filename}"
    print(f"[AUTO-DOWNLOAD] Saved {len(resp.content)} bytes to {local_url}")
    return local_url
