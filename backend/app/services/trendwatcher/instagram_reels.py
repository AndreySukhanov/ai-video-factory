from typing import List, Optional, Set
from datetime import datetime, timezone
import re
from .base import TrendSource, TrendItem
from app.core.config import settings


class InstagramReelsTrendWatcher(TrendSource):
    """
    Fetch trending Instagram Reels by hashtag.
    Primary: RapidAPI instagram-scraper-api2 (free tier, no account needed).
    Fallback: Apify apify~instagram-scraper.
    """

    REGION_HASHTAGS = {
        "US": ["microdrama", "aivideo", "shortfilm", "viralvideo", "aiart"],
        "GB": ["microdrama", "aivideo", "shortfilm", "viralvideo", "aiart"],
        "RU": ["микродрама", "нейросеть", "аивидео", "aiарт"],
        "DE": ["microdrama", "kigeneration", "kurzfilm", "viralvideo"],
        "JP": ["マイクロドラマ", "AI動画", "ショートフィルム"],
        "BR": ["microdrama", "iavideo", "filmecurto", "viralvideo"],
        "IN": ["microdrama", "aivideo", "shortfilm", "reels"],
    }

    @property
    def source_name(self) -> str:
        return "instagram"

    def __init__(self):
        self.rapidapi_key = settings.RAPIDAPI_KEY
        self.apify_token = settings.APIFY_API_TOKEN

    def fetch_trends(self, region: str = "US", category: str = "", max_results: int = 20,
                     keywords: List[str] = None) -> List[TrendItem]:
        if keywords:
            hashtags = keywords
        else:
            config_hashtags = getattr(settings, "INSTAGRAM_HASHTAGS", None)
            hashtags = config_hashtags if config_hashtags else self.REGION_HASHTAGS.get(region.upper(), self.REGION_HASHTAGS["US"])

        if self.rapidapi_key:
            trends = self._fetch_rapidapi(hashtags, max_results)
            if trends:
                return trends
            print("[TRENDS] Instagram RapidAPI returned empty, trying Apify fallback")

        if self.apify_token:
            return self._fetch_apify(hashtags, max_results)

        print("[TRENDS] No Instagram API configured (set RAPIDAPI_KEY or APIFY_API_TOKEN)")
        return []

    # ── RapidAPI ──────────────────────────────────────────────────────────────

    def _fetch_rapidapi(self, hashtags: List[str], max_results: int) -> List[TrendItem]:
        """Fetch via RapidAPI instagram-scraper-api2 — free tier available."""
        import requests

        all_trends: List[TrendItem] = []
        seen_urls: Set[str] = set()
        per_tag = max(3, max_results // max(len(hashtags), 1))

        for hashtag in hashtags:
            if len(all_trends) >= max_results:
                break
            try:
                resp = requests.get(
                    "https://instagram-scraper-api2.p.rapidapi.com/v1/hashtag",
                    headers={
                        "x-rapidapi-key": self.rapidapi_key,
                        "x-rapidapi-host": "instagram-scraper-api2.p.rapidapi.com",
                    },
                    params={"hashtag": hashtag},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                medias = (data.get("data", {})
                              .get("data", {})
                              .get("medias", []))
                batch = self._parse_rapidapi_medias(medias, per_tag, seen_urls, hashtag)
                all_trends.extend(batch)
            except Exception as e:
                print(f"[TRENDS] Instagram RapidAPI error for #{hashtag}: {e}")
                continue

        all_trends.sort(key=lambda t: t.velocity_score, reverse=True)
        print(f"[TRENDS] Instagram RapidAPI: fetched {len(all_trends)} posts")
        return all_trends[:max_results]

    def _parse_rapidapi_medias(self, medias: list, max_results: int,
                                seen_urls: Set[str], matched_keyword: str) -> List[TrendItem]:
        trends = []
        for m in medias:
            if len(trends) >= max_results:
                break

            code = m.get("code", m.get("shortcode", ""))
            caption_obj = m.get("caption") or {}
            caption = caption_obj.get("text", "") if isinstance(caption_obj, dict) else str(caption_obj)
            title = next((line.strip() for line in caption.split("\n") if line.strip()), code)
            if not title:
                continue

            url = f"https://www.instagram.com/p/{code}/" if code else m.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            plays = int(m.get("play_count", 0) or m.get("video_view_count", 0) or 0)
            likes = int(m.get("like_count", 0) or 0)
            comments = int(m.get("comment_count", 0) or 0)

            taken_at = m.get("taken_at", 0)
            published_at = None
            hours_since = 24
            if taken_at:
                published_at = datetime.fromtimestamp(int(taken_at), tz=timezone.utc)
                hours_since = max(1, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)

            score = (plays / 1000) if plays else (likes / 100)
            velocity = (plays or likes * 10) / hours_since

            # thumbnail
            candidates = (m.get("image_versions2") or {}).get("candidates", [])
            thumbnail = candidates[0].get("url", "") if candidates else (m.get("display_url", "") or "")

            hashtags = re.findall(r"#(\w+)", caption)[:10]

            # viral_coef
            user = m.get("user", {}) or {}
            followers = int(user.get("follower_count", 0) or 0)
            viral_coef = round(plays / followers, 1) if plays and followers > 0 else None
            is_anomaly = viral_coef > 10 if viral_coef else False

            trends.append(TrendItem(
                title=title[:200],
                description=f"Instagram | {self._fmt(plays)} views, {self._fmt(likes)} likes",
                source=self.source_name,
                category="instagram_reels",
                score=score,
                velocity_score=velocity,
                published_at=published_at,
                view_count=int(plays) if plays else None,
                thumbnail_url=thumbnail or None,
                keywords=hashtags,
                url=url,
                content_type="reel",
                subscriber_count=followers or None,
                viral_coef=viral_coef,
                is_anomaly=is_anomaly,
                matched_keyword=matched_keyword,
            ))
        return trends

    # ── Apify fallback ────────────────────────────────────────────────────────

    def _fetch_apify(self, hashtags: List[str], max_results: int) -> List[TrendItem]:
        """Fallback: Apify apify~instagram-scraper."""
        import requests

        all_trends: List[TrendItem] = []
        seen_urls: Set[str] = set()
        per_tag = max(3, max_results // max(len(hashtags), 1))
        actor_url = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"
        params = {"token": self.apify_token}

        for hashtag in hashtags:
            if len(all_trends) >= max_results:
                break
            try:
                payload = {
                    "directUrls": [f"https://www.instagram.com/explore/tags/{hashtag}/"],
                    "resultsType": "posts",
                    "resultsLimit": per_tag * 3,
                    "addParentData": False,
                }
                resp = requests.post(actor_url, json=payload, params=params, timeout=180)
                resp.raise_for_status()
                batch = self._parse_apify_results(resp.json(), per_tag, seen_urls, hashtag)
                all_trends.extend(batch)
            except Exception as e:
                print(f"[TRENDS] Instagram Apify error for #{hashtag}: {e}")
                continue

        all_trends.sort(key=lambda t: t.velocity_score, reverse=True)
        print(f"[TRENDS] Instagram Apify: fetched {len(all_trends)} posts")
        return all_trends[:max_results]

    def _parse_apify_results(self, data: list, max_results: int,
                              seen_urls: Set[str], matched_keyword: str) -> List[TrendItem]:
        trends = []
        for item in data[:max_results * 3]:
            caption = item.get("caption", item.get("alt", "")) or ""
            short_code = item.get("shortCode", item.get("shortcode", ""))
            title = next((line.strip() for line in caption.split("\n") if line.strip()), short_code)
            if not title:
                continue

            url = item.get("url", "")
            if not url and short_code:
                url = f"https://www.instagram.com/p/{short_code}/"
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            views = item.get("videoViewCount") or item.get("videoPlayCount") or 0
            likes = max(0, item.get("likesCount", 0) or 0)
            timestamp = item.get("timestamp", "")
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

            score = (views / 1000) if views else (likes / 100)
            velocity = (views or likes * 10) / hours_since
            thumbnail = item.get("displayUrl", item.get("thumbnailUrl", "")) or None
            hashtags = re.findall(r"#(\w+)", caption)[:10]

            trends.append(TrendItem(
                title=title[:200],
                description=f"Instagram | {self._fmt(views)} views, {self._fmt(likes)} likes",
                source=self.source_name,
                category="instagram_reels",
                score=score,
                velocity_score=velocity,
                published_at=published_at,
                view_count=int(views) if views else None,
                thumbnail_url=thumbnail,
                keywords=hashtags,
                url=url,
                content_type="reel",
                matched_keyword=matched_keyword,
            ))
            if len(trends) >= max_results:
                break
        return trends

    @staticmethod
    def _fmt(n) -> str:
        if not n:
            return "0"
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.0f}K"
        return str(n)
