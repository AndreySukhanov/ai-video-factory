"""
Review Queue API — review generated videos before publishing.
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.db import get_db
from app.models.review import ReviewItem
from app.models.trend import StoryIdea
from app.models.youtube_channel import YouTubeChannel, YouTubeUpload
from app.schemas.review import (
    ReviewItemCreate, ReviewItemRead, ReviewApproveRequest, ReviewScheduleRequest,
    ReviewRejectRequest, ReviewActionResponse,
)

router = APIRouter()


def _enrich_review_item(item: ReviewItem, db: Session) -> ReviewItemRead:
    """Add joined fields from StoryIdea."""
    data = ReviewItemRead.model_validate(item)
    if item.story_idea_id:
        idea = db.query(StoryIdea).filter(StoryIdea.id == item.story_idea_id).first()
        if idea:
            data.genre = idea.genre
            data.virality_score = idea.virality_score
            data.idea_text = idea.idea_text
    return data


@router.post("/", response_model=ReviewItemRead)
def create_review_item(
    payload: ReviewItemCreate,
    db: Session = Depends(get_db),
):
    """Create a new review item from a generated video."""
    item = ReviewItem(
        video_url=payload.video_url,
        title=payload.title,
        description=payload.description,
        tags_json=json.dumps(payload.tags),
        project_id=payload.project_id,
        status="pending_review",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _enrich_review_item(item, db)


@router.get("/", response_model=List[ReviewItemRead])
@router.get("/queue", response_model=List[ReviewItemRead])
def get_review_queue(
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get videos waiting for review."""
    query = db.query(ReviewItem)
    if status:
        query = query.filter(ReviewItem.status == status)
    query = query.order_by(ReviewItem.created_at.desc())
    items = query.offset(skip).limit(limit).all()
    return [_enrich_review_item(item, db) for item in items]


@router.get("/{item_id}", response_model=ReviewItemRead)
def get_review_item(item_id: int, db: Session = Depends(get_db)):
    """Get a single review item."""
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return _enrich_review_item(item, db)


@router.post("/{item_id}/approve", response_model=ReviewActionResponse)
def approve_and_upload(
    item_id: int,
    request: ReviewApproveRequest = None,
    db: Session = Depends(get_db),
):
    """Approve video and upload as private to YouTube."""
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status not in ("pending_review", "rejected"):
        raise HTTPException(status_code=400, detail=f"Cannot approve item with status '{item.status}'")

    # Apply edits if provided
    if request:
        if request.title:
            item.title = request.title
        if request.description:
            item.description = request.description
        if request.tags is not None:
            item.tags_json = json.dumps(request.tags)
        if request.reviewer_notes:
            item.reviewer_notes = request.reviewer_notes

    # Upload as private to YouTube
    channel = db.query(YouTubeChannel).filter(YouTubeChannel.is_active == True).first()
    if not channel:
        raise HTTPException(status_code=400, detail="No active YouTube channel connected")

    try:
        from app.services.youtube.uploader import YouTubeUploader
        uploader = YouTubeUploader()
        tags = json.loads(item.tags_json) if item.tags_json else []

        # Add AI disclaimer to description
        description = item.description or ""
        if "This video was created with AI" not in description:
            description += "\n\n⚠️ This video was created with AI tools"

        upload = uploader.upload_video(
            db=db,
            channel_id=channel.id,
            video_path_or_url=item.video_url,
            title=item.title,
            description=description,
            tags=tags,
            privacy_status="private",
            project_id=item.project_id,
            story_idea_id=item.story_idea_id,
        )
        item.youtube_upload_id = upload.id
        item.status = "uploaded"
        db.commit()
        db.refresh(item)

        return ReviewActionResponse(
            success=True,
            item=_enrich_review_item(item, db),
            message=f"Uploaded as private: {upload.youtube_url}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/{item_id}/schedule", response_model=ReviewActionResponse)
