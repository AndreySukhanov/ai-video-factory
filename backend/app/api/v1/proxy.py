from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import httpx

router = APIRouter()

ALLOWED_HOSTS = [
    "scontent",
    "cdninstagram.com",
    "instagram.com",
    "tiktokcdn.com",
    "tiktok.com",
    "ytimg.com",
    "ggpht.com",
    "googleusercontent.com",
]


@router.get("/image")
async def proxy_image(url: str = Query(...)):
    """Proxy external images to avoid CORS/CORP restrictions."""
    if not any(host in url for host in ALLOWED_HOSTS):
        raise HTTPException(status_code=403, detail="Host not allowed")

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; TrendBot/1.0)",
                "Referer": "https://www.instagram.com/",
            })
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            return StreamingResponse(
                iter([resp.content]),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=3600"},
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {e}")
