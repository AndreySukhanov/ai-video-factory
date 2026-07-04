from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import httpx

from app.core.security import is_safe_outbound_url

router = APIRouter()

# CDN domain suffixes from which image proxying is allowed.
# Matching is done by hostname (exact match or subdomain), not by URL substring.
ALLOWED_HOST_SUFFIXES = [
    "cdninstagram.com",
    "instagram.com",
    "fbcdn.net",  # scontent-*.fbcdn.net (Instagram CDN)
    "tiktokcdn.com",
    "tiktok.com",
    "ytimg.com",
    "ggpht.com",
    "googleusercontent.com",
]

MAX_REDIRECTS = 3


def _is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    if not any(
        hostname == suffix or hostname.endswith("." + suffix)
        for suffix in ALLOWED_HOST_SUFFIXES
    ):
        return False
    return is_safe_outbound_url(url)


@router.get("/image")
async def proxy_image(url: str = Query(...)):
    """Proxy external images to avoid CORS/CORP restrictions."""
    if not _is_allowed_url(url):
        raise HTTPException(status_code=403, detail="Host not allowed")

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TrendBot/1.0)",
        "Referer": "https://www.instagram.com/",
    }
    try:
        # Follow redirects manually, validating the host on every hop,
        # so a CDN cannot redirect the request to an arbitrary address.
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            current_url = url
            for _ in range(MAX_REDIRECTS + 1):
                resp = await client.get(current_url, headers=headers)
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        raise HTTPException(status_code=502, detail="Redirect without location")
                    current_url = urljoin(current_url, location)
                    if not _is_allowed_url(current_url):
                        raise HTTPException(status_code=403, detail="Redirect host not allowed")
                    continue
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "image/jpeg")
                return StreamingResponse(
                    iter([resp.content]),
                    media_type=content_type,
                    headers={"Cache-Control": "public, max-age=3600"},
                )
            raise HTTPException(status_code=502, detail="Too many redirects")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {e}")
