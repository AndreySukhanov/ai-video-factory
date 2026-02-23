"""
YouTube Analytics API integration for fetching video performance metrics.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from app.models.analytics import VideoAnalytics
from app.models.youtube_channel import YouTubeChannel, YouTubeUpload
from .auth import YouTubeAuth


class YouTubeAnalyticsService:
    """Fetch video analytics from YouTube Analytics API."""

    def __init__(self):
        self.auth = YouTubeAuth()

    def fetch_video_analytics(
        self,
        db: Session,
        channel_id: int,
        youtube_video_id: str,
        upload_id: int = None,
    ) -> Optional[VideoAnalytics]:
        """Fetch analytics for a specific video."""
        channel = db.query(YouTubeChannel).filter(
            YouTubeChannel.id == channel_id,
            YouTubeChannel.is_active == True,
        ).first()

        if not channel:
            print(f"[ANALYTICS] Channel {channel_id} not found")
            return None

        try:
            access_token = self._get_valid_token(db, channel)

            # Get basic video statistics via Data API
            stats = self._fetch_video_stats(access_token, youtube_video_id)

            # Get analytics data via Analytics API
            analytics_data = self._fetch_analytics_data(access_token, youtube_video_id)

            # Merge and save
            record = VideoAnalytics(
                youtube_upload_id=upload_id,
                youtube_video_id=youtube_video_id,
                views=stats.get("viewCount", 0),
                likes=stats.get("likeCount", 0),
                comments=stats.get("commentCount", 0),
                shares=analytics_data.get("shares", 0),
                watch_time_minutes=analytics_data.get("estimatedMinutesWatched", 0.0),
                average_view_duration_seconds=analytics_data.get("averageViewDuration", 0.0),
                click_through_rate=analytics_data.get("cardClickRate", 0.0),
                impression_count=analytics_data.get("impressions", 0),
                subscriber_gain=analytics_data.get("subscribersGained", 0),
            )
            db.add(record)
            db.commit()
            db.refresh(record)

            print(f"[ANALYTICS] Fetched analytics for {youtube_video_id}: {stats.get('viewCount', 0)} views")
            return record

        except Exception as e:
            print(f"[ANALYTICS] Error fetching analytics: {e}")
            return None

    def fetch_all_uploads_analytics(self, db: Session, channel_id: int) -> List[VideoAnalytics]:
        """Fetch analytics for all uploads of a channel."""
        uploads = db.query(YouTubeUpload).filter(
            YouTubeUpload.channel_id == channel_id,
            YouTubeUpload.youtube_video_id != None,
            YouTubeUpload.status.in_(["published", "scheduled"]),
        ).all()

        results = []
        for upload in uploads:
            analytics = self.fetch_video_analytics(
                db, channel_id, upload.youtube_video_id, upload.id
            )
            if analytics:
                results.append(analytics)

        return results

    def _get_valid_token(self, db: Session, channel: YouTubeChannel) -> str:
        """Get valid access token, refresh if needed."""
        access_token = YouTubeAuth.decrypt_token(channel.access_token)
        refresh_token = YouTubeAuth.decrypt_token(channel.refresh_token)

        if channel.token_expiry and channel.token_expiry < datetime.utcnow():
            new_token, new_expiry = self.auth.refresh_access_token(refresh_token)
            channel.access_token = YouTubeAuth.encrypt_token(new_token)
            if new_expiry:
                channel.token_expiry = datetime.fromisoformat(new_expiry)
            db.commit()
            access_token = new_token

        return access_token

    def _fetch_video_stats(self, access_token: str, video_id: str) -> Dict:
        """Fetch video statistics via YouTube Data API v3."""
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)
        youtube = build("youtube", "v3", credentials=creds)

        response = youtube.videos().list(
            part="statistics",
            id=video_id,
        ).execute()

        items = response.get("items", [])
        if not items:
            return {}

        stats = items[0].get("statistics", {})
        return {
            "viewCount": int(stats.get("viewCount", 0)),
            "likeCount": int(stats.get("likeCount", 0)),
            "commentCount": int(stats.get("commentCount", 0)),
        }

    def _fetch_analytics_data(self, access_token: str, video_id: str) -> Dict:
        """Fetch detailed analytics via YouTube Analytics API."""
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials

            creds = Credentials(token=access_token)
            youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

            end_date = datetime.utcnow().strftime("%Y-%m-%d")
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

            response = youtube_analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="estimatedMinutesWatched,averageViewDuration,shares,subscribersGained",
                filters=f"video=={video_id}",
            ).execute()

            rows = response.get("rows", [])
            if not rows:
                return {}

            row = rows[0]
            headers = [h["name"] for h in response.get("columnHeaders", [])]
            return dict(zip(headers, row))

        except Exception as e:
            print(f"[ANALYTICS] Analytics API error (may not be enabled): {e}")
            return {}
