import json
from typing import List, Dict, Optional
from app.ai_orchestrator.llm_client import LLMClient

class ShotPromptAgent:
    """
    Agent for generating visual prompts with character consistency
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_visual_prompt(
        self, 
        scene_description: str, 
        characters: List[Dict], 
        style: str = "cinematic",
        character_appearances: Optional[Dict[str, str]] = None
    ) -> dict:
        """
        Generate visual prompt with detailed character descriptions
        
        Args:
            scene_description: What happens in the scene
            characters: List of character dicts with name, role, description
            style: Visual style (cinematic, anime, etc.)
            character_appearances: Dict mapping character name to appearance prompt
        
        Returns:
            Dict with visual_prompt and other metadata
        """
        
        # Build detailed character appearance section
        character_section = self._build_character_section(characters, character_appearances)
        
        system_prompt = """You are a visual prompt expert for AI video generation. 
Create detailed, consistent prompts that preserve character appearances across scenes.
Always include specific physical descriptions for each character.
Return valid JSON only."""
        
        user_prompt = f"""
Create a visual prompt for a video generation AI (Veo 3 / Runway / Pika).

SCENE DESCRIPTION:
{scene_description}

CHARACTERS IN SCENE:
{character_section}

STYLE: {style}
FORMAT: 9:16 vertical video (720x1280)

IMPORTANT: Include EXACT physical descriptions for each character to maintain consistency.
Describe: face shape, hair color/style, skin tone, eye color, clothing, distinguishing features.

Return valid JSON:
{{
  "scene_number": 1,
  "visual_prompt": "Detailed prompt with character descriptions...",
  "character_descriptions": {{
    "CharacterName": "physical appearance description"
  }},
  "camera": "camera movement description",
  "lighting": "lighting description",
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
            
            # Use stored appearance prompt if available
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
        Generate prompt that maintains consistency with previous scene
        
        Args:
            scene_description: Current scene description
            characters: Characters in scene
            style: Visual style
            previous_scene_prompt: Prompt from previous scene for reference
        """
        
        character_section = self._build_character_section(characters, None)
        
        consistency_note = ""
        if previous_scene_prompt:
            consistency_note = f"""
PREVIOUS SCENE PROMPT (maintain visual consistency):
{previous_scene_prompt[:500]}...

Ensure characters look EXACTLY the same as in the previous scene.
"""
        
        system_prompt = """You are a visual prompt expert specializing in maintaining 
character consistency across video scenes. Characters must look identical in every scene."""
        
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
  "camera": "...",
  "mood": "..."
}}
"""
        response = self.llm.generate_structured_output(system_prompt, user_prompt)
        return response if response else {}

