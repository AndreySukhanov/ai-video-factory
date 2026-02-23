from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from urllib.parse import quote_plus

from app.core.db import get_db
from app.core.config import settings
from app.models.youtube_channel import YouTubeChannel, YouTubeUpload
from app.schemas.youtube import (
    YouTubeChannelRead, AuthUrlResponse, AuthCallbackResponse,
    YouTubeUploadRequest, YouTubeUploadScheduleRequest,
    YouTubeUploadRead, QuotaStatusResponse,
)
from app.services.youtube.auth import YouTubeAuth
from app.services.youtube.uploader import YouTubeUploader
from app.services.youtube.metadata_generator import MetadataGenerator
from app.services.youtube.quota_tracker import QuotaTracker

router = APIRouter()


# --- Auth ---

@router.get("/auth/url", response_model=AuthUrlResponse)
def get_auth_url():
    """Get YouTube OAuth consent URL."""
    try:
        auth = YouTubeAuth()
        url = auth.get_auth_url()
        return AuthUrlResponse(auth_url=url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auth/callback")
def auth_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    """Handle OAuth callback, exchange code for tokens, save channel."""
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    try:
        auth = YouTubeAuth()
        if not auth.validate_state(state):
            raise ValueError("Invalid or expired OAuth state")

        tokens = auth.exchange_code(code)
        new_refresh_token = tokens.get("refresh_token")

        # Get channel info
        channel_info = auth.get_channel_info(tokens["access_token"])

        # Check if channel already exists
        existing = db.query(YouTubeChannel).filter(
            YouTubeChannel.channel_id == channel_info["channel_id"]
        ).first()

        if existing:
            # Update tokens
            existing.access_token = YouTubeAuth.encrypt_token(tokens["access_token"])
            if new_refresh_token:
                existing.refresh_token = YouTubeAuth.encrypt_token(new_refresh_token)
            if tokens.get("token_expiry"):
                existing.token_expiry = datetime.fromisoformat(tokens["token_expiry"])
            existing.is_active = True
            db.commit()
            channel = existing
        else:
            # Create new channel
            if not new_refresh_token:
                raise ValueError("OAuth response did not include refresh token. Please reconnect and grant offline access.")
            channel = YouTubeChannel(
                channel_id=channel_info["channel_id"],
                channel_title=channel_info["channel_title"],
                access_token=YouTubeAuth.encrypt_token(tokens["access_token"]),
                refresh_token=YouTubeAuth.encrypt_token(new_refresh_token),
                token_expiry=datetime.fromisoformat(tokens["token_expiry"]) if tokens.get("token_expiry") else None,
                is_active=True,
            )
            db.add(channel)
            db.commit()
            db.refresh(channel)

        # Redirect to frontend YouTube page
        return RedirectResponse(url=f"{frontend_url}/youtube?auth=success")

    except Exception as e:
        print(f"[YOUTUBE] Auth callback error: {e}")
        encoded_message = quote_plus(str(e))
        return RedirectResponse(url=f"{frontend_url}/youtube?auth=error&message={encoded_message}")


# --- Channels ---

@router.get("/channels", response_model=List[YouTubeChannelRead])
def list_channels(db: Session = Depends(get_db)):
    """List connected YouTube channels."""
    channels = db.query(YouTubeChannel).filter(YouTubeChannel.is_active == True).all()
    return channels


@router.delete("/channels/{channel_id}")
def disconnect_channel(channel_id: int, db: Session = Depends(get_db)):
    """Disconnect a YouTube channel."""
    channel = db.query(YouTubeChannel).filter(YouTubeChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    channel.is_active = False
    db.commit()
    return {"success": True, "message": f"Channel '{channel.channel_title}' disconnected"}


# --- Uploads ---

@router.post("/upload", response_model=YouTubeUploadRead)
def upload_video(request: YouTubeUploadRequest, db: Session = Depends(get_db)):
    """Upload a video to YouTube."""
    # Generate metadata if requested
    title = request.title
    description = request.description
    tags = request.tags

    if request.generate_metadata and request.story_idea_text:
        generator = MetadataGenerator()
        metadata = generator.generate_metadata(request.story_idea_text)
        title = title or metadata["title"]
        description = description or metadata["description"]
        tags = tags or metadata["tags"]

    try:
        uploader = YouTubeUploader()
        upload = uploader.upload_video(
            db=db,
            channel_id=request.channel_id,
            video_path_or_url=request.video_url,
            title=title,
            description=description,
            tags=tags,
            privacy_status=request.privacy_status,
            project_id=request.project_id,
            story_idea_id=request.story_idea_id,
        )
        return upload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/schedule", response_model=YouTubeUploadRead)
def schedule_upload(request: YouTubeUploadScheduleRequest, db: Session = Depends(get_db)):
    """Upload a video with scheduled publication."""
    title = request.title
    description = request.description
    tags = request.tags

    if request.generate_metadata and request.story_idea_text:
        generator = MetadataGenerator()
        metadata = generator.generate_metadata(request.story_idea_text)
        title = title or metadata["title"]
        description = description or metadata["description"]
        tags = tags or metadata["tags"]

    try:
        uploader = YouTubeUploader()
        upload = uploader.upload_video(
            db=db,
            channel_id=request.channel_id,
            video_path_or_url=request.video_url,
            title=title,
            description=description,
            tags=tags,
            privacy_status="scheduled",
            scheduled_publish_at=request.scheduled_publish_at,
            project_id=request.project_id,
            story_idea_id=request.story_idea_id,
        )
        return upload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/uploads", response_model=List[YouTubeUploadRead])
def list_uploads(
    status: str = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List YouTube uploads with optional status filter."""
    query = db.query(YouTubeUpload)
    if status:
        query = query.filter(YouTubeUpload.status == status)
    uploads = query.order_by(YouTubeUpload.created_at.desc()).offset(skip).limit(limit).all()
    return uploads


# --- Quota ---

@router.get("/quota", response_model=QuotaStatusResponse)
def get_quota():
    """Get current YouTube API quota status."""
    tracker = QuotaTracker()
    return tracker.get_status()
