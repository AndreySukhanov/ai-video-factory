from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class TrendItem:
    """Represents a single trending topic from any source."""
    title: str
    description: str = ""
    source: str = ""  # youtube, google_trends, apify, tiktok
    category: str = ""
    score: float = 0.0
    keywords: List[str] = field(default_factory=list)
    url: str = ""
    fetched_at: Optional[datetime] = None
    # Velocity & tracking
    velocity_score: float = 0.0  # views / hours_since_publish
    published_at: Optional[datetime] = None
    view_count: int = 0
    duration_sec: int = 0  # original video duration in seconds
    thumbnail_url: str = ""
    competition_level: Optional[float] = None
    opportunity_score: Optional[float] = None
    # Content type classification
    content_type: str = "other"
    # Viral coefficient: view_count / max(subscriber_count, 1) — anomaly if > 10
    subscriber_count: Optional[int] = None
    viral_coef: Optional[float] = None
    is_anomaly: bool = False
    # Which user keyword found this trend (Trendsee-style keyword tagging)
    matched_keyword: Optional[str] = None

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.utcnow()


class TrendSource(ABC):
    """Abstract base class for trend data sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source."""
        pass

    @abstractmethod
    def fetch_trends(self, region: str = "US", category: str = "", max_results: int = 20,
                     keywords: List[str] = None) -> List[TrendItem]:
        """
        Fetch trending topics.

        Args:
            region: Country/region code (e.g. US, RU, GB)
            category: Optional category filter
            max_results: Maximum number of trends to return

        Returns:
            List of TrendItem objects
        """
        pass
