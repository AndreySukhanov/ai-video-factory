"""
Story Generator Agent - generates series structure from user idea.
Uses OpenRouter with DeepSeek for episode generation with Veo 3.1 best practices:
ANCHOR+VARIABLE pattern, 8-element formula, English-only prompts, audio-first.
"""
import json
import re
from typing import List, Optional
from pydantic import BaseModel
from app.core.config import settings


class EpisodePrompt(BaseModel):
    """Generated episode with Veo 3.1 optimized prompt"""
    number: int
    title: str
    synopsis: str
    visual_prompt: str           # full prompt (anchor + variable combined)
    anchor_prompt: str = ""      # invariant part (camera, character, setting, lighting, style)
    variable_prompt: str = ""    # unique part (action, dialogue, audio, negative)


class SeriesStructure(BaseModel):
    """Generated series structure with Veo 3.1 metadata"""
    series_title: str
    logline: str
    genre: str
    main_character: str = ""
    character_card: str = ""     # fixed text <= 50 words for every prompt
    voice_description: str = ""  # "warm female voice, American accent"
    anchor_prompt: str = ""      # shared anchor for entire series
    episodes: List[EpisodePrompt]


class StoryGenerator:
    """
    Generates series structure from user idea.
    Creates detailed visual prompts for each episode using Veo 3.1 best practices.
    """

    # Public aliases user can pick in UI → (provider, model_id)
    LLM_PRESETS = {
        "deepseek": ("openrouter", "deepseek/deepseek-v4-pro"),
        "opus-4.8": ("laozhang", "claude-opus-4-8"),
        "gpt-5.5":  ("openai", "gpt-5.5"),
    }

    def __init__(self, llm_preset: str | None = None):
        """
        llm_preset: 'deepseek' | 'opus-4.8' | 'gpt-5.5' | None (auto)
        Auto prefers LaoZhang+Claude if LAOZHANG_API_KEY else OpenRouter+DeepSeek else OpenAI.
        """
        self.client = None
        self.use_real_api = False
        self.model = ""
        self.is_claude = False

        provider, model = None, None
        if llm_preset and llm_preset in self.LLM_PRESETS:
            provider, model = self.LLM_PRESETS[llm_preset]

        if not provider:
            if settings.LAOZHANG_API_KEY:
                provider, model = "laozhang", "claude-opus-4-8"
            elif settings.OPENROUTER_API_KEY:
                provider, model = "openrouter", "deepseek/deepseek-v4-pro"
            elif settings.OPENAI_API_KEY:
                provider, model = "openai", "gpt-4o-mini"
            else:
                return

        try:
            from openai import OpenAI
        except ImportError:
            print("[STORY GENERATOR] Warning: openai package not installed")
            return

        if provider == "laozhang":
            if not settings.LAOZHANG_API_KEY:
                print("[STORY GENERATOR] LaoZhang requested but LAOZHANG_API_KEY missing")
                return
            self.client = OpenAI(api_key=settings.LAOZHANG_API_KEY, base_url=settings.LAOZHANG_BASE_URL)
        elif provider == "openrouter":
            if not settings.OPENROUTER_API_KEY:
                print("[STORY GENERATOR] OpenRouter requested but OPENROUTER_API_KEY missing")
                return
            self.client = OpenAI(api_key=settings.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
        else:  # openai
            if not settings.OPENAI_API_KEY:
                print("[STORY GENERATOR] OpenAI requested but OPENAI_API_KEY missing")
                return
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

        self.model = model
        self.provider = provider
        self.is_claude = model.startswith("claude")
        self.use_real_api = True
        print(f"[STORY GENERATOR] Using {provider} with {model}")

    def generate_series(
        self,
        idea: str,
        genre: str = "drama",
        episodes_count: int = 5,
        duration: int = 4,
        aspect_ratio: str = "9:16"
    ) -> SeriesStructure:
        """
        Generates series structure with Veo 3.1 optimized prompts for each episode.
        """
        if not self.use_real_api or not self.client:
            return self._generate_mock_series(idea, genre, episodes_count, duration, aspect_ratio)

        format_info = {
            "9:16": "vertical mobile video (TikTok/Reels style), close-up and medium shots",
            "16:9": "horizontal cinematic video, wide establishing shots",
        }

        genre_styles = {
            "drama": "emotional close-ups, dramatic lighting with shadows, slow camera movements, intimate moments, melancholic or intense mood",
            "comedy": "bright colorful lighting, dynamic camera work, exaggerated expressions, upbeat and playful mood, quick cuts",
            "thriller": "moody atmospheric lighting, suspenseful tension, dutch angles, fog and mist, slow tension-building zooms, cool color palette",
            "fantasy": "magical glowing effects, vibrant saturated colors, ethereal lighting, sweeping camera movements, mystical atmosphere",
            "romance": "warm golden hour lighting, soft focus, intimate framing, gentle camera moves, dreamy bokeh, tender moments",
            "action": "dynamic camera angles, energetic movement, athletic performance, high contrast lighting, intense close-ups, fast-paced editing, parkour and chase sequences, urban exploration",
            "horror": "low-key atmospheric lighting, unsettling angles, deep shadows, desaturated colors, slow dread-building camera moves, eerie silence",
            "scifi": "futuristic neon lighting, sleek reflective surfaces, cool blue-purple palette, wide establishing shots of technology",
            "mystery": "film noir lighting, shadows and silhouettes, foggy atmosphere, revealing camera movements, suspenseful pacing",
            "melodrama": "heightened emotions, dramatic lighting contrasts, tearful close-ups, sweeping orchestral mood, intense colors"
        }

        genre_style = genre_styles.get(genre.lower(), genre_styles["drama"])

        system_prompt = f"""You are a professional FILMMAKER crafting video prompts for Google Veo 3.1 AI video generation.
Your task is to create a compelling series with PRODUCTION-QUALITY visual prompts following the 8-ELEMENT FORMULA.

GENRE STYLE for {genre.upper()}: {genre_style}

=== CRITICAL: ENGLISH-ONLY PROMPTS ===
ALL visual_prompt, anchor_prompt, variable_prompt, character_card, voice_description fields MUST be in ENGLISH regardless of input language.
Title and synopsis can be in the user's language.

=== 8-ELEMENT FORMULA (every prompt must contain ALL 8) ===
1. [Camera/Shot] - ONE camera movement (slow dolly-in OR gentle pan left, NEVER both — combining causes flicker)
2. [Character Card] - Fixed character description (<=50 words, same for ALL episodes)
3. [Action] - What happens in this episode
4. [Setting] - Location/environment
5. [Style] - Visual style (cinematic, film grain, etc.)
6. [Lighting] - Lighting description
7. [Audio/SFX] - Structured format: "SFX: [sounds]. Ambient: [environment]. Music: [mood/instrument]."
8. [Constraints/Negative] - "(no subtitles). Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated."

=== ANCHOR + VARIABLE PATTERN ===
ANCHOR (IDENTICAL for ALL episodes): camera setup, character_card, setting/location, lighting style, visual style
VARIABLE (UNIQUE per episode): action/movement, dialogue (colon syntax!), audio/SFX, negative prompt

=== DIALOGUE RULES ===
- Use COLON syntax: "Character says: dialogue line" — NOT quotes (Veo renders subtitles with quotes)
- Voice consistency: "In a [voice_description], [character] says: ..."
- Each dialogue line MUST fit in <=8 seconds of natural speech (~20 words max)

=== CONTENT MODERATION ===
Google Veo 3.1 has strict content moderation. NEVER use these words in visual_prompt:
- BANNED: weapon, gun, knife, sword, blood, violence, fight, combat, tactical, military, kill, death, attack, battle
- INSTEAD USE: athletic wear, sporty outfit, urban style, chase, pursuit, escape, parkour, running, acrobatics, intense moment

=== NO COPYRIGHTED CHARACTERS ===
NEVER include copyrighted or famous characters. Create ORIGINAL characters.

=== CHARACTER CONSISTENCY ===
Create ONE detailed character_card (<=50 words) at the start. This EXACT text is prepended to EVERY prompt.
Include: name, age, ethnicity, hair, eyes, face, distinctive features, clothing.
For ANIMAL characters: ALWAYS specify "four-legged" or "quadruped" explicitly to prevent extra limbs artifacts.

=== TECHNICAL CONSTRAINTS ===
Every visual_prompt MUST end with: "{aspect_ratio}, 720p, {duration}s."
Format: {format_info.get(aspect_ratio, 'vertical mobile video')}
Word limit: 80-120 words per visual_prompt

=== INLINE SUBTITLE PREVENTION ===
Include "(no subtitles)" in EVERY prompt."""

        user_request = f"""Create a {episodes_count}-episode micro-drama series based on this idea:

IDEA: "{idea}"

GENRE: {genre}
VIDEO FORMAT: {aspect_ratio}
EPISODE DURATION: {duration} seconds each

Return JSON with this EXACT structure:
{{
  "series_title": "Compelling title for the series",
  "logline": "One sentence describing the series",
  "main_character": "Full detailed description in English",
  "character_card": "<=50 words fixed character description IN ENGLISH (name, age, ethnicity, hair, eyes, face, clothing)",
  "voice_description": "voice type description (e.g. warm raspy female voice, American accent)",
  "anchor_prompt": "shared camera + character_card + setting + lighting + style (IDENTICAL for all episodes, IN ENGLISH)",
  "episodes": [
    {{
      "number": 1,
      "title": "Episode title",
      "synopsis": "Brief 1-2 sentence description",
      "anchor_prompt": "copy of the shared anchor_prompt above",
      "variable_prompt": "unique action + dialogue (colon syntax: Character says: line) + SFX: .../Ambient: .../Music: ... + (no subtitles). Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated. {aspect_ratio}, 720p, {duration}s.",
      "visual_prompt": "anchor_prompt + variable_prompt combined into one flowing prompt, 80-120 words, IN ENGLISH"
    }}
  ]
}}

CRITICAL RULES:
1. ALL prompts in ENGLISH regardless of input language
2. character_card <= 50 words, same for ALL episodes
3. ONE camera movement per episode (never combine)
4. Dialogue uses colon syntax: Character says: line (NOT quotes)
5. Each dialogue line <= 20 words (~8 sec speech)
6. Include (no subtitles) inline in every prompt
7. Negative prompt uses NOUNS: "text overlays, subtitles, extra limbs" NOT "no cartoon, don't draw"
8. Structured audio: SFX: ..., Ambient: ..., Music: ...
9. End every visual_prompt with: {aspect_ratio}, 720p, {duration}s.
10. Main character is visual focus of EVERY episode"""

        try:
            print(f"[STORY GENERATOR] Generating {episodes_count} episodes for: {idea[:50]}...")
            print(f"[STORY GENERATOR] Using model: {self.model}")

            # Each episode carries long English Veo prompts (~700-900 tokens).
            # Scale the budget with episode count so 10-episode plans don't truncate.
            series_max_tokens = min(16000, max(4000, 1500 + episodes_count * 850))
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_request}
                ],
                temperature=0.8,
                max_tokens=series_max_tokens,
                timeout=120,
            )

            raw_content = response.choices[0].message.content
            print(f"[STORY GENERATOR] Raw response length: {len(raw_content) if raw_content else 0}")
            print(f"[STORY GENERATOR] Raw response first 500 chars: {raw_content[:500] if raw_content else 'EMPTY'}")

            # Clean markdown code blocks if present
            if raw_content:
                if "```json" in raw_content:
                    raw_content = raw_content.replace("```json", "").replace("```", "")
                elif "```" in raw_content:
                    raw_content = raw_content.replace("```", "")
                raw_content = raw_content.strip()

            # Try to extract and parse JSON with error recovery
            result = {}
            if raw_content and "{" in raw_content:
                try:
                    json_str = raw_content[raw_content.find("{"):raw_content.rfind("}")+1]
                    if json_str:
                        result = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"[STORY GENERATOR] JSON parse error: {e}, trying to fix...")
                    json_str = raw_content[raw_content.find("{"):]
                    open_curly = json_str.count("{")
                    close_curly = json_str.count("}")
                    open_square = json_str.count("[")
                    close_square = json_str.count("]")
                    json_str += "]" * (open_square - close_square)
                    json_str += "}" * (open_curly - close_curly)
                    try:
                        result = json.loads(json_str)
                        print(f"[STORY GENERATOR] Fixed JSON successfully!")
                    except:
                        episodes_match = re.findall(
                            r'"number"\s*:\s*(\d+).*?"title"\s*:\s*"([^"]+)".*?"synopsis"\s*:\s*"([^"]+)".*?"visual_prompt"\s*:\s*"((?:[^"\\]|\\.)*)"|'
                            r'"number"\s*:\s*(\d+).*?"visual_prompt"\s*:\s*"((?:[^"\\]|\\.)*)"',
                            raw_content,
                            re.DOTALL | re.MULTILINE
                        )
                        if episodes_match:
                            episodes_data = []
                            for m in episodes_match:
                                if m[0]:
                                    episodes_data.append({
                                        "number": int(m[0]),
                                        "title": m[1],
                                        "synopsis": m[2],
                                        "visual_prompt": m[3].replace('\\"', '"').replace('\\n', ' ')
                                    })
                                elif m[4]:
                                    episodes_data.append({
                                        "number": int(m[4]),
                                        "title": f"Episode {m[4]}",
                                        "synopsis": "",
                                        "visual_prompt": m[5].replace('\\"', '"').replace('\\n', ' ')
                                    })
                            if episodes_data:
                                result = {
                                    "series_title": "Generated Series",
                                    "logline": idea,
                                    "episodes": episodes_data
                                }
                                print(f"[STORY GENERATOR] Extracted {len(episodes_data)} episodes via regex")

            # Extract new Veo 3.1 fields
            character_card = result.get("character_card", "")
            voice_description = result.get("voice_description", "")
            series_anchor_prompt = result.get("anchor_prompt", "")
            main_character = result.get("main_character", "")

            # Auto-build character_card if LLM didn't provide one
            if not character_card and main_character:
                print("[STORY GENERATOR] No character_card from LLM, auto-building...")
                character_card = self.build_character_card(main_character, genre)

            # Parse episodes
            episodes = []
            tech_suffix = f"{aspect_ratio}, 720p, {duration}s."

            for ep_data in result.get("episodes", []):
                visual_prompt = ep_data.get("visual_prompt", "")
                ep_anchor = ep_data.get("anchor_prompt", series_anchor_prompt)
                ep_variable = ep_data.get("variable_prompt", "")

                # If visual_prompt is empty but we have anchor+variable, combine them
                if not visual_prompt and ep_anchor and ep_variable:
                    visual_prompt = f"{ep_anchor}. {ep_variable}"

                # Inject character_card at start if not present
                if character_card and character_card.lower()[:20] not in visual_prompt.lower():
                    visual_prompt = f"{character_card}. {visual_prompt}"
                elif main_character and not character_card:
                    if not visual_prompt.lower().startswith(main_character[:20].lower()):
                        visual_prompt = f"{main_character}. {visual_prompt}"

                # Append tech constraints if missing
                if aspect_ratio not in visual_prompt and "720p" not in visual_prompt:
                    visual_prompt = f"{visual_prompt.rstrip('.')}. {tech_suffix}"

                # Append (no subtitles) if missing
                if "(no subtitles)" not in visual_prompt.lower():
                    # Insert before Negative prompt if present
                    if "negative prompt:" in visual_prompt.lower():
                        visual_prompt = visual_prompt.replace("Negative prompt:", "(no subtitles). Negative prompt:")
                        visual_prompt = visual_prompt.replace("negative prompt:", "(no subtitles). Negative prompt:")
                    else:
                        visual_prompt = visual_prompt.rstrip('.') + ". (no subtitles)."

                # Append default negative prompt if missing
                if "negative prompt:" not in visual_prompt.lower():
                    visual_prompt = visual_prompt.rstrip('.') + ". Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated."

                # Append default audio if missing
                if not any(w in visual_prompt.lower() for w in ['sfx:', 'ambient:', 'music:']):
                    # Insert before negative prompt
                    neg_idx = visual_prompt.lower().find("(no subtitles)")
                    if neg_idx == -1:
                        neg_idx = visual_prompt.lower().find("negative prompt:")
                    if neg_idx > 0:
                        visual_prompt = visual_prompt[:neg_idx] + "SFX: subtle environmental sounds. Ambient: quiet atmosphere. Music: soft background score. " + visual_prompt[neg_idx:]
                    else:
                        visual_prompt += " SFX: subtle environmental sounds. Ambient: quiet atmosphere. Music: soft background score."

                episodes.append(EpisodePrompt(
                    number=ep_data.get("number", len(episodes) + 1),
                    title=ep_data.get("title", f"Episode {len(episodes) + 1}"),
                    synopsis=ep_data.get("synopsis", ""),
                    visual_prompt=visual_prompt,
                    anchor_prompt=ep_anchor,
                    variable_prompt=ep_variable
                ))

            # Quality check and auto-fix prompts
            if episodes:
                print(f"[STORY GENERATOR] Running quality check on {len(episodes)} episodes...")
                from .quality_checker import get_quality_checker
                quality_checker = get_quality_checker()

                prompts_data = [
                    {
                        'number': ep.number,
                        'title': ep.title,
                        'synopsis': ep.synopsis,
                        'visual_prompt': ep.visual_prompt
                    }
                    for ep in episodes
                ]

                fixed_prompts, reports = quality_checker.check_and_fix_prompts(prompts_data, main_character)

                for i, (ep, fixed) in enumerate(zip(episodes, fixed_prompts)):
                    if fixed.get('visual_prompt') != ep.visual_prompt:
                        print(f"[STORY GENERATOR] Episode {ep.number} prompt was auto-fixed")
                        episodes[i] = EpisodePrompt(
                            number=ep.number,
                            title=ep.title,
                            synopsis=ep.synopsis,
                            visual_prompt=fixed.get('visual_prompt', ep.visual_prompt),
                            anchor_prompt=ep.anchor_prompt,
                            variable_prompt=ep.variable_prompt
                        )

            series = SeriesStructure(
                series_title=result.get("series_title", "Untitled Series"),
                logline=result.get("logline", ""),
                genre=genre,
                main_character=main_character,
                character_card=character_card,
                voice_description=voice_description,
                anchor_prompt=series_anchor_prompt,
                episodes=episodes
            )

            print(f"[STORY GENERATOR] Created series: {series.series_title} with {len(episodes)} episodes")
            print(f"[STORY GENERATOR] Character card: {character_card[:80]}" if character_card else "[STORY GENERATOR] No character card")
            print(f"[STORY GENERATOR] Anchor prompt: {series_anchor_prompt[:80]}" if series_anchor_prompt else "[STORY GENERATOR] No anchor prompt")
            return series

        except Exception as e:
            print(f"[STORY GENERATOR] Error: {e}, using mock")
            return self._generate_mock_series(idea, genre, episodes_count, duration, aspect_ratio)

    def build_character_card(self, description: str, genre: str = "drama") -> str:
        """
        Auto-generate a character_card (<=50 words) from a free-form description via LLM.
        Used when LLM didn't return a character_card in series generation.
        """
        if not self.use_real_api or not self.client:
            # Basic extraction: take first 50 words
            words = description.split()[:50]
            return " ".join(words)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": (
                        "You create character cards for AI video generation (Veo 3.1). "
                        "A character card is a FIXED visual description (<=50 words, ENGLISH ONLY) "
                        "that is prepended to EVERY video prompt for consistency. "
                        "Include: name, age, ethnicity, hair (color/style), eyes, face shape, "
                        "distinctive features, clothing. Be specific and visual. "
                        "Return ONLY the character card text, nothing else."
                    )},
                    {"role": "user", "content": (
                        f"Create a character card (<=50 words, English) from this description:\n\n"
                        f"{description}\n\nGenre: {genre}"
                    )}
                ],
                temperature=0.5,
                max_tokens=100,
                timeout=30,
            )
            card = response.choices[0].message.content.strip()
            # Remove quotes if LLM wrapped it
            card = card.strip('"').strip("'")
            # Enforce 50-word limit
            words = card.split()
            if len(words) > 50:
                card = " ".join(words[:50])
            print(f"[STORY GENERATOR] Built character card: {card[:80]}...")
            return card
        except Exception as e:
            print(f"[STORY GENERATOR] Character card generation failed: {e}")
            words = description.split()[:50]
            return " ".join(words)

    def _generate_mock_series(
        self,
        idea: str,
        genre: str,
        episodes_count: int,
        duration: int = 4,
        aspect_ratio: str = "9:16"
    ) -> SeriesStructure:
        """Generates mock series when API is unavailable"""
        character_card = "Alex, 28-year-old person, short brown hair, green eyes, oval face, wearing casual dark jacket and jeans"
        anchor = f"Medium shot, slow dolly-in. {character_card}. Urban city street, golden hour lighting, cinematic film grain"
        tech_suffix = f"{aspect_ratio}, 720p, {duration}s."

        episodes = []
        for i in range(episodes_count):
            variable = f"Character walks forward with determination. SFX: footsteps on pavement. Ambient: distant city traffic. Music: soft piano melody. (no subtitles). Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated. {tech_suffix}"
            episodes.append(EpisodePrompt(
                number=i + 1,
                title=f"Episode {i + 1}",
                synopsis=f"Part {i + 1} of the story based on: {idea[:50]}",
                visual_prompt=f"{anchor}. {variable}",
                anchor_prompt=anchor,
                variable_prompt=variable
            ))

        return SeriesStructure(
            series_title=f"Series: {idea[:30]}",
            logline=idea,
            genre=genre,
            character_card=character_card,
            voice_description="calm neutral voice",
            anchor_prompt=anchor,
            episodes=episodes
        )


# Per-preset cache (so we don't rebuild OpenAI client every request)
_story_generators: dict[str, StoryGenerator] = {}

def get_story_generator(llm_preset: str | None = None) -> StoryGenerator:
    """
    Get or create StoryGenerator instance for the given LLM preset.
    llm_preset: 'deepseek' | 'opus-4.8' | 'gpt-5.5' | None (auto-detect)
    """
    cache_key = llm_preset or "auto"
    if cache_key not in _story_generators:
        _story_generators[cache_key] = StoryGenerator(llm_preset=llm_preset)
    return _story_generators[cache_key]
