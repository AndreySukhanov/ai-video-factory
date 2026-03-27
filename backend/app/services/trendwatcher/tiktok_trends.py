from typing import List
from datetime import datetime, timezone
from .base import TrendSource, TrendItem
from app.core.config import settings


class TikTokTrendsSource(TrendSource):
    """
    Fetch trending TikTok content.
    Primary: RapidAPI tiktok-scraper7 (free tier, no account needed).
    Fallback: Apify clockworks~free-tiktok-scraper.
    """

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
        "US": ["AI generated story", "AI animation viral", "microdrama POV"],
        "RU": ["нейросеть видео", "ИИ генерация", "микродрама"],
        "DE": ["KI generiert video", "animation story"],
        "JP": ["AI生成動画", "マイクロドラマ"],
        "BR": ["IA video gerado", "microdrama brasil"],
    }

    REGION_CODES = {
        "US": "US", "GB": "GB", "RU": "RU", "DE": "DE",
        "JP": "JP", "BR": "BR", "IN": "IN",
    }

    @property
    def source_name(self) -> str:
        return "tiktok"

    def __init__(self):
        self.rapidapi_key = settings.RAPIDAPI_KEY
        self.apify_token = settings.APIFY_API_TOKEN

    def fetch_trends(self, region: str = "US", category: str = "", max_results: int = 20,
                     keywords: List[str] = None) -> List[TrendItem]:
        hashtags = keywords if keywords else self.REGION_HASHTAGS.get(region.upper(), self.REGION_HASHTAGS["US"])

        if self.rapidapi_key:
            trends = self._fetch_rapidapi(hashtags, region, max_results)
            if trends:
                return trends
            print("[TRENDS] TikTok RapidAPI returned empty, trying Apify fallback")

        if self.apify_token:
            return self._fetch_apify(hashtags, region, max_results)

        print("[TRENDS] No TikTok API configured (set RAPIDAPI_KEY or APIFY_API_TOKEN)")
        return []

    def _fetch_rapidapi(self, hashtags: List[str], region: str, max_results: int) -> List[TrendItem]:
        """Fetch via RapidAPI tiktok-scraper7 — free tier, 500 req/month."""
        import requests

        all_items: list = []
        seen_ids: set = set()
        per_tag = max(3, max_results // max(len(hashtags), 1))
        region_code = self.REGION_CODES.get(region.upper(), "US")

        for hashtag in hashtags:
            if len(all_items) >= max_results:
                break
            try:
                resp = requests.get(
                    "https://tiktok-scraper7.p.rapidapi.com/feed/search",
                    headers={
                        "x-rapidapi-key": self.rapidapi_key,
                        "x-rapidapi-host": "tiktok-scraper7.p.rapidapi.com",
                    },
                    params={
                        "keywords": hashtag,
                        "region": region_code,
                        "count": per_tag * 3,
                        "cursor": 0,
                        "publish_time": 0,
                        "sort_type": 0,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                videos = data.get("data", {}).get("videos", [])
                for v in videos:
                    vid_id = v.get("video_id", "")
                    if vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)
                    item = self._parse_rapidapi_item(v, hashtag)
                    if item:
                        all_items.append(item)
                        if len(all_items) >= max_results:
                            break
            except Exception as e:
                print(f"[TRENDS] TikTok RapidAPI error for #{hashtag}: {e}")
                continue

        all_items.sort(key=lambda t: t.velocity_score, reverse=True)
        print(f"[TRENDS] TikTok RapidAPI: fetched {len(all_items)} videos")
        return all_items[:max_results]

    def _parse_rapidapi_item(self, v: dict, matched_keyword: str = None) -> "TrendItem | None":
        title = v.get("title", "").strip()
        if not title:
            return None

        plays = int(v.get("play", 0) or 0)
        likes = int(v.get("digg", 0) or 0)
        author = v.get("author", {}) or {}
        followers = int(author.get("follower_count", 0) or 0)
        create_time = v.get("create_time", 0)

        published_at = None
        hours_since = 24
        if create_time:
            published_at = datetime.fromtimestamp(int(create_time), tz=timezone.utc)
            hours_since = max(1, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)

        velocity = plays / hours_since
        viral_coef = round(plays / followers, 1) if followers > 0 else None
        is_anomaly = viral_coef > 10 if viral_coef else False

        unique_id = author.get("unique_id", "")
        vid_id = v.get("video_id", "")
        url = f"https://www.tiktok.com/@{unique_id}/video/{vid_id}" if unique_id and vid_id else ""
        if not url:
            return None

        thumbnail = v.get("cover", "") or v.get("origin_cover", "")
        hashtags = [tag.strip("#") for tag in title.split() if tag.startswith("#")]

        return TrendItem(
            title=title[:200],
            description=f"TikTok | {self._fmt(plays)} plays, {self._fmt(likes)} likes",
            source=self.source_name,
            category="tiktok_trending",
            score=plays / 1000,
            velocity_score=velocity,
            published_at=published_at,
            view_count=plays,
            thumbnail_url=thumbnail or None,
            keywords=hashtags[:10],
            url=url,
            content_type=self._classify(title, hashtags),
            subscriber_count=followers or None,
            viral_coef=viral_coef,
            is_anomaly=is_anomaly,
            matched_keyword=matched_keyword,
        )

    def _fetch_apify(self, hashtags: List[str], region: str, max_results: int) -> List[TrendItem]:
        """Fallback: Apify clockworks~free-tiktok-scraper."""
        try:
            import requests
            actor_url = "https://api.apify.com/v2/acts/clockworks~free-tiktok-scraper/run-sync-get-dataset-items"
            payload = {
                "hashtags": hashtags,
                "resultsPerPage": min(max_results * 2, 50),
                "shouldDownloadVideos": False,
            }
            response = requests.post(actor_url, json=payload,
                                     params={"token": self.apify_token}, timeout=120)
            response.raise_for_status()
            return self._parse_apify_results(response.json(), max_results)
        except Exception as e:
            print(f"[TRENDS] TikTok Apify fallback error: {e}")
            return []

    def _parse_apify_results(self, data: list, max_results: int) -> List[TrendItem]:
        trends = []
        seen_urls = set()
        for item in data[:max_results * 3]:
            title = item.get("text", item.get("desc", ""))
            if not title or len(title) < 5:
                continue
            plays = item.get("playCount", 0) or 0
            likes = item.get("diggCount", 0) or 0
            create_time = item.get("createTime", 0)
            published_at = None
            hours_since = 24
            if isinstance(create_time, (int, float)) and create_time > 0:
                published_at = datetime.fromtimestamp(create_time, tz=timezone.utc)
                hours_since = max(1, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)
            velocity = plays / hours_since
            author_meta = item.get("authorMeta", {}) or {}
            followers = int(author_meta.get("fans", 0) or 0)
            viral_coef = round(plays / followers, 1) if followers > 0 else None
            is_anomaly = viral_coef > 10 if viral_coef else False
            url = item.get("webVideoUrl", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            hashtags = []
            for tag in item.get("hashtags", []):
                if isinstance(tag, dict):
                    hashtags.append(tag.get("name", ""))
                elif isinstance(tag, str):
                    hashtags.append(tag)
            trends.append(TrendItem(
                title=title[:200],
                description=f"TikTok | {self._fmt(plays)} plays, {self._fmt(likes)} likes",
                source=self.source_name,
                category="tiktok_trending",
                score=plays / 1000,
                velocity_score=velocity,
                published_at=published_at,
                view_count=plays,
                keywords=hashtags[:10],
                url=url,
                content_type=self._classify(title, hashtags),
                subscriber_count=followers or None,
                viral_coef=viral_coef,
                is_anomaly=is_anomaly,
            ))
            if len(trends) >= max_results:
                break
        trends.sort(key=lambda t: t.velocity_score, reverse=True)
        print(f"[TRENDS] TikTok Apify: fetched {len(trends)} videos")
        return trends

    @staticmethod
    def _classify(title: str, hashtags: list) -> str:
        text = f"{title} {' '.join(hashtags)}".lower()
        if any(k in text for k in ["ai", "нейросеть", "ki generi", "ia gerad", "ai生成"]):
            return "ai_generated"
        if any(k in text for k in ["animation", "animated", "cartoon", "анимация", "アニメ"]):
            return "animation"
        if any(k in text for k in ["story", "microdrama", "pov", "drama", "история", "микродрама"]):
            return "story"
        return "other"

    @staticmethod
    def _fmt(n: int) -> str:
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.0f}K"
        return str(n)
