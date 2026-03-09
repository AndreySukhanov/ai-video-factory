"""
Prompt Enhancer Agent - enhances user prompts for Veo 3.1 video generation
with 8-element formula, structured audio, English-only, I2V motion awareness.
"""
import json
from typing import Optional
from app.core.config import settings


class PromptEnhancer:
    """
    Enhances simple user prompts for video generation using Veo 3.1 best practices:
    8-element formula, structured audio, English-only output, I2V awareness.
    """

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
        self.use_openrouter = bool(settings.OPENROUTER_API_KEY)
        self.use_real_api = bool(self.api_key)
        self.client = None

        if self.use_real_api:
            try:
                from openai import OpenAI
                if self.use_openrouter:
                    self.client = OpenAI(
                        api_key=self.api_key,
                        base_url="https://openrouter.ai/api/v1"
                    )
                    self.model = "deepseek/deepseek-chat-v3-0324"
                    print("[PROMPT ENHANCER] Using OpenRouter with DeepSeek V3")
                else:
                    self.client = OpenAI(api_key=self.api_key)
                    self.model = "gpt-4o-mini"
                    print("[PROMPT ENHANCER] Using OpenAI")
            except ImportError:
                print("[PROMPT ENHANCER] Warning: openai package not installed")
                self.use_real_api = False

    def enhance_prompt(
        self,
        user_prompt: str,
        aspect_ratio: str = "9:16",
        duration: int = 4,
        is_i2v: bool = False
    ) -> str:
        """
        Enhances prompt using Veo 3.1 8-element formula.

        Args:
            user_prompt: Original user prompt
            aspect_ratio: Video aspect ratio
            duration: Video duration in seconds
            is_i2v: If True, prompt is for image-to-video (motion-only, don't re-describe subject)
        """
        if not self.use_real_api or not self.client:
            return self._basic_enhance(user_prompt, aspect_ratio, duration, is_i2v)

        i2v_instruction = ""
        if is_i2v:
            i2v_instruction = """
CRITICAL - IMAGE-TO-VIDEO (I2V) MODE:
This prompt will be used with a reference image as first frame.
Describe MOTION and CHANGES ONLY - do NOT re-describe the subject/character/scene visible in the image.
Focus on: what moves, how it moves, camera movement, audio changes.
BAD: "A young woman with brown hair stands in a park..."
GOOD: "Subject walks forward slowly, hair swaying in the breeze, gentle smile forming..."
"""

        system_prompt = f"""You are a professional FILMMAKER crafting video prompts for Google Veo 3.1.
Your task is to enhance user prompts using the 8-ELEMENT FORMULA for maximum quality.

OUTPUT MUST BE IN ENGLISH regardless of input language.

8-ELEMENT FORMULA:
1. [Camera/Shot] - Use exactly ONE camera movement (slow dolly-in OR gentle pan left, NEVER both — combining causes flicker)
2. [Character/Subject] - Main subject description
3. [Action] - What happens
4. [Setting] - Location/environment
5. [Style] - Visual style (cinematic, film grain, etc.)
6. [Lighting] - Lighting description
7. [Audio/SFX] - Structured: "SFX: [sounds]. Ambient: [environment]. Music: [mood/instrument]."
8. [Constraints] - "(no subtitles). Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated."

RULES:
1. Keep the ORIGINAL meaning and subject
2. Add ALL 8 elements if missing
3. ONE camera movement only (never combine!)
4. Dialogue uses colon syntax: "Character says: line" (NOT quotes)
5. Structured audio is MANDATORY
6. Include "(no subtitles)" inline
7. Negative prompt uses NOUNS (NOT "no X")
8. End with technical constraints
9. Return ONLY JSON
10. For ANIMAL characters: ALWAYS specify exact number of legs (e.g. "four-legged fox", "quadruped") in Character/Subject to prevent anatomical errors
11. NEVER put "cartoon" in negative prompt if the user wants cartoon/animation style — it conflicts with the request
{i2v_instruction}"""

        format_info = {
            "9:16": "vertical mobile format, portrait orientation, close-up or medium shots",
            "16:9": "horizontal cinematic format, wide shots work well",
        }

        user_request = f"""Enhance this video generation prompt:

ORIGINAL PROMPT: "{user_prompt}"

VIDEO FORMAT: {aspect_ratio} ({format_info.get(aspect_ratio, 'vertical')})
DURATION: {duration} seconds
{"MODE: Image-to-Video (describe MOTION ONLY)" if is_i2v else "MODE: Text-to-Video"}

Return JSON with:
{{
  "enhanced_prompt": "Full enhanced prompt with ALL 8 elements IN ENGLISH, ending with {aspect_ratio}, 720p, {duration}s.",
  "camera": "single camera movement",
  "lighting": "lighting description",
  "audio": "SFX: ..., Ambient: ..., Music: ...",
  "mood": "emotional mood",
  "negative_prompt": "text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated"
}}"""

        try:
            print(f"[PROMPT ENHANCER] Calling {self.model}... (I2V={is_i2v})")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_request}
                ],
                temperature=0.7,
                max_tokens=600,
                timeout=30,
            )

            content = response.choices[0].message.content
            if "{" in content and "}" in content:
                json_str = content[content.find("{"):content.rfind("}")+1]
                result = json.loads(json_str)
            else:
                result = json.loads(content)

            if result and result.get("enhanced_prompt"):
                enhanced = result["enhanced_prompt"]

                # Ensure (no subtitles) is present
                if "(no subtitles)" not in enhanced.lower():
                    if "negative prompt:" in enhanced.lower():
                        enhanced = enhanced.replace("Negative prompt:", "(no subtitles). Negative prompt:")
                    else:
                        enhanced = enhanced.rstrip('.') + ". (no subtitles)."

                # Ensure negative prompt is present
                if "negative prompt:" not in enhanced.lower():
                    neg = result.get("negative_prompt", "text overlays, subtitles, cartoon, watermark, blurry, low quality")
                    enhanced = enhanced.rstrip('.') + f". Negative prompt: {neg}."

                # Ensure structured audio is present
                if not any(w in enhanced.lower() for w in ['sfx:', 'ambient:', 'music:']):
                    audio = result.get("audio", "SFX: subtle environmental sounds. Ambient: quiet atmosphere. Music: soft background score")
                    neg_idx = enhanced.lower().find("(no subtitles)")
                    if neg_idx == -1:
                        neg_idx = enhanced.lower().find("negative prompt:")
                    if neg_idx > 0:
                        enhanced = enhanced[:neg_idx] + audio + ". " + enhanced[neg_idx:]
                    else:
                        enhanced += f" {audio}."

                # Ensure tech constraints at end
                if aspect_ratio not in enhanced and "720p" not in enhanced:
                    enhanced = enhanced.rstrip('.') + f". {aspect_ratio}, 720p, {duration}s."

                print(f"[PROMPT ENHANCER] Original: {user_prompt[:50]}...")
                print(f"[PROMPT ENHANCER] Enhanced: {enhanced[:100]}...")
                return enhanced
            else:
                print("[PROMPT ENHANCER] No enhanced prompt in response, using basic enhance")
                return self._basic_enhance(user_prompt, aspect_ratio, duration, is_i2v)

        except Exception as e:
            print(f"[PROMPT ENHANCER] Error: {e}, falling back to basic enhance")
            return self._basic_enhance(user_prompt, aspect_ratio, duration, is_i2v)

    def _basic_enhance(self, prompt: str, aspect_ratio: str, duration: int = 4, is_i2v: bool = False) -> str:
        """
        Basic enhancement without LLM using Veo 3.1 formula.
        """
        if aspect_ratio == "9:16":
            format_hint = "vertical mobile video, portrait orientation"
        elif aspect_ratio == "16:9":
            format_hint = "horizontal cinematic video, widescreen"
        else:
            format_hint = "square format video"

        if is_i2v:
            enhanced = (
                f"Subject moves forward with subtle motion, smooth natural movement. {prompt}. "
                f"{format_hint}, cinematic, professional lighting, shallow depth of field. "
                f"SFX: subtle environmental sounds. Ambient: quiet atmosphere. Music: soft background score. "
                f"(no subtitles). Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated. "
                f"{aspect_ratio}, 720p, {duration}s."
            )
        else:
            enhanced = (
                f"{prompt}. {format_hint}, cinematic, professional lighting, shallow depth of field. "
                f"SFX: subtle environmental sounds. Ambient: quiet atmosphere. Music: soft background score. "
                f"(no subtitles). Negative prompt: text overlays, subtitles, watermark, blurry, low quality, extra limbs, deformed anatomy, mutated. "
                f"{aspect_ratio}, 720p, {duration}s."
            )

        print(f"[PROMPT ENHANCER] Basic enhance applied: {enhanced[:100]}...")
        return enhanced


# Singleton instance
_prompt_enhancer = None

def get_prompt_enhancer() -> PromptEnhancer:
    """Get or create singleton PromptEnhancer instance."""
    global _prompt_enhancer
    if _prompt_enhancer is None:
        _prompt_enhancer = PromptEnhancer()
    return _prompt_enhancer
