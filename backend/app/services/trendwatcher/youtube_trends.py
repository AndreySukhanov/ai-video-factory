import re
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

    # Unicode script ranges for language filtering
    LANG_SCRIPTS = {
        "ru": re.compile(r'[\u0400-\u04FF]'),   # Cyrillic
        "en": re.compile(r'[a-zA-Z]'),           # Latin
        "de": re.compile(r'[a-zA-ZäöüßÄÖÜ]'),   # Latin + German
        "fr": re.compile(r'[a-zA-ZàâéèêëïîôùûüÿçœæÀÂÉÈÊËÏÎÔÙÛÜŸÇŒÆ]'),
        "es": re.compile(r'[a-zA-ZñáéíóúüÑÁÉÍÓÚÜ¿¡]'),
        "pt": re.compile(r'[a-zA-ZãõáéíóúâêôàçÃÕÁÉÍÓÚÂÊÔÀÇ]'),
        "ja": re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'),  # Hiragana+Katakana+Kanji
        "ko": re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF]'),  # Hangul
        "hi": re.compile(r'[\u0900-\u097F]'),    # Devanagari
        "tr": re.compile(r'[a-zA-ZçğıöşüÇĞİÖŞÜ]'),
        "it": re.compile(r'[a-zA-ZàèéìíîòóùúÀÈÉÌÍÎÒÓÙÚ]'),
        "pl": re.compile(r'[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]'),
        "nl": re.compile(r'[a-zA-Z]'),
    }

    # Non-Latin/non-target scripts to reject when they dominate the title
    _INDIC_SCRIPTS = re.compile(
        r'[\u0900-\u097F'    # Devanagari (Hindi)
        r'\u0980-\u09FF'     # Bengali
        r'\u0A00-\u0A7F'     # Gurmukhi (Punjabi)
        r'\u0A80-\u0AFF'     # Gujarati
        r'\u0B00-\u0B7F'     # Oriya/Odia
        r'\u0B80-\u0BFF'     # Tamil
        r'\u0C00-\u0C7F'     # Telugu
        r'\u0C80-\u0CFF'     # Kannada
        r'\u0D00-\u0D7F]'    # Malayalam
    )
    _ARABIC_SCRIPT = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')
    _CJK_SCRIPT = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
    _HANGUL_SCRIPT = re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF]')
    _THAI_SCRIPT = re.compile(r'[\u0E00-\u0E7F]')
    _CYRILLIC_SCRIPT = re.compile(r'[\u0400-\u04FF]')

    # Scripts that should NOT dominate for a given language
    FOREIGN_SCRIPTS = {
        "ru": [_INDIC_SCRIPTS, _ARABIC_SCRIPT, _CJK_SCRIPT, _HANGUL_SCRIPT, _THAI_SCRIPT],
        "en": [_INDIC_SCRIPTS, _ARABIC_SCRIPT, _CJK_SCRIPT, _HANGUL_SCRIPT, _THAI_SCRIPT, _CYRILLIC_SCRIPT],
        "de": [_INDIC_SCRIPTS, _ARABIC_SCRIPT, _CJK_SCRIPT, _HANGUL_SCRIPT, _THAI_SCRIPT, _CYRILLIC_SCRIPT],
        "fr": [_INDIC_SCRIPTS, _ARABIC_SCRIPT, _CJK_SCRIPT, _HANGUL_SCRIPT, _THAI_SCRIPT, _CYRILLIC_SCRIPT],
        "es": [_INDIC_SCRIPTS, _ARABIC_SCRIPT, _CJK_SCRIPT, _HANGUL_SCRIPT, _THAI_SCRIPT, _CYRILLIC_SCRIPT],
        "pt": [_INDIC_SCRIPTS, _ARABIC_SCRIPT, _CJK_SCRIPT, _HANGUL_SCRIPT, _THAI_SCRIPT, _CYRILLIC_SCRIPT],
        "ja": [_INDIC_SCRIPTS, _ARABIC_SCRIPT, _HANGUL_SCRIPT, _CYRILLIC_SCRIPT],
        "ko": [_INDIC_SCRIPTS, _ARABIC_SCRIPT, _CJK_SCRIPT, _CYRILLIC_SCRIPT],
        "hi": [_ARABIC_SCRIPT, _CJK_SCRIPT, _HANGUL_SCRIPT, _CYRILLIC_SCRIPT, _THAI_SCRIPT],
    }

    # Search queries targeting AI-generated or AI-reproducible content:
    # cute animal stories, AI art, animations, emotional mini-stories, neural network videos
    REGION_QUERIES = {
        "US": [
            "#shorts AI generated story",
            "#shorts AI animation cute animals",
            "#shorts Sora Kling AI video",
            "#shorts cute puppy kitten AI",
            "#shorts emotional AI short film",
            "#shorts wholesome animation story AI",
        ],
        "GB": [
            "#shorts AI generated story",
            "#shorts AI animation cute",
            "#shorts emotional AI short film",
            "#shorts cute animal animation story",
        ],
        "RU": [
            "#shorts нейросеть видео",
            "#shorts нейросетьзахватитмир",
            "#shorts ИИ генерация видео",
            "#shorts щенок котёнок анимация нейросеть",
            "#shorts трогательная анимация история AI",
            "#shorts AI арт видео нейросеть",
        ],
        "DE": [
            "#shorts KI generiert video",
            "#shorts KI animation süße tiere",
            "#shorts neuronales netz kunst",
            "#shorts KI kurzfilm emotionale geschichte",
        ],
        "JP": [
            "#shorts AI生成 動画",
            "#shorts AI アニメーション かわいい",
            "#shorts ニューラルネットワーク アート",
            "#shorts AI ショートフィルム 感動",
        ],
        "BR": [
            "#shorts IA gerada vídeo",
            "#shorts animação IA fofa animais",
            "#shorts rede neural arte vídeo",
            "#shorts história emocional IA curta",
        ],
        "IN": [
            "#shorts AI generated cute animal story",
            "#shorts neural network animation hindi",
            "#shorts AI video emotional story",
            "#shorts Sora Kling AI generated india",
        ],
    }

    # Fallback queries for unlisted regions
    DEFAULT_QUERIES = [
        "#shorts AI generated story",
        "#shorts AI animation cute animals",
        "#shorts emotional AI short film",
        "#shorts Sora Kling midjourney video",
    ]

    # Keywords indicating content is AI-generated or easily AI-reproducible
    AI_REPRODUCIBLE_KEYWORDS = [
        # Direct AI markers
        "ai generated", "ai art", "ai video", "ai animation", "ai creates",
        "made with ai", "created by ai", "ai powered", "ai made",
        "sora", "runway", "pika", "kling", "midjourney", "stable diffusion",
        "veo", "dall-e", "leonardo ai", "luma", "minimax", "hailuo",
        "neural network", "deep learning", "generative",
        # Russian AI markers
        "нейросеть", "нейросетьзахватитмир", "ии генерация", "ии видео",
        "сгенерировано ии", "создано нейросетью", "ии арт", "нейронная сеть",
        # Animation / easily reproducible with AI
        "animation story", "animated story", "cute animation",
        "3d animation", "cartoon story", "pixar style", "ghibli style",
        "анимация история", "мультик", "мультфильм",
        # Cute animal stories (prime AI content)
        "cute puppy", "cute kitten", "puppy saved", "kitten rescued",
        "baby animal", "cute dog", "cute cat", "animal rescue story",
        "щенок", "котёнок", "милый", "спас",
        # Emotional mini-stories (AI-friendly format)
        "emotional story", "heartwarming", "wholesome", "touching story",
        "трогательная история", "добрый", "история любви",
        # Micro-drama / short film
        "microdrama", "micro drama", "short film", "mini movie",
        "микродрама", "короткометражка",
        # Did-you-know / fact animation
        "did you know", "amazing facts", "unbelievable",
        "#aiart", "#aivideo", "#aigeneratedvideo", "#neuralnetwork",
    ]

    # Keywords indicating NOT AI-reproducible (real footage, sports, news, etc.)
    NON_AI_KEYWORDS = [
        "gameplay", "gaming", "fortnite", "minecraft", "roblox gameplay",
        "nfl", "nba", "football highlights", "soccer highlights", "cricket",
        "ipl", "wwe", "mma", "ufc", "boxing",
        "mukbang", "asmr eating", "cooking recipe", "workout",
        "unboxing", "haul", "vlog", "daily vlog",
        "bollywood", "salman khan", "shah rukh", "tiktok dance",
        "reaction video", "prank in public",
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
        channel_id_map: dict = {}  # video_url -> channelId for batch subscriber lookup
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

                    # Filter out wrong-language videos
                    if not self._matches_language(snippet.get("title", ""), lang):
                        continue

                    # Filter: only AI-generated or AI-reproducible content
                    title_text = snippet.get("title", "")
                    desc_text = snippet.get("description", "")[:500]
                    tag_list = snippet.get("tags", [])[:10] if snippet.get("tags") else []
                    if not self._is_ai_reproducible(title_text, desc_text, tag_list):
                        continue

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

                    trend_item = TrendItem(
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
                    )
                    trends.append(trend_item)

                    # Track channelId for batch subscriber lookup
                    channel_id = snippet.get("channelId", "")
                    if channel_id:
                        channel_id_map[video_url] = channel_id

            except Exception as e:
                print(f"[TRENDS] YouTube search '{query}' error: {e}")
                continue

        # Batch-fetch subscriber counts and compute viral_coef
        if channel_id_map:
            unique_channel_ids = list(set(channel_id_map.values()))
            sub_counts = self._fetch_subscriber_counts(service, unique_channel_ids)
            for trend_item in trends:
                ch_id = channel_id_map.get(trend_item.url)
                if ch_id and ch_id in sub_counts:
                    subs = sub_counts[ch_id]
                    trend_item.subscriber_count = subs
                    if subs > 0:
                        trend_item.viral_coef = round(trend_item.view_count / subs, 1)
                        trend_item.is_anomaly = trend_item.viral_coef > 10

        return trends

    @staticmethod
    def _fetch_subscriber_counts(service, channel_ids: list) -> dict:
        """Batch-fetch subscriber counts for a list of channel IDs. Costs 1 API unit per 50."""
        result = {}
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i:i + 50]
            try:
                resp = service.channels().list(
                    part="statistics",
                    id=",".join(batch),
                ).execute()
                for ch in resp.get("items", []):
                    ch_id = ch["id"]
                    subs = int(ch.get("statistics", {}).get("subscriberCount", 0))
                    result[ch_id] = subs
            except Exception as e:
                print(f"[TRENDS] YouTube channels.list error: {e}")
        return result

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
    def _keyword_in_text(text: str, keyword: str) -> bool:
        """Check if keyword appears as a whole word/phrase in text (not as substring)."""
        if keyword.startswith('#'):
            return keyword in text
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))

    def _is_ai_reproducible(self, title: str, description: str, tags: list) -> bool:
        """Check if content is AI-generated or easily reproducible with AI."""
        text = f"{title} {description} {' '.join(tags)}".lower()

        # Reject if clearly non-AI content
        if any(self._keyword_in_text(text, kw) for kw in self.NON_AI_KEYWORDS):
            return False

        # Accept if has AI-reproducible markers
        if any(self._keyword_in_text(text, kw) for kw in self.AI_REPRODUCIBLE_KEYWORDS):
            return True

        # Accept if content_type will be classified as AI-friendly
        content_type = self._classify_content_type(title, description, tags)
        if content_type in ("ai_generated", "animation", "story"):
            return True

        return False

    def _matches_language(self, title: str, lang: str) -> bool:
        """Check if title matches expected language by script analysis."""
        if not title or lang not in self.LANG_SCRIPTS:
            return True  # No filter if unknown

        # Strip emojis and special chars for cleaner analysis
        clean = re.sub(r'[#@\d\s.,!?(){}[\]"\'…—–\-:;/\\|_~*+=%&^$<>]', '', title)
        if not clean:
            return True

        # Count characters matching expected script
        expected = self.LANG_SCRIPTS[lang]
        expected_chars = len(expected.findall(clean))

        # Check for foreign scripts — reject if ANY foreign chars found
        foreign_scripts = self.FOREIGN_SCRIPTS.get(lang, [])
        foreign_chars = sum(len(fs.findall(clean)) for fs in foreign_scripts)

        # Strict: reject if foreign script has more than 2 chars
        if foreign_chars > 2:
            return False

        # For Latin-based languages (en, de, fr, etc.): require some Latin
        if lang in ("en", "de", "fr", "es", "pt", "it", "nl", "pl", "tr"):
            latin_chars = len(re.findall(r'[a-zA-Z]', clean))
            if latin_chars == 0:
                return False

        # For Cyrillic (RU): require some Cyrillic or Latin
        if lang == "ru" and expected_chars == 0:
            latin = len(re.findall(r'[a-zA-Z]', clean))
            if latin > 0:
                return True  # English title is OK for RU region
            return False

        return True

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
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
