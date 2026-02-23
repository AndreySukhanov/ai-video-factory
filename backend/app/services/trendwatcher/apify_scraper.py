from typing import List
from .base import TrendSource, TrendItem
from app.core.config import settings


class ApifyScraper(TrendSource):
    """Optional: Deep scraping of YouTube Shorts via Apify Actor."""

    REGION_SEARCH = {
        "US": "shorts trending viral",
        "GB": "shorts trending viral UK",
        "RU": "shorts тренды вирусное русский",
        "DE": "shorts trending viral deutsch",
        "JP": "shorts トレンド バイラル",
        "BR": "shorts trending viral brasil",
        "IN": "shorts trending viral india hindi",
    }

    @property
    def source_name(self) -> str:
        return "apify"

    def __init__(self):
        self.api_token = settings.APIFY_API_TOKEN

    def fetch_trends(self, region: str = "US", category: str = "", max_results: int = 20) -> List[TrendItem]:
        """
        Fetch trending Shorts via Apify YouTube scraper.
        Uses the official Apify YouTube Scraper actor.
        """
        if not self.api_token:
            print("[TRENDS] APIFY_API_TOKEN not set, skipping Apify scraper")
            return []

        # Try multiple actors in order of reliability
        trends = self._try_streamers_youtube(region, category, max_results)
        if trends:
            return trends

        trends = self._try_search_scraper(region, category, max_results)
        return trends

    def _try_streamers_youtube(self, region: str, category: str, max_results: int) -> List[TrendItem]:
        """Use streamers/youtube-scraper actor."""
        try:
            import requests

            actor_url = "https://api.apify.com/v2/acts/streamers~youtube-scraper/run-sync-get-dataset-items"
            params = {"token": self.api_token}
            search_query = self.REGION_SEARCH.get(region.upper(), f"shorts trending {region}")
            payload = {
                "searchKeywords": [search_query],
                "maxResults": max_results,
                "maxResultsShorts": max_results,
                "type": "search",
            }

            response = requests.post(actor_url, json=payload, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()

            return self._parse_results(data, category, max_results)

        except Exception as e:
            print(f"[TRENDS] Apify streamers~youtube-scraper error: {e}")
            return []

    def _try_search_scraper(self, region: str, category: str, max_results: int) -> List[TrendItem]:
        """Fallback: use generic web scraper for YouTube search."""
        try:
            import requests

            actor_url = "https://api.apify.com/v2/acts/apify~youtube-scraper/run-sync-get-dataset-items"
            params = {"token": self.api_token}
            search_query = self.REGION_SEARCH.get(region.upper(), f"trending shorts {region}")
            payload = {
                "searchKeywords": [search_query],
                "maxResults": max_results,
            }

            response = requests.post(actor_url, json=payload, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()

            return self._parse_results(data, category, max_results)

        except Exception as e:
            print(f"[TRENDS] Apify apify~youtube-scraper error: {e}")
            return []

    def _parse_results(self, data: list, category: str, max_results: int) -> List[TrendItem]:
        """Parse Apify scraper results into TrendItems."""
        trends = []
        for item in data[:max_results * 2]:
            duration = item.get("duration", 0)
            if isinstance(duration, str):
                parts = duration.split(":")
                try:
                    duration = sum(int(p) * (60 ** i) for i, p in enumerate(reversed(parts)))
                except (ValueError, TypeError):
                    duration = 0

            if duration > 60:
                continue

            title = item.get("title", "")
            if not title:
                continue

            trends.append(TrendItem(
                title=title,
                description=item.get("description", "")[:500],
                source=self.source_name,
                category=category or "shorts",
                score=item.get("viewCount", item.get("views", 0)) / 1000 if item.get("viewCount", item.get("views", 0)) else 0,
                keywords=item.get("tags", [])[:10] if item.get("tags") else [],
                url=item.get("url", item.get("link", "")),
            ))

            if len(trends) >= max_results:
                break

        print(f"[TRENDS] Apify: fetched {len(trends)} shorts")
        return trends
