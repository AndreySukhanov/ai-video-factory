"""
Story Generator Agent - генерирует структуру серии из идеи пользователя.
Использует OpenRouter с DeepSeek для генерации эпизодов с детальными промтами.
"""
import json
from typing import List, Optional
from pydantic import BaseModel
from app.core.config import settings


class EpisodePrompt(BaseModel):
    """Сгенерированный эпизод с промтом"""
    number: int
    title: str
    synopsis: str
    visual_prompt: str


class SeriesStructure(BaseModel):
    """Структура сгенерированной серии"""
    series_title: str
    logline: str
    genre: str
    main_character: str = ""  # Character description for consistency
    episodes: List[EpisodePrompt]


class StoryGenerator:
    """
    Генерирует структуру серии из идеи пользователя.
    Создаёт детальные визуальные промты для каждого эпизода.
    Использует OpenRouter с DeepSeek.
    """
    
    def __init__(self):
        # Check for OpenRouter key first, then fall back to OpenAI
        self.api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
        self.use_openrouter = bool(settings.OPENROUTER_API_KEY)
        self.use_real_api = bool(self.api_key)
        self.client = None
        
        if self.use_real_api:
            try:
                from openai import OpenAI
                if self.use_openrouter:
                    # OpenRouter uses OpenAI-compatible API
                    self.client = OpenAI(
                        api_key=self.api_key,
                        base_url="https://openrouter.ai/api/v1"
                    )
                    self.model = "deepseek/deepseek-chat-v3-0324"
                    print("[STORY GENERATOR] Using OpenRouter with DeepSeek V3")
                else:
                    self.client = OpenAI(api_key=self.api_key)
                    self.model = "gpt-4o-mini"
                    print("[STORY GENERATOR] Using OpenAI")
            except ImportError:
                print("[STORY GENERATOR] Warning: openai package not installed")
                self.use_real_api = False
    
    def generate_series(
        self,
        idea: str,
        genre: str = "drama",
        episodes_count: int = 5,
        duration: int = 4,
        aspect_ratio: str = "9:16"
    ) -> SeriesStructure:
        """
        Генерирует структуру серии с промтами для каждого эпизода.
        
        Args:
            idea: Основная идея серии от пользователя
            genre: Жанр (drama, comedy, thriller, fantasy, romance, action)
            episodes_count: Количество эпизодов (1-10)
            duration: Длительность каждого эпизода в секундах
            aspect_ratio: Соотношение сторон видео
            
        Returns:
            SeriesStructure с названием, логлайном и списком эпизодов
        """
        if not self.use_real_api or not self.client:
            return self._generate_mock_series(idea, genre, episodes_count)
        
        # Определяем формат видео
        format_info = {
            "9:16": "vertical mobile video (TikTok/Reels style), close-up and medium shots",
            "16:9": "horizontal cinematic video, wide establishing shots",
            "1:1": "square social media format, centered compositions"
        }
        
        # Genre-specific visual styles (moderation-safe descriptions)
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
        
        system_prompt = f"""You are a professional screenwriter and visual prompt engineer for AI-generated vertical micro-dramas.
Your task is to create a compelling series structure with detailed visual prompts for each episode.

GENRE STYLE for {genre.upper()}: {genre_style}

CRITICAL - CONTENT MODERATION SAFETY:
Google Veo 3 has strict content moderation. NEVER use these words in visual_prompt or character descriptions:
- BANNED: weapon, gun, knife, sword, blood, violence, fight, combat, tactical, military, kill, death, attack, battle
- INSTEAD USE: athletic wear, sporty outfit, urban style, chase, pursuit, escape, parkour, running, acrobatics, intense moment

CRITICAL - CHARACTER CONSISTENCY:
Without reference images, AI video generators create different people each time. To maintain consistency:
1. Create ONE detailed character description at the start (name, age, ethnicity, hair color/style, eye color, face shape, distinctive features)
2. Copy-paste this EXACT character description at the START of EVERY visual_prompt
3. Use the SAME clothing/outfit throughout the series for recognition
4. Example: "Mika, 24-year-old Japanese woman, long straight black hair to waist, dark almond eyes, soft oval face, wearing sleek black athletic wear with neon accents"

RULES:
1. Create dramatic, engaging stories with clear hooks matching the {genre} genre
2. Each episode should have a compelling visual prompt for AI video generation (Veo 3)
3. Visual prompts must START with the EXACT character description, then setting, lighting, action, camera work
4. APPLY THE GENRE STYLE to every visual prompt - use the specific lighting, mood, and camera work for {genre}
5. ALWAYS respond in the SAME LANGUAGE as the user's idea
6. Format: {format_info.get(aspect_ratio, 'vertical mobile video')}
7. Keep each episode self-contained but connected to the overall story arc
8. End each episode with a hook to encourage watching the next one"""

        user_request = f"""Create a {episodes_count}-episode micro-drama series based on this idea:

IDEA: "{idea}"

GENRE: {genre}
VIDEO FORMAT: {aspect_ratio}
EPISODE DURATION: {duration} seconds each

Return JSON with this EXACT structure:
{{
  "series_title": "Compelling title for the series",
  "logline": "One sentence describing the series",
  "main_character": "Full detailed description: name, age, ethnicity, hair (color, length, style), eyes (color, shape), face shape, distinctive features, clothing",
  "episodes": [
    {{
      "number": 1,
      "title": "Episode title",
      "synopsis": "Brief 1-2 sentence description of what happens",
      "visual_prompt": "START with the EXACT main_character description, then: setting details, character action, lighting, camera movement, mood. 80-120 words total."
    }}
  ]
}}

CRITICAL: Every visual_prompt MUST start with the EXACT same character description (copy from main_character) to ensure the AI generates the same person in every episode."""

        try:
            print(f"[STORY GENERATOR] Generating {episodes_count} episodes for: {idea[:50]}...")
            print(f"[STORY GENERATOR] Using model: {self.model}")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_request}
                ],
                temperature=0.8,
                max_tokens=4000
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
                    # Extract JSON block
                    json_str = raw_content[raw_content.find("{"):raw_content.rfind("}")+1]
                    if json_str:
                        result = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"[STORY GENERATOR] JSON parse error: {e}, trying to fix...")
                    # Try to fix truncated JSON by closing brackets
                    json_str = raw_content[raw_content.find("{"):]
                    # Count open/close brackets
                    open_curly = json_str.count("{")
                    close_curly = json_str.count("}")
                    open_square = json_str.count("[")
                    close_square = json_str.count("]")
                    # Add missing closers
                    json_str += "]" * (open_square - close_square)
                    json_str += "}" * (open_curly - close_curly)
                    try:
                        result = json.loads(json_str)
                        print(f"[STORY GENERATOR] Fixed JSON successfully!")
                    except:
                        # Last resort: try to parse partial episodes using more flexible regex
                        import re
                        # More flexible regex that handles multi-line content
                        episodes_match = re.findall(
                            r'"number"\s*:\s*(\d+).*?"title"\s*:\s*"([^"]+)".*?"synopsis"\s*:\s*"([^"]+)".*?"visual_prompt"\s*:\s*"((?:[^"\\]|\\.)*)"|'
                            r'"number"\s*:\s*(\d+).*?"visual_prompt"\s*:\s*"((?:[^"\\]|\\.)*)"',
                            raw_content, 
                            re.DOTALL | re.MULTILINE
                        )
                        if episodes_match:
                            episodes_data = []
                            for m in episodes_match:
                                if m[0]:  # First pattern match (full)
                                    episodes_data.append({
                                        "number": int(m[0]), 
                                        "title": m[1], 
                                        "synopsis": m[2], 
                                        "visual_prompt": m[3].replace('\\"', '"').replace('\\n', ' ')
                                    })
                                elif m[4]:  # Second pattern (minimal)
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
            
            # Parse episodes
            episodes = []
            for ep_data in result.get("episodes", []):
                episodes.append(EpisodePrompt(
                    number=ep_data.get("number", len(episodes) + 1),
                    title=ep_data.get("title", f"Episode {len(episodes) + 1}"),
                    synopsis=ep_data.get("synopsis", ""),
                    visual_prompt=ep_data.get("visual_prompt", "")
                ))
            
            # Quality check and auto-fix prompts
            if episodes:
                print(f"[STORY GENERATOR] Running quality check on {len(episodes)} episodes...")
                from .quality_checker import get_quality_checker
                quality_checker = get_quality_checker()
                
                # Convert to dict format for quality checker
                prompts_data = [
                    {
                        'number': ep.number,
                        'title': ep.title,
                        'synopsis': ep.synopsis,
                        'visual_prompt': ep.visual_prompt
                    }
                    for ep in episodes
                ]
                
                # Get main character from result
                main_character = result.get("main_character", "")
                
                # Check and fix
                fixed_prompts, reports = quality_checker.check_and_fix_prompts(prompts_data, main_character)
                
                # Update episodes with fixed prompts
                for i, (ep, fixed) in enumerate(zip(episodes, fixed_prompts)):
                    if fixed.get('visual_prompt') != ep.visual_prompt:
                        print(f"[STORY GENERATOR] Episode {ep.number} prompt was auto-fixed")
                        episodes[i] = EpisodePrompt(
                            number=ep.number,
                            title=ep.title,
                            synopsis=ep.synopsis,
                            visual_prompt=fixed.get('visual_prompt', ep.visual_prompt)
                        )
            
            series = SeriesStructure(
                series_title=result.get("series_title", "Untitled Series"),
                logline=result.get("logline", ""),
                genre=genre,
                main_character=result.get("main_character", ""),
                episodes=episodes
            )
            
            print(f"[STORY GENERATOR] Created series: {series.series_title} with {len(episodes)} episodes")
            return series
            
        except Exception as e:
            print(f"[STORY GENERATOR] Error: {e}, using mock")
            return self._generate_mock_series(idea, genre, episodes_count)
    
    def _generate_mock_series(
        self,
        idea: str,
        genre: str,
        episodes_count: int
    ) -> SeriesStructure:
        """Генерирует mock-серию когда API недоступен"""
        episodes = []
        for i in range(episodes_count):
            episodes.append(EpisodePrompt(
                number=i + 1,
                title=f"Episode {i + 1}",
                synopsis=f"Part {i + 1} of the story based on: {idea[:50]}",
                visual_prompt=f"{idea}. Episode {i + 1}. Cinematic vertical video, professional lighting, shallow depth of field, high quality."
            ))
        
        return SeriesStructure(
            series_title=f"Series: {idea[:30]}",
            logline=idea,
            genre=genre,
            episodes=episodes
        )


# Singleton instance
_story_generator = None

def get_story_generator() -> StoryGenerator:
    """Get or create singleton StoryGenerator instance."""
    global _story_generator
    if _story_generator is None:
        _story_generator = StoryGenerator()
    return _story_generator
