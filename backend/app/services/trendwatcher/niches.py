"""Niche registry for trend-discovery.

Each niche has:
  - display_name (per locale)
  - hashtags (per locale) — for TikTok/Instagram hashtag search
  - youtube_queries (per locale) — for YouTube Data API search

Adding a new niche: append a dict to NICHES. Frontend picks it up automatically via
the `/api/v1/trends/niches` endpoint.

Localization scheme:
  - "en" — used for US, GB, AU, CA, IN
  - "ru" — used for RU
  - Other regions fall back to "en"
"""
from typing import Optional


NICHES: dict[str, dict] = {
    "astrology": {
        "display_name": {
            "en": "Astrology & Tarot",
            "ru": "Астрология и таро",
        },
        "hashtags": {
            "en": [
                "astrology", "tarot", "zodiac", "horoscope",
                "tarotreading", "zodiacsigns", "mercuryretrograde",
                "astrologer", "palmreading", "manifestation",
                "witchtok", "spirituality", "esoteric",
                "fortunetelling", "psychic", "oracle",
                "numerology", "runes",
            ],
            "ru": [
                "астрология", "таро", "гороскоп", "зодиак",
                "эзотерика", "астролог", "тарорасклад", "картытаро",
                "гадание", "магия", "экстрасенс", "медиум",
                "рунолог", "нумерология", "рейки",
                "меркурийретроград", "знакизодиака", "ретроградныймеркурий",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts astrology reading",
                "#shorts tarot card reading",
                "#shorts zodiac sign reveal",
                "#shorts horoscope today",
                "#shorts mercury retrograde",
                "#shorts witchtok spell",
            ],
            "ru": [
                "#shorts астрология",
                "#shorts таро онлайн",
                "#shorts гороскоп сегодня",
                "#shorts знаки зодиака",
                "#shorts эзотерика",
                "#shorts ретроградный меркурий",
            ],
        },
    },

    "relationships": {
        "display_name": {
            "en": "Relationships & Dating",
            "ru": "Отношения и психология",
        },
        "hashtags": {
            "en": [
                "relationshiptips", "datingadvice", "redflags",
                "couplegoals", "breakup", "exboyfriend", "exgirlfriend",
                "toxicrelationship", "narcissist", "ghosting",
                "loveadvice", "marriageadvice", "psychology",
            ],
            "ru": [
                "отношения", "психологияотношений", "редфлаги",
                "разрыв", "бывший", "бывшая",
                "токсичныеотношения", "нарцисс", "психологлайф",
                "советылюбви", "браксоветы", "психология",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts relationship red flags",
                "#shorts dating advice",
                "#shorts toxic relationship signs",
                "#shorts narcissist behavior",
            ],
            "ru": [
                "#shorts отношения советы",
                "#shorts красные флаги",
                "#shorts токсичные отношения",
                "#shorts психология отношений",
            ],
        },
    },

    "motivation": {
        "display_name": {
            "en": "Motivation & Mindset",
            "ru": "Мотивация и саморазвитие",
        },
        "hashtags": {
            "en": [
                "motivation", "mindset", "successmindset", "selfdevelopment",
                "discipline", "hardwork", "entrepreneur", "hustle",
                "personalgrowth", "gratitude", "mindsetshift",
            ],
            "ru": [
                "мотивация", "саморазвитие", "успех", "цели",
                "дисциплина", "предприниматель", "ростличности",
                "осознанность", "благодарность",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts motivation discipline",
                "#shorts mindset shift",
                "#shorts success habits",
                "#shorts entrepreneur tips",
            ],
            "ru": [
                "#shorts мотивация",
                "#shorts саморазвитие",
                "#shorts успешные привычки",
                "#shorts дисциплина",
            ],
        },
    },
}


REGION_LANG_MAP = {
    "US": "en", "GB": "en", "AU": "en", "CA": "en", "IN": "en",
    "RU": "ru",
}


def resolve_lang(region: str) -> str:
    """Pick locale key for a given region. Falls back to 'en'."""
    return REGION_LANG_MAP.get((region or "").upper(), "en")


def get_niche(niche_id: str) -> Optional[dict]:
    return NICHES.get(niche_id)


def get_hashtags(niche_id: str, region: str) -> list[str]:
    """Get TikTok/Instagram hashtags for a niche+region. Empty list if not found."""
    niche = NICHES.get(niche_id)
    if not niche:
        return []
    lang = resolve_lang(region)
    return niche["hashtags"].get(lang, niche["hashtags"].get("en", []))


def get_youtube_queries(niche_id: str, region: str) -> list[str]:
    """Get YouTube search queries for a niche+region. Empty list if not found."""
    niche = NICHES.get(niche_id)
    if not niche:
        return []
    lang = resolve_lang(region)
    return niche["youtube_queries"].get(lang, niche["youtube_queries"].get("en", []))


def list_niches(lang: str = "en") -> list[dict]:
    """Return list of available niches with localized display names."""
    out = []
    for niche_id, data in NICHES.items():
        out.append({
            "id": niche_id,
            "display_name": data["display_name"].get(lang, data["display_name"].get("en", niche_id)),
            "hashtag_count": len(data["hashtags"].get(lang, [])),
        })
    return out
