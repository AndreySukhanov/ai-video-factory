"""
Redis-based YouTube API quota tracking.
YouTube Data API v3: 10,000 units/day, upload = 1,600 units.
"""
from datetime import date
import redis
from app.core.config import settings


class QuotaTracker:
    """Track YouTube API quota usage via Redis."""

    DAILY_LIMIT = 10000
    UPLOAD_COST = 1600  # units per video upload
    KEY_PREFIX = "youtube_quota"

    def __init__(self):
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            try:
                self._redis = redis.from_url(settings.REDIS_URL)
            except Exception as e:
                print(f"[QUOTA] Redis connection failed: {e}")
                return None
        return self._redis

    def _today_key(self) -> str:
        return f"{self.KEY_PREFIX}:{date.today().isoformat()}"

    def get_usage(self) -> int:
        """Get current day's quota usage."""
        r = self._get_redis()
        if r is None:
            return 0
        val = r.get(self._today_key())
        return int(val) if val else 0

    def get_remaining(self) -> int:
        """Get remaining quota for today."""
        return max(0, self.DAILY_LIMIT - self.get_usage())

    def can_upload(self) -> bool:
        """Check if there's enough quota for an upload."""
        return self.get_remaining() >= self.UPLOAD_COST

    def record_upload(self):
        """Record an upload (1600 units)."""
        self._increment(self.UPLOAD_COST)

    def record_usage(self, units: int):
        """Record arbitrary quota usage."""
        self._increment(units)

    def _increment(self, units: int):
        r = self._get_redis()
        if r is None:
            return
        key = self._today_key()
        pipe = r.pipeline()
        pipe.incrby(key, units)
        pipe.expire(key, 86400)  # TTL 24 hours
        pipe.execute()

    def get_status(self) -> dict:
        """Get full quota status."""
        usage = self.get_usage()
        remaining = max(0, self.DAILY_LIMIT - usage)
        max_uploads = remaining // self.UPLOAD_COST
        return {
            "daily_limit": self.DAILY_LIMIT,
            "used": usage,
            "remaining": remaining,
            "upload_cost": self.UPLOAD_COST,
            "max_uploads_remaining": max_uploads,
            "date": date.today().isoformat(),
        }
