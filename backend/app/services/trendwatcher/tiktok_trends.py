from typing import List
from datetime import datetime, timezone
from .base import TrendSource, TrendItem
from app.core.config import settings


class TikTokTrendsSource(TrendSource):
    """
    Fetch trending TikTok content via Apify actors.
    TikTok trends hit YouTube Shorts with 2-5 day delay = leading signal.
    """

    # Region-specific hashtags and search queries
    REGION_HASHTAGS = {
        "US": ["aiart", "aigenerated", "animation", "microdrama", "storytime"],
        "GB": ["aiart", "aigenerated", "animation", "microdrama", "storytime"],
        "RU": ["нейросеть", "ииарт", "анимация", "микродрама", "сторителлинг"],
        "DE": ["kigeneration", "animation", "kurzfilm", "microdrama"],
        "JP": ["AI生成", "アニメ", "ショートドラマ", "マイクロドラマ"],
        "BR": ["iagerativa", "animacao", "microdrama", "historiacurta"],
        "IN": ["aigenerated", "animation", "microdrama", "storytime"],
    }

    REGION_QUERIES = {
        "US": ["AI generated story", "AI animation viral", "microdrama POV", "skit comedy story"],
        "GB": ["AI generated story UK", "animation drama", "microdrama POV"],
        "RU": ["нейросеть видео", "ИИ генерация", "микродрама POV", "анимация история"],
        "DE": ["KI generiert video", "animation story deutsch", "microdrama"],
        "JP": ["AI生成動画", "アニメストーリー", "マイクロドラマ"],
        "BR": ["IA video gerado", "animação drama", "microdrama brasil"],
        "IN": ["AI generated video india", "animation story hindi", "microdrama POV"],
    }

    @property
    def source_name(self) -> str:
        return "tiktok"

    def __init__(self):
        self.api_token = settings.APIFY_API_TOKEN

    def fetch_trends(self, region: str = "US", category: str = "", max_results: int = 20) -> List[TrendItem]:
        if not self.api_token:
            print("[TRENDS] APIFY_API_TOKEN not set, skipping TikTok source")
            return []

        trends = self._try_hashtag_scrape(region, max_results)
        if not trends:
            trends = self._try_search_scrape(region, max_results)
        return trends

    def _try_hashtag_scrape(self, region: str, max_results: int) -> List[TrendItem]:
        """Scrape TikTok trending hashtags via Apify."""
        try:
            import requests

            actor_url = "https://api.apify.com/v2/acts/clockworks~free-tiktok-scraper/run-sync-get-dataset-items"
            params = {"token": self.api_token}
            hashtags = self.REGION_HASHTAGS.get(region.upper(), self.REGION_HASHTAGS["US"])
            payload = {
                "hashtags": hashtags,
                "resultsPerPage": min(max_results * 2, 50),
                "shouldDownloadVideos": False,
            }

            response = requests.post(actor_url, json=payload, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()

            return self._parse_results(data, max_results)
        except Exception as e:
            print(f"[TRENDS] TikTok hashtag scraper error: {e}")
            return []

    def _try_search_scrape(self, region: str, max_results: int) -> List[TrendItem]:
        """Fallback: search for trending TikTok videos."""
        try:
            import requests

            actor_url = "https://api.apify.com/v2/acts/clockworks~free-tiktok-scraper/run-sync-get-dataset-items"
            params = {"token": self.api_token}
            queries = self.REGION_QUERIES.get(region.upper(), self.REGION_QUERIES["US"])
            payload = {
                "searchQueries": queries,
                "resultsPerPage": min(max_results * 2, 50),
                "shouldDownloadVideos": False,
            }

            response = requests.post(actor_url, json=payload, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()

            return self._parse_results(data, max_results)
        except Exception as e:
            print(f"[TRENDS] TikTok search scraper error: {e}")
            return []

    def _parse_results(self, data: list, max_results: int) -> List[TrendItem]:
        """Parse TikTok scraper results into TrendItems with velocity."""
        trends = []
        seen_urls = set()

        for item in data[:max_results * 3]:
            title = item.get("text", item.get("desc", ""))
            if not title or len(title) < 5:
                continue

            plays = item.get("playCount", item.get("plays", 0)) or 0
            likes = item.get("diggCount", item.get("likes", 0)) or 0
            shares = item.get("shareCount", item.get("shares", 0)) or 0

            # Parse creation time for velocity calculation
            create_time = item.get("createTime", item.get("createTimeISO", 0))
            published_at = None
            hours_since = 24  # default

            if isinstance(create_time, (int, float)) and create_time > 0:
                published_at = datetime.fromtimestamp(create_time, tz=timezone.utc)
                hours_since = max(1, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)
            elif isinstance(create_time, str) and create_time:
                try:
                    published_at = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                    hours_since = max(1, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)
                except (ValueError, TypeError):
                    pass

            velocity = plays / hours_since

            # Extract hashtags
            hashtags = []
            for tag in item.get("hashtags", item.get("challenges", [])):
                if isinstance(tag, dict):
                    name = tag.get("name", tag.get("title", ""))
                elif isinstance(tag, str):
                    name = tag
                else:
                    continue
                if name:
                    hashtags.append(name)

            # Extract sound/audio name — key leading signal for YouTube
            music = item.get("music", item.get("musicMeta", {}))
            sound_name = ""
            if isinstance(music, dict):
                sound_name = music.get("title", music.get("musicName", ""))
                if sound_name and sound_name not in hashtags:
                    hashtags.append(f"sound:{sound_name}")

            # Build URL
            url = item.get("webVideoUrl", item.get("url", ""))
            if not url:
                author = item.get("authorMeta", {}).get("name", "") or item.get("author", {}).get("uniqueId", "")
                vid_id = item.get("id", "")
                if author and vid_id:
                    url = f"https://www.tiktok.com/@{author}/video/{vid_id}"

            if url in seen_urls:
                continue
            seen_urls.add(url)

            description = f"TikTok | {self._format_count(plays)} plays, {self._format_count(likes)} likes"
            if sound_name:
                description += f" | {sound_name}"

            content_type = self._classify_content_type(title, hashtags)

            trends.append(TrendItem(
                title=title[:200],
                description=description,
                source=self.source_name,
                category="tiktok_trending",
                score=plays / 1000,
                velocity_score=velocity,
                published_at=published_at,
                view_count=plays,
                keywords=hashtags[:10],
                url=url,
                content_type=content_type,
            ))

            if len(trends) >= max_results:
                break

        trends.sort(key=lambda t: t.velocity_score, reverse=True)
        print(f"[TRENDS] TikTok: fetched {len(trends)} videos")
        return trends

    @staticmethod
    def _classify_content_type(title: str, hashtags: list) -> str:
        text = f"{title} {' '.join(hashtags)}".lower()
        ai_kw = ["ai", "aigenerat", "aiart", "sora", "runway", "midjourney", "kling",
                  "нейросеть", "ии", "ki generi", "ia gerad", "ai生成"]
        anim_kw = ["animation", "animated", "cartoon", "anime", "3d", "анимация", "мультик", "アニメ", "animação"]
        story_kw = ["story", "storytime", "microdrama", "pov", "drama", "short film",
                     "история", "микродрама", "драма", "ドラマ", "história"]
        skit_kw = ["skit", "sketch", "comedy skit", "скетч", "юмор"]
        if any(kw in text for kw in ai_kw):
            return "ai_generated"
        if any(kw in text for kw in anim_kw):
            return "animation"
        if any(kw in text for kw in story_kw):
            return "story"
        if any(kw in text for kw in skit_kw):
            return "skit"
        return "other"

    @staticmethod
    def _format_count(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.0f}K"
        return str(n)
