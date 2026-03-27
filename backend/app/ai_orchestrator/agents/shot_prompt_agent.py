import json
from typing import List, Dict, Optional
from app.ai_orchestrator.llm_client import LLMClient

class ShotPromptAgent:
    """
    Agent for generating visual prompts with character consistency
    and Veo 3.1 best practices (audio, negative prompt, colon dialogue).
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_visual_prompt(
        self,
        scene_description: str,
        characters: List[Dict],
        style: str = "cinematic",
        character_appearances: Optional[Dict[str, str]] = None,
        visual_tags: Optional[List[str]] = None,
    ) -> dict:
        """
        Generate visual prompt with detailed character descriptions
        and Veo 3.1 audio/SFX/negative prompt.
        """
        character_section = self._build_character_section(characters, character_appearances)

        visual_tags_note = ""
        if visual_tags:
            tags_str = ", ".join(visual_tags[:5])
            visual_tags_note = f"\nVISUAL STYLE REFERENCE (from trend analysis): {tags_str}"

        system_prompt = """You are a visual prompt expert for Google Veo 3.1 AI video generation.
Create detailed, consistent prompts that preserve character appearances across scenes.
Always include specific physical descriptions for each character.
Include audio/SFX descriptions for every shot using structured format: SFX: ..., Ambient: ..., Music: ...
Use colon syntax for dialogue: "Character says: line" NOT quoted dialogue.
End with negative prompt using nouns: "Negative prompt: text overlays, subtitles, watermark, extra limbs, deformed anatomy"
Include "(no subtitles)" inline in every prompt.
Use exactly ONE camera movement per prompt (never combine multiple movements).
Return valid JSON only."""

        user_prompt = f"""
Create a visual prompt for Google Veo 3.1 video generation.

SCENE DESCRIPTION:
{scene_description}{visual_tags_note}

CHARACTERS IN SCENE:
{character_section}

STYLE: {style}
FORMAT: 9:16 vertical video (720x1280)

IMPORTANT: Include EXACT physical descriptions for each character to maintain consistency.

Return valid JSON:
{{
  "scene_number": 1,
  "visual_prompt": "Detailed prompt with character descriptions, audio, and constraints...",
  "character_descriptions": {{
    "CharacterName": "physical appearance description"
  }},
  "camera": "single camera movement description",
  "lighting": "lighting description",
  "audio": "SFX: ..., Ambient: ..., Music: ...",
  "negative_prompt": "text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated",
  "style": "{style}",
  "mood": "emotional mood"
}}
"""
        response = self.llm.generate_structured_output(system_prompt, user_prompt)
        return response if response else {}

    def _build_character_section(
        self,
        characters: List[Dict],
        appearances: Optional[Dict[str, str]] = None
    ) -> str:
        """Build detailed character description section"""
        if not characters:
            return "No specific characters"

        lines = []
        for char in characters:
            name = char.get("name", "Unknown")
            role = char.get("role", "")
            description = char.get("description", "")

            appearance = ""
            if appearances and name in appearances:
                appearance = appearances[name]

            line = f"- {name}"
            if role:
                line += f" ({role})"
            if description:
                line += f": {description}"
            if appearance:
                line += f"\n  APPEARANCE: {appearance}"

            lines.append(line)

        return "\n".join(lines)

    def generate_consistent_prompt(
        self,
        scene_description: str,
        characters: List[Dict],
        style: str = "cinematic",
        previous_scene_prompt: Optional[str] = None
    ) -> dict:
        """
        Generate prompt that maintains consistency with previous scene.
        """
        character_section = self._build_character_section(characters, None)

        consistency_note = ""
        if previous_scene_prompt:
            consistency_note = f"""
PREVIOUS SCENE PROMPT (maintain visual consistency):
{previous_scene_prompt[:500]}...

Ensure characters look EXACTLY the same as in the previous scene.
"""

        system_prompt = """You are a visual prompt expert for Google Veo 3.1 specializing in maintaining
character consistency across video scenes. Characters must look identical in every scene.
Include structured audio: SFX: ..., Ambient: ..., Music: ...
Use colon syntax for dialogue: Character says: line (NOT quotes).
Include "(no subtitles)" inline.
End with: Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated."""

        user_prompt = f"""
Create a visual prompt for scene continuation.

CURRENT SCENE:
{scene_description}

CHARACTERS:
{character_section}

{consistency_note}

STYLE: {style}
FORMAT: 9:16 vertical

Return JSON with detailed character descriptions that match previous scene:
{{
  "visual_prompt": "...",
  "character_descriptions": {{}},
  "camera": "single camera movement",
  "audio": "SFX: ..., Ambient: ..., Music: ...",
  "negative_prompt": "text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated",
  "mood": "..."
}}
"""
        response = self.llm.generate_structured_output(system_prompt, user_prompt)
        return response if response else {}
