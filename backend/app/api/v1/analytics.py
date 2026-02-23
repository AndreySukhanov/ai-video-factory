from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.db import get_db
from app.models.analytics import VideoAnalytics
from app.models.youtube_channel import YouTubeUpload
from app.services.youtube.analytics import YouTubeAnalyticsService
from app.services.monitoring import HealthChecker, AlertService, run_health_check_and_alert

router = APIRouter()


# --- Schemas ---
class VideoAnalyticsRead(BaseModel):
    id: int
    youtube_upload_id: Optional[int] = None
    youtube_video_id: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    watch_time_minutes: float = 0.0
    average_view_duration_seconds: float = 0.0
    click_through_rate: float = 0.0
    impression_count: int = 0
    subscriber_gain: int = 0
    fetched_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AnalyticsSummary(BaseModel):
    total_videos: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_watch_time_minutes: float = 0.0
    avg_views_per_video: float = 0.0
    avg_ctr: float = 0.0
    total_subscriber_gain: int = 0


class HealthCheckResponse(BaseModel):
    overall: bool
    redis: dict
    worker: dict
    api_keys: dict
    youtube_quota: dict
    timestamp: str


class AlertRequest(BaseModel):
    title: str
    message: str
    level: str = "info"


# --- Endpoints ---

@router.get("/videos", response_model=List[VideoAnalyticsRead])
def list_video_analytics(
    youtube_video_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List video analytics records."""
    query = db.query(VideoAnalytics)
    if youtube_video_id:
        query = query.filter(VideoAnalytics.youtube_video_id == youtube_video_id)
    records = query.order_by(VideoAnalytics.fetched_at.desc()).offset(skip).limit(limit).all()
    return records


@router.post("/videos/fetch")
def fetch_video_analytics(
    channel_id: int = Query(...),
    youtube_video_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Fetch fresh analytics for a specific video."""
    # Find upload record
    upload = db.query(YouTubeUpload).filter(
        YouTubeUpload.youtube_video_id == youtube_video_id
    ).first()
    upload_id = upload.id if upload else None

    service = YouTubeAnalyticsService()
    analytics = service.fetch_video_analytics(
        db, channel_id, youtube_video_id, upload_id
    )

    if analytics:
        return VideoAnalyticsRead.model_validate(analytics)
    raise HTTPException(status_code=500, detail="Failed to fetch analytics")


@router.post("/videos/fetch-all")
def fetch_all_analytics(channel_id: int = Query(...), db: Session = Depends(get_db)):
    """Fetch analytics for all uploads of a channel."""
    service = YouTubeAnalyticsService()
    results = service.fetch_all_uploads_analytics(db, channel_id)
    return {"success": True, "count": len(results)}


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(db: Session = Depends(get_db)):
    """Get aggregate analytics summary across all videos."""
    from sqlalchemy import func

    # Get latest analytics per video (deduplicated)
    subquery = db.query(
        VideoAnalytics.youtube_video_id,
        func.max(VideoAnalytics.fetched_at).label("latest"),
    ).group_by(VideoAnalytics.youtube_video_id).subquery()

    records = db.query(VideoAnalytics).join(
        subquery,
        (VideoAnalytics.youtube_video_id == subquery.c.youtube_video_id) &
        (VideoAnalytics.fetched_at == subquery.c.latest),
    ).all()

    if not records:
        return AnalyticsSummary()

    total_views = sum(r.views for r in records)
    total_likes = sum(r.likes for r in records)
    total_comments = sum(r.comments for r in records)
    total_watch = sum(r.watch_time_minutes for r in records)
    total_subs = sum(r.subscriber_gain for r in records)
    ctr_values = [r.click_through_rate for r in records if r.click_through_rate > 0]

    return AnalyticsSummary(
        total_videos=len(records),
        total_views=total_views,
        total_likes=total_likes,
        total_comments=total_comments,
        total_watch_time_minutes=total_watch,
        avg_views_per_video=total_views / len(records) if records else 0,
        avg_ctr=sum(ctr_values) / len(ctr_values) if ctr_values else 0,
        total_subscriber_gain=total_subs,
    )


# --- Health & Monitoring ---

@router.get("/health", response_model=HealthCheckResponse)
def health_check():
    """Run system health checks."""
    checker = HealthChecker()
    return checker.check_all()


@router.post("/health/check-and-alert")
def check_and_alert():
    """Run health checks and send alerts for failures."""
    results = run_health_check_and_alert()
    return results


@router.post("/alert/test")
def test_alert(request: AlertRequest):
    """Send a test alert to configured channels."""
    alerter = AlertService()
    alerter.send_alert(request.title, request.message, request.level)
    return {"success": True, "message": "Alert sent"}
