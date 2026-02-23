"""
Auto-pipeline: trend → ideas → (manual approve) → generate → review queue.
Orchestrates the video creation flow with human checkpoints.
"""
import json
from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.config import settings
from app.models.trend import StoryIdea
from app.models.review import ReviewItem
from app.models import Project, Job
from app.services.pipeline_config import PipelineConfig
from app.services.trendwatcher.trend_analyzer import TrendAnalyzer
from app.services.youtube.metadata_generator import MetadataGenerator


class AutoPipeline:
    """Orchestrates the trend-to-review pipeline (no auto-publish)."""

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.trend_analyzer = TrendAnalyzer()
        self.metadata_generator = MetadataGenerator()

    def run_full_cycle(self, db: Session):
        """
        Execute one pipeline cycle:
        1. [AUTO]  Fetch trends
        2. [AUTO]  LLM → story ideas
        3. [NOTIF] Telegram: "New ideas ready"
        4. [STOP]  Wait for manual approval on /trends
        """
        print("[PIPELINE] Starting cycle...")

        # Step 1: Fetch trends
        print("[PIPELINE] Step 1: Fetching trends...")
        trends = self.trend_analyzer.fetch_all_trends(
            db,
            region=self.config.region,
            max_per_source=self.config.max_trends_per_source,
        )

        # Step 2: Analyze trends → story ideas
        print("[PIPELINE] Step 2: Analyzing trends...")
        ideas = self.trend_analyzer.analyze_trends(
            db,
            trends=trends,
            max_ideas=self.config.max_ideas_per_analysis,
            genre=self.config.default_genre,
            channel_niche=self.config.channel_niche,
            niche_keywords=self.config.niche_keywords,
            content_style=self.config.content_style,
        )

        if not ideas:
            print("[PIPELINE] No ideas generated")
            return {"status": "no_ideas", "trends_count": len(trends)}

        # Step 3: Notify and wait for manual approval
        print("[PIPELINE] Step 3: Ideas ready — awaiting manual approval on /trends")
        try:
            from app.services.monitoring import notify_new_ideas
            notify_new_ideas(ideas)
        except Exception as e:
            print(f"[PIPELINE] Notification error: {e}")

        return {
            "status": "awaiting_approval",
            "trends_count": len(trends),
            "ideas_count": len(ideas),
        }

    def generate_approved(self, db: Session):
        """
        Generate videos for all manually-approved ideas:
        5. [AUTO]  Generate video for each approved idea
        6. [AUTO]  LLM → title/description/tags
        7. [AUTO]  Create ReviewItem (pending_review)
        8. [NOTIF] Telegram: "Video ready for review"
        """
        # Check daily video limit
        today_count = self._count_today_videos(db)
        if today_count >= self.config.max_videos_per_day:
            print(f"[PIPELINE] Daily limit reached ({today_count}/{self.config.max_videos_per_day})")
            return {"status": "limit_reached", "videos_today": today_count}

        # Find approved ideas that haven't been generated yet
        approved_ideas = db.query(StoryIdea).filter(
            StoryIdea.status == "approved"
        ).all()

        if not approved_ideas:
            print("[PIPELINE] No approved ideas to generate")
            return {"status": "no_approved_ideas"}

        remaining_slots = self.config.max_videos_per_day - today_count
        ideas_to_process = approved_ideas[:remaining_slots]

        print(f"[PIPELINE] Generating {len(ideas_to_process)} videos...")
        results = []
        for idea in ideas_to_process:
            try:
                result = self._generate_video_for_idea(db, idea)
                results.append(result)
            except Exception as e:
                print(f"[PIPELINE] Error generating video for idea {idea.id}: {e}")

        return {
            "status": "generated",
            "generated_count": len(results),
            "results": [{"idea_id": r["idea"].id, "project_id": r["project_id"]} for r in results],
        }

    def create_review_item(self, db: Session, idea: StoryIdea, project_id: int, video_url: str):
        """
        After video generation completes, create a ReviewItem and notify.
        Called by the generation callback/webhook.
        """
        # Generate metadata via LLM
        metadata = self.metadata_generator.generate_metadata(
            story_idea=idea.idea_text,
            genre=idea.genre,
        )

        review_item = ReviewItem(
            story_idea_id=idea.id,
            project_id=project_id,
            video_url=video_url,
            title=metadata["title"],
            description=metadata["description"],
            tags_json=json.dumps(metadata.get("tags", [])),
            status="pending_review",
        )
        db.add(review_item)
        db.commit()
        db.refresh(review_item)

        # Notify via Telegram
        try:
            from app.services.monitoring import notify_video_ready
            notify_video_ready(review_item, idea)
        except Exception as e:
            print(f"[PIPELINE] Notification error: {e}")

        return review_item

    def _generate_video_for_idea(self, db: Session, idea: StoryIdea) -> dict:
        """Create a project and queue video generation for an idea."""
        project = Project(
            title=f"Auto: {idea.idea_text[:50]}...",
            logline=idea.idea_text,
            genre=idea.genre,
            target_platform="youtube_shorts",
            status="draft",
        )
        db.add(project)
        db.flush()

        idea.project_id = project.id
        idea.status = "generated"

        # Create generation job
        job = Job(
            type="GENERATE_STORY",
            status="queued",
            payload_json=json.dumps({
                "project_id": project.id,
                "idea_id": idea.id,
                "idea": idea.idea_text,
                "genre": idea.genre,
                "model": self.config.default_model,
                "duration": self.config.default_duration,
                "aspect_ratio": self.config.default_aspect_ratio,
                "from_pipeline": True,
            }),
        )
        db.add(job)
        db.commit()
        db.refresh(project)

        # Enqueue job
        try:
            from app.services.generation_service import enqueue_job
            enqueue_job(job.id)
        except Exception as e:
            print(f"[PIPELINE] Failed to enqueue job: {e}")

        return {
            "idea": idea,
            "project_id": project.id,
            "job_id": job.id,
            "video_url": None,
        }

    def _count_today_videos(self, db: Session) -> int:
        """Count videos generated today."""
        today = date.today()
        return db.query(StoryIdea).filter(
            StoryIdea.status.in_(["generated", "published"]),
            StoryIdea.created_at >= datetime(today.year, today.month, today.day),
        ).count()


# RQ job handler
def handle_auto_pipeline_job(config_overrides: dict = None):
    """RQ job handler for running the auto-pipeline."""
    db = SessionLocal()
    try:
        config = PipelineConfig()
        if config_overrides:
            for key, value in config_overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        pipeline = AutoPipeline(config=config)
        return pipeline.run_full_cycle(db)
    finally:
        db.close()
