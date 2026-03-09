"""
Configuration for the autonomous video pipeline.
"""
from dataclasses import dataclass, field
from typing import List
from app.core.config import settings


@dataclass
class PipelineConfig:
    """Configuration for the auto-pipeline."""

    # How many videos to generate per day
    max_videos_per_day: int = settings.AUTO_PIPELINE_MAX_VIDEOS_PER_DAY

    # Default genre filter (empty = all genres)
    default_genre: str = settings.AUTO_PIPELINE_DEFAULT_GENRE

    # Video generation settings
    default_model: str = "seedance"
    default_duration: int = 6
    default_aspect_ratio: str = "9:16"

    # YouTube upload settings
    default_privacy: str = "private"  # private, unlisted, public
    generate_metadata: bool = True

    # Trend fetch settings
    region: str = "US"
    max_trends_per_source: int = 20
    max_ideas_per_analysis: int = 5

    # Allowed genres for auto-generation
    allowed_genres: List[str] = field(default_factory=lambda: [
        "drama", "comedy", "horror", "thriller", "romance", "sci-fi", "mystery"
    ])

    # Niche filter — focus the channel on a specific niche
    channel_niche: str = ""           # e.g. "horror stories", "life hacks"
    niche_keywords: List[str] = field(default_factory=list)  # keywords for filtering
    content_style: str = ""           # e.g. "cinematic dark", "bright upbeat"
