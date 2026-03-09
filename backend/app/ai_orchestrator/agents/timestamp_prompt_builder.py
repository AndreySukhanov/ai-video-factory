"""
Timestamp Prompt Builder - creates multi-shot prompts for Veo 3.1 using [HH:MM-HH:MM] syntax.
Maps narrative structures to timestamp segments within a single 8-second clip.

Example output:
  [00:00-00:02] Close-up of Maya's face, eyes widening in shock.
  [00:02-00:05] Camera pulls back revealing the empty room.
  [00:05-00:07] Maya turns and runs toward the door.
  [00:07-00:08] Quick cut to door slamming shut.
"""
import json
from typing import Optional
from app.core.config import settings


# Narrative structure templates with segment weights
NARRATIVE_TEMPLATES = {
    "hook_conflict_twist_cta": {
        "segments": ["Hook", "Conflict", "Twist", "CTA"],
        "weights": [0.25, 0.30, 0.30, 0.15],
        "description": "Classic viral hook structure",
    },
    "hook_buildup_climax_resolution": {
        "segments": ["Hook", "Buildup", "Climax", "Resolution"],
        "weights": [0.20, 0.30, 0.30, 0.20],
        "description": "Standard dramatic arc",
    },
    "question_evidence_reveal": {
        "segments": ["Question", "Evidence", "Reveal"],
        "weights": [0.25, 0.45, 0.30],
        "description": "Mystery/curiosity format",
    },
    "before_process_after": {
        "segments": ["Before", "Process", "After"],
        "weights": [0.25, 0.50, 0.25],
        "description": "Transformation format",
    },
    "pov_situation_reaction_outcome": {
        "segments": ["POV Setup", "Situation", "Reaction", "Outcome"],
        "weights": [0.20, 0.30, 0.25, 0.25],
        "description": "First-person perspective format",
    },
    "two_shot": {
        "segments": ["Part A", "Part B"],
        "weights": [0.50, 0.50],
        "description": "Simple two-shot contrast/comparison",
    },
}


