from typing import List, Optional
from datetime import datetime, timezone
from .base import TrendSource, TrendItem
from app.core.config import settings


class InstagramReelsTrendWatcher(TrendSource):
    """
    Fetch trending Instagram Reels via Apify actor.
    Instagram Reels is the primary source of viral short-form content — same niche as Trendsee.io.
    """

    # Region-specific hashtags
    REGION_HASHTAGS = {
        "US": ["microdrama", "aivideo", "shortfilm", "viralvideo", "aiart"],
        "GB": ["microdrama", "aivideo", "shortfilm", "viralvideo", "aiart"],
        "RU": ["микродрама", "нейросеть", "аивидео", "кроткийфильм", "aiарт"],
        "DE": ["microdrama", "kigeneration", "kurzfilm", "viralvideo"],
        "JP": ["マイクロドラマ", "AI動画", "ショートフィルム", "バイラル"],
        "BR": ["microdrama", "iavideo", "filmecurto", "viralvideo"],
        "IN": ["microdrama", "aivideo", "shortfilm", "reels"],
    }

    @property
    def source_name(self) -> str:
        return "instagram"

    def __init__(self):
        self.api_token = settings.APIFY_API_TOKEN

    def fetch_trends(self, region: str = "US", category: str = "", max_results: int = 20,
                     keywords: List[str] = None) -> List[TrendItem]:
        if not self.api_token:
            print("[TRENDS] APIFY_API_TOKEN not set, skipping Instagram source")
            return []

        if keywords:
            hashtags = keywords
        else:
            config_hashtags = getattr(settings, "INSTAGRAM_HASHTAGS", None)
            hashtags = config_hashtags if config_hashtags else self.REGION_HASHTAGS.get(region.upper(), self.REGION_HASHTAGS["US"])

        trends = self._try_hashtag_scrape(hashtags, max_results)
        if not trends:
            print("[TRENDS] Instagram hashtag scrape returned empty, no fallback")
        return trends

    def _try_hashtag_scrape(self, hashtags: List[str], max_results: int) -> List[TrendItem]:
        """Scrape Instagram Reels trending by hashtag via Apify instagram-scraper.
        Sends one request per hashtag to correctly tag matched_keyword on each result."""
        import requests

        actor_url = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"
        params = {"token": self.api_token}
        all_trends: List[TrendItem] = []
        seen_urls: set = set()
        per_hashtag = max(3, max_results // max(len(hashtags), 1))

        for hashtag in hashtags:
            if len(all_trends) >= max_results:
                break
            try:
                direct_url = f"https://www.instagram.com/explore/tags/{hashtag}/"
                payload = {
                    "directUrls": [direct_url],
                    "resultsType": "posts",
                    "resultsLimit": per_hashtag * 3,
                    "addParentData": False,
                }
                response = requests.post(actor_url, json=payload, params=params, timeout=180)
                response.raise_for_status()
                data = response.json()
                batch = self._parse_results(data, per_hashtag, seen_urls, matched_keyword=hashtag)
                all_trends.extend(batch)
            except Exception as e:
                print(f"[TRENDS] Instagram scraper error for #{hashtag}: {e}")
                continue

        all_trends.sort(key=lambda t: t.velocity_score, reverse=True)
        print(f"[TRENDS] Instagram: fetched {len(all_trends)} posts across {len(hashtags)} hashtags")
        return all_trends[:max_results]

    def _parse_results(self, data: list, max_results: int,
                       seen_urls: set = None, matched_keyword: str = None) -> List[TrendItem]:
        """Parse Instagram scraper results into TrendItems."""
        trends = []
        if seen_urls is None:
            seen_urls = set()

        for item in data[:max_results * 3]:
            # Accept all post types (Image, Sidecar, Video, GraphVideo, Reel)
            # Instagram hashtag explore returns mostly photos/carousels but all are trend signals
            caption = item.get("caption", item.get("alt", "")) or ""
            short_code = item.get("shortCode", item.get("shortcode", ""))
            if not caption and not short_code:
                continue

            # Title: first non-empty line of caption
            title = next((line.strip() for line in caption.split("\n") if line.strip()), "")
            if not title:
                title = short_code  # fallback to shortCode as title
            if not title:
                continue

            # Views: prefer videoViewCount, estimate from likes for photos
            views = (
                item.get("videoViewCount") or
                item.get("videoPlayCount") or
                item.get("playCount") or
                0
            )
            likes = item.get("likesCount", item.get("likes", 0)) or 0
            if likes < 0:
                likes = 0
            comments = item.get("commentsCount", item.get("comments", 0)) or 0

            # Score based on engagement (views preferred, likes as proxy)
            score = (views / 1000) if views else (likes / 100)

            # Published time → velocity
            timestamp = item.get("timestamp", item.get("taken_at_timestamp", ""))
            published_at = None
            hours_since = 24

            if isinstance(timestamp, (int, float)) and timestamp > 0:
                published_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                hours_since = max(1, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)
            elif isinstance(timestamp, str) and timestamp:
                try:
                    published_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    hours_since = max(1, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)
                except (ValueError, TypeError):
                    pass

            engagement = (views or likes * 10) / hours_since
            velocity_score = engagement

            # Thumbnail
            thumbnail_url = item.get("displayUrl", item.get("thumbnailUrl", item.get("previewUrl", ""))) or None

            # URL (short_code already extracted above)
            url = item.get("url", "")
            if not url and short_code:
                url = f"https://www.instagram.com/p/{short_code}/"
            if not url:
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract hashtags from caption
            import re
            hashtags = re.findall(r"#(\w+)", caption)[:10]

            # Instagram doesn't return follower count without separate profile fetch
            # viral_coef stays None unless we have it
            subscriber_count = None
            viral_coef = None
            is_anomaly = False

            description = f"Instagram | {self._format_count(views)} views, {self._format_count(likes)} likes"

            trends.append(TrendItem(
                title=title[:200],
                description=description,
                source=self.source_name,
                category="instagram_reels",
                score=score,
                velocity_score=velocity_score,
                published_at=published_at,
                view_count=int(views) if views else None,
                thumbnail_url=thumbnail_url,
                keywords=hashtags,
                url=url,
                content_type="reel",
                subscriber_count=subscriber_count,
                viral_coef=viral_coef,
                is_anomaly=is_anomaly,
                matched_keyword=matched_keyword,
            ))

            if len(trends) >= max_results:
                break

        return trends

    @staticmethod
    def _format_count(n) -> str:
        if not n:
            return "0"
        n = int(n)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.0f}K"
        return str(n)
