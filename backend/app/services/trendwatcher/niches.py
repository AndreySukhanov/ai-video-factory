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

    # ── Специальная ниша: рекламные ролики астрологических дейтинг-апов ──
    # Главный вирусный паттерн 2026: "Soulmate Sketch" (приложение рисует AI-портрет
    # соулмейта по натальной карте). Топ-апы: Astra, NUiT, Boo, Co-Star, The Pattern.
    # Видео по формуле: скептичная героиня → пробует апп → AI-портрет → шок → CTA скачать.
    "dating_astrology": {
        "display_name": {
            "en": "Astrology Dating Apps (soulmate ads)",
            "ru": "Астро-дейтинг приложения (реклама)",
        },
        "hashtags": {
            "en": [
                "soulmatesketch", "soulmate", "astrologyapp", "astrologydating",
                "birthchart", "birthchartreading", "natalchart",
                "zodiaccompatibility", "zodiacmatch", "twinflame",
                "astraapp", "nuit", "coastar", "thepattern",
                "synastry", "love astrology", "lovecompatibility",
                "manifestlove", "manifestation",
            ],
            "ru": [
                "соулмейт", "соулмейтскетч", "астроприложение",
                "астропортрет", "астропортретсудьбы",
                "натальнаякарта", "совместимостьзнаков",
                "совместимость", "близнецовоепламя",
                "синастрия", "ярусь судьбу", "судьбавтоммаппе",
                "карматическаясвязь", "любовнаясовместимость",
                "знакизодиакалюбовь", "тарорасклад",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts soulmate sketch app",
                "#shorts astrology dating app review",
                "#shorts birth chart soulmate reveal",
                "#shorts AI soulmate portrait app",
                "#shorts astra app soulmate",
                "#shorts zodiac compatibility test",
            ],
            "ru": [
                "#shorts соулмейт приложение",
                "#shorts портрет судьбы по дате рождения",
                "#shorts астро дейтинг",
                "#shorts совместимость знаков расклад",
                "#shorts таро на любовь",
                "#shorts натальная карта совместимость",
            ],
        },
    },

    "cooking": {
        "display_name": {
            "en": "Cooking & Recipes",
            "ru": "Готовка и рецепты",
        },
        "hashtags": {
            "en": [
                "cooking", "recipe", "foodtiktok", "homemade",
                "easyrecipe", "quickrecipe", "viralrecipe", "tasty",
                "mealprep", "dinneridea", "breakfastidea", "dessert",
                "asmrcooking", "chefshacks",
            ],
            "ru": [
                "рецепт", "готовка", "рецепты", "кулинария",
                "вкусно", "простойрецепт", "быстрыйрецепт",
                "завтрак", "обед", "ужин", "десерт",
                "пирог", "торт", "лайфхакикухни",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts viral recipe",
                "#shorts easy dinner recipe",
                "#shorts asmr cooking",
                "#shorts 5 minute meal",
            ],
            "ru": [
                "#shorts рецепт быстро",
                "#shorts простой рецепт",
                "#shorts вкусный обед",
                "#shorts десерт за 5 минут",
            ],
        },
    },

    "fitness": {
        "display_name": {
            "en": "Fitness & Workouts",
            "ru": "Фитнес и тренировки",
        },
        "hashtags": {
            "en": [
                "fitness", "workout", "gym", "gymmotivation",
                "homeworkout", "fitcheck", "fitnesstips",
                "abs", "calisthenics", "weightlossjourney",
                "fittok", "bodytransformation", "fitspo",
            ],
            "ru": [
                "фитнес", "тренировка", "зал", "спортзал",
                "домашняятренировка", "ппменю", "похудение",
                "пресс", "стройнаяфигура", "зожтиктоктренировка",
                "трансформациятела", "правильноепитание",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts ab workout home",
                "#shorts gym motivation",
                "#shorts weight loss transformation",
                "#shorts fitness tips beginner",
            ],
            "ru": [
                "#shorts тренировка дома",
                "#shorts мотивация зал",
                "#shorts похудение результат",
                "#shorts ппменю на день",
            ],
        },
    },

    "finance": {
        "display_name": {
            "en": "Finance & Passive Income",
            "ru": "Финансы и заработок",
        },
        "hashtags": {
            "en": [
                "passiveincome", "moneytips", "investing", "stockmarket",
                "financetips", "moneymindset", "wealth", "crypto",
                "sidehustle", "millionaire", "financialfreedom",
                "personalfinance", "moneymanagement",
            ],
            "ru": [
                "финансы", "инвестиции", "заработок", "пассивныйдоход",
                "деньги", "финансоваяграмотность", "сбережения",
                "криптовалюта", "подработка", "бизнесидея",
                "финансоваясвобода", "финансовыйуспех",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts passive income ideas",
                "#shorts money tips beginner",
                "#shorts side hustle 2026",
                "#shorts investing for beginners",
            ],
            "ru": [
                "#shorts заработок в интернете",
                "#shorts инвестиции для новичков",
                "#shorts финансовая грамотность",
                "#shorts пассивный доход 2026",
            ],
        },
    },

    "beauty": {
        "display_name": {
            "en": "Beauty & Makeup",
            "ru": "Красота и макияж",
        },
        "hashtags": {
            "en": [
                "makeup", "makeuptutorial", "skincare", "beauty",
                "beautytips", "haircare", "glowup", "beautyhacks",
                "grwm", "getreadywithme", "lipstick", "eyeliner",
                "skincareroutine", "selfcare",
            ],
            "ru": [
                "макияж", "макияжденьги", "уходзакожей", "красота",
                "бьютихаки", "уходзаволосами", "глоуап",
                "уходзалицом", "косметика", "помада",
                "макияжвечерний", "уходсебя",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts makeup tutorial",
                "#shorts skincare routine",
                "#shorts beauty hack viral",
                "#shorts glow up transformation",
            ],
            "ru": [
                "#shorts макияж урок",
                "#shorts уход за кожей",
                "#shorts бьюти хак",
                "#shorts глоу ап трансформация",
            ],
        },
    },

    "pets": {
        "display_name": {
            "en": "Pets & Cute Animals",
            "ru": "Питомцы и милые животные",
        },
        "hashtags": {
            "en": [
                "puppy", "kitten", "cuteanimals", "dogsoftiktok",
                "catsoftiktok", "petlife", "rescuedog", "fluffycat",
                "adoptdontshop", "dogtraining", "cattok",
                "funnydog", "funnypets",
            ],
            "ru": [
                "щенок", "котенок", "милыеживотные", "собака",
                "кошка", "питомец", "спасенныйпес", "котиктикток",
                "забавныеживотные", "приютживотных",
                "дрессировкасобак",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts cute puppy",
                "#shorts funny cat",
                "#shorts pet rescue story",
                "#shorts dog and owner bond",
            ],
            "ru": [
                "#shorts милый щенок",
                "#shorts смешной кот",
                "#shorts спас собаку",
                "#shorts питомец и хозяин",
            ],
        },
    },

    "parenting": {
        "display_name": {
            "en": "Parenting & Kids",
            "ru": "Родительство и дети",
        },
        "hashtags": {
            "en": [
                "parenting", "momlife", "dadlife", "parentingtips",
                "toddlerlife", "newborn", "raisingkids", "parentinghacks",
                "kidsoftiktok", "familytime", "parentingadvice",
            ],
            "ru": [
                "родительство", "мамажизнь", "папажизнь",
                "воспитаниедетей", "малыш", "новорожденный",
                "детитикток", "лайфхакимам", "семья",
                "советымам",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts parenting hack",
                "#shorts toddler funny moment",
                "#shorts raising kids advice",
                "#shorts mom life truth",
            ],
            "ru": [
                "#shorts лайфхак родителям",
                "#shorts смешные дети",
                "#shorts воспитание совет",
                "#shorts мама будни",
            ],
        },
    },

    "comedy": {
        "display_name": {
            "en": "Comedy & Skits",
            "ru": "Юмор и скетчи",
        },
        "hashtags": {
            "en": [
                "comedy", "funny", "skit", "comedyskit",
                "viral", "lol", "humor", "memes",
                "standupcomedy", "funnymoments", "satire",
            ],
            "ru": [
                "юмор", "смешно", "скетч", "приколы",
                "вирусное", "лол", "мемы",
                "стендап", "смешныемоменты", "сатира",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts comedy skit viral",
                "#shorts funny moment",
                "#shorts standup joke",
            ],
            "ru": [
                "#shorts скетч смешной",
                "#shorts приколы",
                "#shorts стендап шутка",
            ],
        },
    },

    "tech": {
        "display_name": {
            "en": "Tech & AI Tools",
            "ru": "Технологии и AI-инструменты",
        },
        "hashtags": {
            "en": [
                "tech", "techreview", "ai", "aitools",
                "chatgpt", "aitok", "gadgets", "techtips",
                "futuretech", "smartphone", "aifaq",
                "techhack", "newai",
            ],
            "ru": [
                "техника", "обзортехники", "нейросеть",
                "чатгпт", "айтуок", "гаджеты", "лайфхакитехника",
                "будущее", "смартфон", "новинкатехники",
                "ии",
            ],
        },
        "youtube_queries": {
            "en": [
                "#shorts new AI tool",
                "#shorts tech review 2026",
                "#shorts chatgpt prompt",
                "#shorts smartphone hack",
            ],
            "ru": [
                "#shorts новая нейросеть",
                "#shorts обзор гаджета",
                "#shorts чатгпт промпт",
                "#shorts лайфхак смартфон",
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