class TimestampPromptBuilder:
    """
    Builds timestamp-segmented prompts for Veo 3.1 multi-shot generation.
    One 8-sec clip with N segments marked by [HH:MM-HH:MM] timestamps.
    """

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
        self.use_real_api = bool(self.api_key)
        self.client = None

        if self.use_real_api:
            try:
                from openai import OpenAI
                if settings.OPENROUTER_API_KEY:
                    self.client = OpenAI(
                        api_key=self.api_key,
                        base_url="https://openrouter.ai/api/v1"
                    )
                    self.model = "deepseek/deepseek-chat-v3-0324"
                else:
                    self.client = OpenAI(api_key=self.api_key)
                    self.model = "gpt-4o-mini"
            except ImportError:
                self.use_real_api = False

    def get_template(self, narrative_structure: str) -> dict:
        """Get narrative template by name, with fallback."""
        # Normalize key
        key = narrative_structure.lower().replace(" ", "_").replace("→", "_").replace("->", "_")
        # Try exact match
        if key in NARRATIVE_TEMPLATES:
            return NARRATIVE_TEMPLATES[key]
        # Try fuzzy match
        for template_key, template in NARRATIVE_TEMPLATES.items():
            if any(seg.lower() in key for seg in template["segments"]):
                return template
        # Default
        return NARRATIVE_TEMPLATES["hook_conflict_twist_cta"]

    def build_timestamps(self, duration: int, weights: list[float]) -> list[tuple[str, str]]:
        """Build [HH:MM-HH:MM] timestamp pairs from weights."""
        timestamps = []
        current = 0.0
        for weight in weights:
            start = current
            end = current + duration * weight
            start_str = f"00:{int(start):02d}"
            end_str = f"00:{int(round(end)):02d}"
            timestamps.append((start_str, end_str))
            current = end
        return timestamps

    def build_timestamp_prompt(
        self,
        scene_description: str,
        character_card: str = "",
        duration: int = 8,
        narrative_structure: str = "hook_conflict_twist_cta",
        aspect_ratio: str = "9:16",
    ) -> str:
        """
        Build a timestamp-segmented prompt from scene description and narrative structure.

        Args:
            scene_description: What happens in the scene
            character_card: Fixed character description
            duration: Video duration (ideally 8s for timestamps)
            narrative_structure: Key into NARRATIVE_TEMPLATES
            aspect_ratio: Video aspect ratio

        Returns:
            Formatted prompt with [HH:MM-HH:MM] segments
        """
        template = self.get_template(narrative_structure)
        timestamps = self.build_timestamps(duration, template["weights"])

        if self.use_real_api and self.client:
            return self._build_with_llm(
                scene_description, character_card, template, timestamps,
                duration, aspect_ratio
            )
        else:
            return self._build_basic(
                scene_description, character_card, template, timestamps,
                duration, aspect_ratio
            )

    def _build_with_llm(
        self,
        scene_description: str,
        character_card: str,
        template: dict,
        timestamps: list[tuple[str, str]],
        duration: int,
        aspect_ratio: str,
    ) -> str:
        """Build timestamp prompt using LLM."""
        segments_info = "\n".join([
            f"[{ts[0]}-{ts[1]}] {seg}"
            for ts, seg in zip(timestamps, template["segments"])
        ])

        system_prompt = """You are a professional filmmaker creating multi-shot timestamp prompts for Veo 3.1.
Each segment uses [HH:MM-HH:MM] syntax. Rules:
- Each segment is one continuous shot (ONE camera movement max)
- Character card appears ONLY in the first segment
- Each segment: [timestamp] camera + action + setting detail
- Include audio for each segment: SFX/Ambient/Music
- End with (no subtitles). Negative prompt. Technical constraints.
- Output ONLY the prompt text, no JSON, no explanation.
- ENGLISH ONLY."""

        user_msg = f"""Create a timestamp prompt for this scene:

SCENE: {scene_description}
CHARACTER: {character_card or 'No specific character'}
STRUCTURE ({template['description']}):
{segments_info}
DURATION: {duration}s
ASPECT: {aspect_ratio}

Write the complete prompt with [HH:MM-HH:MM] timestamps for each segment."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7,
                max_tokens=500,
                timeout=30,
            )
            prompt = response.choices[0].message.content.strip()

            # Ensure constraints at end
            if "(no subtitles)" not in prompt.lower():
                prompt += " (no subtitles)."
            if "negative prompt:" not in prompt.lower():
                prompt += " Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated."
            if aspect_ratio not in prompt:
                prompt += f" {aspect_ratio}, 720p, {duration}s."

            return prompt
        except Exception as e:
            print(f"[TIMESTAMP BUILDER] LLM failed: {e}, using basic builder")
            return self._build_basic(
                scene_description, character_card, template, timestamps,
                duration, aspect_ratio
            )

    def _build_basic(
        self,
        scene_description: str,
        character_card: str,
        template: dict,
        timestamps: list[tuple[str, str]],
        duration: int,
        aspect_ratio: str,
    ) -> str:
        """Build timestamp prompt without LLM using template."""
        parts = []
        for i, (ts, seg_name) in enumerate(zip(timestamps, template["segments"])):
            if i == 0 and character_card:
                parts.append(f"[{ts[0]}-{ts[1]}] {character_card}. {seg_name}: {scene_description}.")
            else:
                parts.append(f"[{ts[0]}-{ts[1]}] {seg_name}: continuation of the scene.")

        prompt = " ".join(parts)
        prompt += (
            f" SFX: subtle environmental sounds. Ambient: quiet atmosphere. Music: soft background score."
            f" (no subtitles). Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated."
            f" {aspect_ratio}, 720p, {duration}s."
        )
        return prompt


# Singleton
_timestamp_builder = None

def get_timestamp_builder() -> TimestampPromptBuilder:
    global _timestamp_builder
    if _timestamp_builder is None:
        _timestamp_builder = TimestampPromptBuilder()
    return _timestamp_builder
