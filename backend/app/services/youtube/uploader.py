"""
YouTube video upload via resumable upload API.
"""
import os
import tempfile
import requests as http_requests
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import is_internal_backend_asset_url, is_safe_outbound_url
from app.models.youtube_channel import YouTubeChannel, YouTubeUpload
from .auth import YouTubeAuth
from .quota_tracker import QuotaTracker


class YouTubeUploader:
    """Handles video uploads to YouTube."""

    UPLOAD_COST_UNITS = 1600  # YouTube API quota cost per upload

    def __init__(self):
        self.auth = YouTubeAuth()
        self.quota_tracker = QuotaTracker()

    def upload_video(
        self,
        db: Session,
        channel_id: int,
        video_path_or_url: str,
        title: str,
        description: str = "",
        tags: list = None,
        privacy_status: str = "private",
        scheduled_publish_at: Optional[datetime] = None,
        project_id: Optional[int] = None,
        story_idea_id: Optional[int] = None,
    ) -> YouTubeUpload:
        """
        Upload a video to YouTube.

        Args:
            channel_id: DB id of the YouTubeChannel
            video_path_or_url: Local path or URL to the video file
            title: Video title
            description: Video description
            tags: List of tags
            privacy_status: private, public, unlisted, or scheduled
            scheduled_publish_at: When to publish (for scheduled)
            project_id: Related project ID
            story_idea_id: Related story idea ID
        """
        # Get channel
        channel = db.query(YouTubeChannel).filter(
            YouTubeChannel.id == channel_id,
            YouTubeChannel.is_active == True,
        ).first()
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or inactive")

        # Check quota
        if not self.quota_tracker.can_upload():
            raise ValueError("YouTube daily quota exceeded. Max ~6 uploads/day (10,000 units)")

        # Create upload record
        upload = YouTubeUpload(
            channel_id=channel.id,
            project_id=project_id,
            story_idea_id=story_idea_id,
            title=title,
            description=description,
            tags_json=str(tags or []),
            status="uploading",
            privacy_status=privacy_status if privacy_status != "scheduled" else "private",
            scheduled_publish_at=scheduled_publish_at,
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)

        video_path = None
        try:
            # Get fresh access token
            access_token = self._get_valid_token(db, channel)

            # Download video if URL
            video_path = self._ensure_local_file(video_path_or_url)

            # Upload to YouTube
            actual_privacy = "private"
            publish_at = None
            if privacy_status == "scheduled" and scheduled_publish_at:
                actual_privacy = "private"
                publish_at = scheduled_publish_at.isoformat() + "Z"
            elif privacy_status in ("public", "unlisted", "private"):
                actual_privacy = privacy_status

            youtube_video_id = self._do_upload(
                access_token=access_token,
                video_path=video_path,
                title=title,
                description=description,
                tags=tags or [],
                privacy_status=actual_privacy,
                publish_at=publish_at,
            )

            # Update record
            upload.youtube_video_id = youtube_video_id
            upload.youtube_url = f"https://youtube.com/watch?v={youtube_video_id}"
            upload.status = "scheduled" if scheduled_publish_at else "published"
            upload.published_at = datetime.utcnow() if not scheduled_publish_at else None

            # Track quota
            self.quota_tracker.record_upload()

            db.commit()
            db.refresh(upload)
            print(f"[YOUTUBE] Upload success: {upload.youtube_url}")
            return upload

        except Exception as e:
            upload.status = "failed"
            upload.error_text = str(e)
            db.commit()
            print(f"[YOUTUBE] Upload failed: {e}")
            raise

        finally:
            # Clean up temp file if we downloaded from URL
            if (
                video_path
                and video_path_or_url.startswith(("http://", "https://"))
                and os.path.exists(video_path)
            ):
                os.unlink(video_path)

    def _get_valid_token(self, db: Session, channel: YouTubeChannel) -> str:
        """Get a valid access token, refreshing if needed."""
        access_token = YouTubeAuth.decrypt_token(channel.access_token)
        refresh_token = YouTubeAuth.decrypt_token(channel.refresh_token)

        # Check if token is expired
        if channel.token_expiry and channel.token_expiry < datetime.utcnow():
            new_token, new_expiry = self.auth.refresh_access_token(refresh_token)
            channel.access_token = YouTubeAuth.encrypt_token(new_token)
            if new_expiry:
                channel.token_expiry = datetime.fromisoformat(new_expiry)
            db.commit()
            access_token = new_token

        return access_token

    def _ensure_local_file(self, path_or_url: str) -> str:
        """Download URL to temp file if needed, return local path."""
        if path_or_url.startswith(("http://", "https://")):
            allow_private = settings.ALLOW_PRIVATE_URL_FETCH or is_internal_backend_asset_url(
                path_or_url, settings.BACKEND_URL
            )
            if not is_safe_outbound_url(path_or_url, allow_private=allow_private):
                raise ValueError("Unsafe video URL")

            resp = http_requests.get(path_or_url, stream=True, timeout=120)
            resp.raise_for_status()
            suffix = ".mp4"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp.close()
            return tmp.name
        return path_or_url

    def _do_upload(
        self,
        access_token: str,
        video_path: str,
        title: str,
        description: str,
        tags: list,
        privacy_status: str,
        publish_at: Optional[str] = None,
    ) -> str:
        """Perform the actual YouTube upload via googleapiclient."""
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)
        youtube = build("youtube", "v3", credentials=creds)

        # Ensure AI disclaimer is present
        ai_disclaimer = "\n\n\u26a0\ufe0f This video was created with AI tools"
        if "This video was created with AI" not in description:
            description = description + ai_disclaimer

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:500],
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        if publish_at:
            body["status"]["publishAt"] = publish_at

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=256 * 1024,  # 256KB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[YOUTUBE] Upload progress: {int(status.progress() * 100)}%")

        video_id = response["id"]
        print(f"[YOUTUBE] Upload complete: video_id={video_id}")
        return video_id


def handle_youtube_upload_job(
    channel_id: int,
    video_path_or_url: str,
    title: str,
    description: str = "",
    tags: list = None,
    privacy_status: str = "private",
    scheduled_publish_at: str = None,
    project_id: int = None,
    story_idea_id: int = None,
):
    """RQ job handler for YouTube uploads."""
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        uploader = YouTubeUploader()
        publish_dt = None
        if scheduled_publish_at:
            publish_dt = datetime.fromisoformat(scheduled_publish_at)

        uploader.upload_video(
            db=db,
            channel_id=channel_id,
            video_path_or_url=video_path_or_url,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            scheduled_publish_at=publish_dt,
            project_id=project_id,
            story_idea_id=story_idea_id,
        )
    finally:
        db.close()
