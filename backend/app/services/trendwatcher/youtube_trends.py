from typing import List
from datetime import datetime, timedelta, timezone
from .base import TrendSource, TrendItem
from app.core.config import settings


class YouTubeTrendsSource(TrendSource):
    """Fetch trending YouTube Shorts via YouTube Data API v3 with velocity scoring."""

    REGION_LANG_MAP = {
        "US": "en", "GB": "en", "AU": "en", "CA": "en",
        "RU": "ru", "DE": "de", "FR": "fr", "ES": "es",
        "JP": "ja", "KR": "ko", "BR": "pt", "IN": "hi",
        "IT": "it", "NL": "nl", "PL": "pl", "TR": "tr",
        "MX": "es", "AR": "es", "CL": "es",
    }

    # Region-specific search queries targeting AI-reproducible content:
    # stories, animations, AI-generated, skits, micro-dramas
    REGION_QUERIES = {
        "US": [
            "#shorts AI generated",
            "#shorts animation story",
            "#shorts microdrama",
            "#shorts story time dramatic",
            "#shorts skit comedy",
            "#shorts AI art video",
        ],
        "GB": [
            "#shorts AI generated",
            "#shorts animation story UK",
            "#shorts microdrama",
            "#shorts story time dramatic",
            "#shorts skit comedy british",
        ],
        "RU": [
            "#shorts ИИ генерация",
            "#shorts анимация история",
            "#shorts микродрама",
            "#shorts сторителлинг драма",
            "#shorts скетч комедия",
        ],
        "DE": [
            "#shorts KI generiert",
            "#shorts animation geschichte",
            "#shorts microdrama deutsch",
            "#shorts kurzfilm story",
        ],
        "JP": [
            "#shorts AI生成",
            "#shorts アニメ ストーリー",
            "#shorts マイクロドラマ",
            "#shorts ショートドラマ",
        ],
        "BR": [
            "#shorts IA gerada",
            "#shorts animação história",
            "#shorts microdrama",
            "#shorts história curta drama",
        ],
        "IN": [
            "#shorts AI generated india",
            "#shorts animation story hindi",
            "#shorts microdrama",
            "#shorts story dramatic hindi",
        ],
    }

    # Fallback queries for unlisted regions
    DEFAULT_QUERIES = [
        "#shorts AI generated",
        "#shorts animation story",
        "#shorts microdrama",
        "#shorts story time dramatic",
        "#shorts skit comedy",
    ]

    @property
    def source_name(self) -> str:
        return "youtube"

    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY
        self._service = None

    def _get_service(self):
        if self._service is None:
            if not self.api_key:
                raise ValueError("YOUTUBE_API_KEY is not configured")
            from googleapiclient.discovery import build
            self._service = build("youtube", "v3", developerKey=self.api_key)
        return self._service

    def fetch_trends(self, region: str = "US", category: str = "", max_results: int = 20) -> List[TrendItem]:
        """
        Fetch viral YouTube Shorts using dual time-window strategy:
        - Emerging (24h): fresh, fast-growing content
        - Confirmed (3 days): proven viral content
        Results sorted by velocity (views/hour), not absolute views.
        """
        if not self.api_key:
            print("[TRENDS] YOUTUBE_API_KEY not set, returning empty list")
            return []

        try:
            service = self._get_service()
            lang = self.REGION_LANG_MAP.get(region.upper(), "en")
            half = max_results // 2

            # Pass 1: Emerging (24h) — fresh content, order by relevance
            emerging = self._search_window(
                service, region, lang,
                published_after=self._get_date_hours_ago(24),
                order="relevance",
                max_results=half,
            )

            # Pass 2: Confirmed (3 days) — proven viral, order by viewCount
            confirmed = self._search_window(
                service, region, lang,
                published_after=self._get_date_hours_ago(72),
                order="viewCount",
                max_results=half,
            )

            # Merge, deduplicate, sort by velocity
            all_trends = self._merge_and_deduplicate(emerging, confirmed)
            all_trends.sort(key=lambda t: t.velocity_score, reverse=True)

            print(f"[TRENDS] YouTube: fetched {len(all_trends)} shorts from {region} "
                  f"(emerging={len(emerging)}, confirmed={len(confirmed)})")
            return all_trends[:max_results]

        except Exception as e:
            print(f"[TRENDS] YouTube API error: {e}")
            return []

    def _search_window(self, service, region: str, lang: str,
                       published_after: str, order: str,
                       max_results: int) -> List[TrendItem]:
        """Search for Shorts within a specific time window."""
        trends = []
        queries = self.REGION_QUERIES.get(region.upper(), self.DEFAULT_QUERIES)

        for query in queries:
            if len(trends) >= max_results:
                break

            try:
                search_response = service.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    videoDuration="short",
                    order=order,
                    regionCode=region,
                    relevanceLanguage=lang,
                    publishedAfter=published_after,
                    maxResults=10,
                ).execute()

                video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
                if not video_ids:
                    continue

                details_response = service.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=",".join(video_ids),
                ).execute()

                for item in details_response.get("items", []):
                    if len(trends) >= max_results:
                        break

                    duration = item.get("contentDetails", {}).get("duration", "")
                    seconds = self._parse_duration(duration)
                    if seconds > 60 or seconds < 5:
                        continue

                    snippet = item.get("snippet", {})
                    stats = item.get("statistics", {})
                    channel = snippet.get("channelTitle", "")
                    views = int(stats.get("viewCount", 0))

                    # Calculate velocity (views per hour since publish)
                    published_at = self._parse_published_at(snippet.get("publishedAt", ""))
                    hours_since = max(1, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600) if published_at else 24
                    velocity = views / hours_since

                    video_url = f"https://youtube.com/shorts/{item['id']}"
                    if any(t.url == video_url for t in trends):
                        continue

                    tags = snippet.get("tags", [])[:10] if snippet.get("tags") else [channel]
                    content_type = self._classify_content_type(
                        snippet.get("title", ""),
                        snippet.get("description", ""),
                        tags,
                    )

                    trends.append(TrendItem(
                        title=snippet.get("title", ""),
                        description=snippet.get("description", "")[:500],
                        source=self.source_name,
                        category=query.replace("#shorts ", ""),
                        score=views / 1000,
                        velocity_score=velocity,
                        published_at=published_at,
                        view_count=views,
                        duration_sec=seconds,
                        thumbnail_url=snippet.get("thumbnails", {}).get("high", snippet.get("thumbnails", {}).get("medium", {})).get("url", ""),
                        keywords=tags,
                        url=video_url,
                        content_type=content_type,
                    ))

            except Exception as e:
                print(f"[TRENDS] YouTube search '{query}' error: {e}")
                continue

        return trends

    def estimate_competition(self, query: str, region: str = "US") -> float:
        """
        Estimate competition level by counting Shorts published in last 24h on this topic.
        Returns 0.0 (low) to 1.0 (very saturated).
        Costs 100 API units per call — use sparingly.
        """
        try:
            service = self._get_service()
            search_response = service.search().list(
                part="snippet",
                q=query,
                type="video",
                videoDuration="short",
                order="date",
                regionCode=region,
                publishedAfter=self._get_date_hours_ago(24),
                maxResults=1,  # We only need totalResults count
            ).execute()

            total = search_response.get("pageInfo", {}).get("totalResults", 0)

            if total <= 10:
                return 0.2
            elif total <= 50:
                return 0.5
            elif total <= 200:
                return 0.7
            else:
                return 0.9

        except Exception as e:
            print(f"[TRENDS] Competition check error for '{query}': {e}")
            return 0.5

    @staticmethod
    def _classify_content_type(title: str, description: str, tags: list) -> str:
        """Classify video content type based on title, description and tags."""
        text = f"{title} {description} {' '.join(tags)}".lower()

        ai_keywords = [
            "ai generated", "ai art", "ai video", "ai animation",
            "sora", "runway", "pika", "kling", "midjourney", "stable diffusion",
            "veo", "генерация ии", "ии видео", "нейросеть", "ki generiert",
            "ia gerada", "ai生成",
        ]
        animation_keywords = [
            "animation", "animated", "cartoon", "anime", "3d render",
            "pixar style", "ghibli", "motion graphics", "анимация", "мультик",
            "мультфильм", "アニメ", "animação",
        ]
        story_keywords = [
            "story time", "storytime", "micro drama", "microdrama", "short film",
            "mini movie", "pov:", "dramatic story", "short story", "сторителлинг",
            "история", "микродрама", "драма", "kurzfilm", "ドラマ", "história",
        ]
        skit_keywords = [
            "skit", "comedy skit", "sketch", "funny skit", "roleplay",
            "скетч", "юмор", "комедия",
        ]
        music_keywords = [
            "music video", "lyric video", "ai music", "song",
            "клип", "музыка",
        ]

        if any(kw in text for kw in ai_keywords):
            return "ai_generated"
        if any(kw in text for kw in animation_keywords):
            return "animation"
        if any(kw in text for kw in story_keywords):
            return "story"
        if any(kw in text for kw in skit_keywords):
            return "skit"
        if any(kw in text for kw in music_keywords):
            return "music_video"
        return "other"

    @staticmethod
    def _merge_and_deduplicate(list1: List[TrendItem], list2: List[TrendItem]) -> List[TrendItem]:
        """Merge two trend lists, removing duplicates by URL."""
        seen_urls = set()
        merged = []
        for item in list1 + list2:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                merged.append(item)
        return merged

    @staticmethod
    def _get_date_hours_ago(hours: int) -> str:
        """Get ISO date string for N hours ago."""
        d = datetime.utcnow() - timedelta(hours=hours)
        return d.strftime("%Y-%m-%dT00:00:00Z")

    @staticmethod
    def _parse_published_at(iso_str: str):
        """Parse ISO 8601 datetime string to datetime object."""
        if not iso_str:
            return None
        try:
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_duration(iso_duration: str) -> int:
        """Parse ISO 8601 duration (PT1M30S) to seconds."""
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