def approve_and_schedule(
    item_id: int,
    request: ReviewScheduleRequest,
    db: Session = Depends(get_db),
):
    """Approve video and schedule publication on YouTube."""
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status not in ("pending_review", "rejected"):
        raise HTTPException(status_code=400, detail=f"Cannot schedule item with status '{item.status}'")

    # Apply edits
    if request.title:
        item.title = request.title
    if request.description:
        item.description = request.description
    if request.tags is not None:
        item.tags_json = json.dumps(request.tags)
    if request.reviewer_notes:
        item.reviewer_notes = request.reviewer_notes

    channel = db.query(YouTubeChannel).filter(YouTubeChannel.is_active == True).first()
    if not channel:
        raise HTTPException(status_code=400, detail="No active YouTube channel connected")

    try:
        from app.services.youtube.uploader import YouTubeUploader
        uploader = YouTubeUploader()
        tags = json.loads(item.tags_json) if item.tags_json else []

        description = item.description or ""
        if "This video was created with AI" not in description:
            description += "\n\n⚠️ This video was created with AI tools"

        upload = uploader.upload_video(
            db=db,
            channel_id=channel.id,
            video_path_or_url=item.video_url,
            title=item.title,
            description=description,
            tags=tags,
            privacy_status="scheduled",
            scheduled_publish_at=request.scheduled_publish_at,
            project_id=item.project_id,
            story_idea_id=item.story_idea_id,
        )
        item.youtube_upload_id = upload.id
        item.status = "uploaded"
        db.commit()
        db.refresh(item)

        return ReviewActionResponse(
            success=True,
            item=_enrich_review_item(item, db),
            message=f"Scheduled: {upload.youtube_url}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schedule failed: {str(e)}")


@router.post("/{item_id}/reject", response_model=ReviewActionResponse)
def reject_item(
    item_id: int,
    request: ReviewRejectRequest = None,
    db: Session = Depends(get_db),
):
    """Reject a video."""
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    item.status = "rejected"
    if request and request.reviewer_notes:
        item.reviewer_notes = request.reviewer_notes
    db.commit()
    db.refresh(item)

    return ReviewActionResponse(
        success=True,
        item=_enrich_review_item(item, db),
        message="Video rejected",
    )


@router.post("/{item_id}/regenerate", response_model=ReviewActionResponse)
def regenerate_video(item_id: int, db: Session = Depends(get_db)):
    """Re-queue video generation for this idea."""
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    if not item.story_idea_id:
        raise HTTPException(status_code=400, detail="No linked story idea for regeneration")

    idea = db.query(StoryIdea).filter(StoryIdea.id == item.story_idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Linked story idea not found")

    # Reset idea to approved so pipeline can regenerate
    idea.status = "approved"
    item.status = "rejected"
    item.reviewer_notes = (item.reviewer_notes or "") + "\n[Regeneration requested]"
    db.commit()
    db.refresh(item)

    return ReviewActionResponse(
        success=True,
        item=_enrich_review_item(item, db),
        message="Idea reset to 'approved' — regenerate via /trends or pipeline",
    )


@router.post("/{item_id}/publish", response_model=ReviewActionResponse)
def publish_video(item_id: int, db: Session = Depends(get_db)):
    """Change an uploaded private video to public on YouTube."""
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    if item.status != "uploaded":
        raise HTTPException(status_code=400, detail=f"Can only publish uploaded videos, current status: '{item.status}'")

    # Find the exact linked upload record first (safe path)
    upload = None
    if item.youtube_upload_id:
        upload = db.query(YouTubeUpload).filter(YouTubeUpload.id == item.youtube_upload_id).first()

    # Backward-compatibility fallback for older records without explicit link.
    # Only auto-link when there is exactly one candidate to avoid publishing wrong video.
    if not upload and item.project_id:
        candidates = db.query(YouTubeUpload).filter(
            YouTubeUpload.project_id == item.project_id,
            YouTubeUpload.youtube_video_id.isnot(None),
        ).order_by(YouTubeUpload.id.desc()).limit(5).all()

        if len(candidates) == 1:
            upload = candidates[0]
            item.youtube_upload_id = upload.id
            db.commit()
            db.refresh(item)
        elif len(candidates) > 1:
            raise HTTPException(
                status_code=409,
                detail="Multiple YouTube uploads found for this project; item is not linked to a specific upload",
            )

    if not upload or not upload.youtube_video_id:
        raise HTTPException(status_code=400, detail="No YouTube upload found for this video")

    channel = db.query(YouTubeChannel).filter(YouTubeChannel.id == upload.channel_id).first()
    if not channel:
        raise HTTPException(status_code=400, detail="YouTube channel not found")

    try:
        from app.services.youtube.uploader import YouTubeUploader
        uploader = YouTubeUploader()
        access_token = uploader._get_valid_token(db, channel)

        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)
        youtube = build("youtube", "v3", credentials=creds)

        youtube.videos().update(
            part="status",
            body={
                "id": upload.youtube_video_id,
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            },
        ).execute()

        upload.privacy_status = "public"
        upload.status = "published"
        item.status = "published"
        db.commit()
        db.refresh(item)

        return ReviewActionResponse(
            success=True,
            item=_enrich_review_item(item, db),
            message=f"Published: {upload.youtube_url}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publish failed: {str(e)}")
