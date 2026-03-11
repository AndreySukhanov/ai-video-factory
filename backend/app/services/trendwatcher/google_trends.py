import re
import xml.etree.ElementTree as ET
from typing import List
from datetime import datetime
from .base import TrendSource, TrendItem
from urllib.parse import quote_plus


class GoogleTrendsSource(TrendSource):
    """Fetch trending searches via Google Trends RSS feed (reliable, no API key)."""

    RSS_URL = "https://trends.google.com/trending/rss?geo={geo}"

    REGION_HL = {
        "US": "en-US", "GB": "en-GB", "AU": "en-AU", "CA": "en-CA",
        "RU": "ru-RU", "DE": "de-DE", "FR": "fr-FR", "ES": "es-ES",
        "JP": "ja-JP", "KR": "ko-KR", "BR": "pt-BR", "IN": "hi-IN",
        "IT": "it-IT", "NL": "nl-NL", "PL": "pl-PL", "TR": "tr-TR",
    }

    REGION_SEED_KEYWORDS = {
        "US": ["AI video", "AI art", "animated story", "cute animal story", "neural network"],
        "RU": ["нейросеть видео", "ИИ арт", "анимация история", "милые животные", "нейросетьзахватитмир"],
        "DE": ["KI video", "KI kunst", "animation geschichte", "süße tiere"],
        "JP": ["AI動画", "AI生成", "アニメストーリー", "かわいい動物"],
        "BR": ["IA vídeo", "IA arte", "animação história", "animais fofos"],
        "IN": ["AI video", "AI art", "animated story", "cute animal story"],
    }

    DEFAULT_SEED_KEYWORDS = ["AI video", "AI art", "animated story", "cute animal story", "neural network"]

    # Topics suitable for AI video generation (keep these)
    AI_FRIENDLY_KEYWORDS = [
        # AI / tech
        "ai", "artificial intelligence", "chatgpt", "openai", "midjourney", "sora",
        "neural network", "deep learning", "robot", "deepfake",
        "нейросеть", "ии", "искусственный интеллект", "робот",
        # Entertainment / storytelling
        "movie", "film", "animation", "anime", "cartoon", "pixar", "disney",
        "horror", "sci-fi", "fantasy", "superhero", "marvel", "dc",
        "фильм", "кино", "мультфильм", "анимация", "аниме", "ужасы", "фантастика",
        # Animals (cute stories)
        "dog", "puppy", "cat", "kitten", "animal", "pet", "cute",
        "собака", "щенок", "кот", "котёнок", "животное", "милый",
        # Emotional / story topics
        "story", "mystery", "legend", "myth", "fairytale", "miracle",
        "история", "легенда", "миф", "сказка", "чудо", "тайна",
        # Science / nature (visualizable)
        "space", "ocean", "dinosaur", "volcano", "earthquake", "tornado",
        "cosmos", "planet", "black hole", "universe",
        "космос", "океан", "динозавр", "вулкан", "планета", "вселенная",
        # Viral visual content
        "optical illusion", "satisfying", "transformation", "before after",
        "what if", "did you know", "amazing facts",
    ]

    # Topics NOT suitable for AI video (reject these)
    NON_AI_KEYWORDS = [
        # Sports
        "nfl", "nba", "nhl", "mlb", "premier league", "champions league",
        "la liga", "bundesliga", "serie a", "ligue 1", "ucl",
        "football", "basketball", "baseball", "hockey", "soccer", "cricket",
        "tennis", "golf", "boxing", "ufc", "mma", "wrestling", "wwe",
        "playoff", "tournament", "championship", "draft", "trade",
        "super bowl", "world cup", "olympics",
        "лч", "лига чемпионов", "рпл", "кхл", "футбол", "баскетбол",
        "хоккей", "бокс", "борьба", "чемпионат",
        # Sports people patterns
        "quarterback", "touchdown", "goal scorer", "transfer",
        # Politics / news
        "election", "senate", "congress", "governor", "mayor",
        "trump", "biden", "выборы", "сенат", "депутат",
        # Stock market / finance
        "stock", "nasdaq", "dow jones", "s&p 500", "crypto",
        "bitcoin", "earnings", "ipo", "акции", "биржа",
        # Weather / mundane
        "weather forecast", "road closure", "traffic",
        "погода", "пробки",
        # Specific sports entities
        "lakers", "celtics", "warriors", "cowboys", "eagles", "chiefs",
        "yankees", "dodgers", "49ers", "packers", "bills", "ravens",
        "mbappe", "mbappé", "реал мадрид", "real madrid", "psg",
        "chelsea", "manchester", "barcelona", "juventus",
        "winline", "винлайн", "fonbet", "фонбет", "okko",
        "fotmob",
    ]

    @property
    def source_name(self) -> str:
        return "google_trends"

    @staticmethod
    def _keyword_in_text(text: str, keyword: str) -> bool:
        """Check if keyword appears as a whole word/phrase in text (not as substring)."""
        if keyword.startswith('#'):
            return keyword in text
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))

    def _is_ai_friendly(self, title: str, description: str = "") -> bool:
        """Check if a Google Trend topic is suitable for AI video creation."""
        text = f"{title} {description}".lower()

        # Reject if clearly non-AI content (sports, politics, finance)
        if any(self._keyword_in_text(text, kw) for kw in self.NON_AI_KEYWORDS):
            return False

        # Accept if has AI-friendly keywords
        if any(self._keyword_in_text(text, kw) for kw in self.AI_FRIENDLY_KEYWORDS):
            return True

        # For remaining: accept only if the topic sounds like it could be
        # a story, visual concept, or entertainment — not dry news
        # Heuristic: short titles (1-2 words) are usually person names or teams = reject
        words = title.strip().split()
        if len(words) <= 2:
            return False

        return False

    def fetch_trends(self, region: str = "US", category: str = "", max_results: int = 20) -> List[TrendItem]:
        """
        Fetch trending searches from Google Trends.
        Primary: RSS feed (reliable, always works).
        Fallback: pytrends (can be blocked by Google).
        """
        # Primary: RSS feed — reliable, no rate limits
        trends = self._try_rss_feed(region, category, max_results)
        if trends:
            return trends

        # Fallback 1: pytrends trending_searches
        trends = self._try_trending_searches(region, category, max_results)
        if trends:
            return trends

        # Fallback 2: pytrends related queries
        return self._try_popular_keywords(region, category, max_results)

    def _try_rss_feed(self, region: str, category: str, max_results: int) -> List[TrendItem]:
        """Primary method: parse Google Trends RSS feed."""
        try:
            import requests

            geo = region.upper() if len(region) == 2 else "US"
            url = self.RSS_URL.format(geo=geo)
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (compatible; TrendBot/1.0)"
            })
            resp.raise_for_status()

            # Parse XML
            ns = {"ht": "https://trends.google.com/trending/rss"}
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")

            trends = []
            skipped = 0
            for idx, item in enumerate(items):
                if len(trends) >= max_results:
                    break

                title = item.findtext("title", "").strip()
                if not title:
                    continue

                # Extract news snippet for description
                news_title = item.findtext(".//ht:news_item_title", "", ns)
                description = news_title if news_title else f"Trending: {title}"

                # Filter: only AI-friendly topics
                if not self._is_ai_friendly(title, description):
                    skipped += 1
                    continue

                # Extract traffic estimate
                traffic_text = item.findtext("ht:approx_traffic", "0", ns)
                traffic = self._parse_traffic(traffic_text)

                # Extract image
                picture = item.findtext("ht:picture", "", ns)

                # Parse pubDate for velocity estimate
                pub_date_str = item.findtext("pubDate", "")
                hours_age = self._hours_since(pub_date_str)
                velocity = traffic / max(1, hours_age)

                trends.append(TrendItem(
                    title=title,
                    description=description[:500],
                    source=self.source_name,
                    category=category or "daily_trends",
                    score=traffic / 1000 if traffic > 0 else max_results - idx,
                    velocity_score=velocity,
                    keywords=[title] + title.lower().split()[:4],
                    url=f"https://trends.google.com/trends/explore?q={quote_plus(title)}&geo={geo}",
                ))

            print(f"[TRENDS] Google Trends (RSS): fetched {len(trends)} from {region} (skipped {skipped} non-AI)")
            return trends

        except Exception as e:
            print(f"[TRENDS] Google Trends RSS failed: {e}")
            return []

    def _try_trending_searches(self, region: str, category: str, max_results: int) -> List[TrendItem]:
        try:
            from pytrends.request import TrendReq
            hl = self.REGION_HL.get(region.upper(), "en-US")
            pytrends = TrendReq(hl=hl, tz=360, timeout=(10, 25))
            trending = pytrends.trending_searches(pn=self._map_region(region))
            trends = []
            for idx, row in trending.head(max_results * 3).iterrows():
                if len(trends) >= max_results:
                    break
                keyword = row[0]
                if not self._is_ai_friendly(keyword):
                    continue
                trends.append(TrendItem(
                    title=keyword,
                    description=f"Trending search: {keyword}",
                    source=self.source_name,
                    category=category or "general",
                    score=max_results - len(trends),
                    keywords=[keyword],
                    url=f"https://trends.google.com/trends/explore?q={quote_plus(keyword)}",
                ))
            print(f"[TRENDS] Google Trends (trending_searches): fetched {len(trends)} from {region}")
            return trends
        except Exception as e:
            print(f"[TRENDS] Google Trends trending_searches failed: {e}")
            return []

    def _try_popular_keywords(self, region: str, category: str, max_results: int) -> List[TrendItem]:
        """Fallback: search for popular entertainment keywords with Breakout detection."""
        try:
            from pytrends.request import TrendReq
            hl = self.REGION_HL.get(region.upper(), "en-US")
            pytrends = TrendReq(hl=hl, tz=360, timeout=(10, 25))

            seed_keywords = self.REGION_SEED_KEYWORDS.get(region.upper(), self.DEFAULT_SEED_KEYWORDS)
            pytrends.build_payload(seed_keywords[:5], timeframe="now 1-d", geo=region.upper())
            related = pytrends.related_queries()

            trends = []
            for kw, data in related.items():
                if data and data.get("rising") is not None:
                    rising_df = data["rising"]
                    for idx, row in rising_df.head(max_results // 3).iterrows():
                        query = row.get("query", "")
                        if not query:
                            continue

                        value = row.get("value", 0)
                        is_breakout = (
                            (isinstance(value, str) and "Breakout" in str(value)) or
                            (isinstance(value, (int, float)) and value >= 5000)
                        )

                        if not self._is_ai_friendly(query):
                            continue

                        cat = "breakout" if is_breakout else (category or "related")
                        base_score = 10000 if is_breakout else (float(value) if isinstance(value, (int, float)) else 0)
                        velocity = 1000 if is_breakout else base_score / 10

                        trends.append(TrendItem(
                            title=query,
                            description=f"{'BREAKOUT' if is_breakout else 'Rising'} query related to: {kw}",
                            source=self.source_name,
                            category=cat,
                            score=base_score,
                            velocity_score=velocity,
                            keywords=[query, kw],
                            url=f"https://trends.google.com/trends/explore?q={quote_plus(query)}",
                        ))

            trends.sort(key=lambda t: (t.category == "breakout", t.score), reverse=True)
            print(f"[TRENDS] Google Trends (related): fetched {len(trends)} "
                  f"({sum(1 for t in trends if t.category == 'breakout')} breakouts) from {region}")
            return trends[:max_results]
        except Exception as e:
            print(f"[TRENDS] Google Trends related failed: {e}")
            return []

    @staticmethod
    def _parse_traffic(text: str) -> float:
        """Parse traffic string like '100,000+' or '10K+' to number."""
        if not text:
            return 0
        text = text.strip().replace("+", "").replace(",", "")
        try:
            if "K" in text.upper():
                return float(text.upper().replace("K", "")) * 1000
            elif "M" in text.upper():
                return float(text.upper().replace("M", "")) * 1_000_000
            return float(text)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _hours_since(pub_date_str: str) -> float:
        """Calculate hours since pubDate string."""
        if not pub_date_str:
            return 24
        try:
            from email.utils import parsedate_to_datetime
            pub_dt = parsedate_to_datetime(pub_date_str)
            from datetime import timezone
            delta = datetime.now(timezone.utc) - pub_dt
            return max(1, delta.total_seconds() / 3600)
        except Exception:
            return 24

    @staticmethod
    def _map_region(region: str) -> str:
        """Map ISO country code to pytrends region name."""
        mapping = {
            "US": "united_states",
            "GB": "united_kingdom",
            "RU": "russia",
            "DE": "germany",
            "FR": "france",
            "JP": "japan",
            "BR": "brazil",
            "IN": "india",
        }
        return mapping.get(region.upper(), "united_states")
