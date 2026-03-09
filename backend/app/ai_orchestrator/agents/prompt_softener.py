"""
Prompt Softener Agent — rewrites rejected prompts to pass content moderation.

When a video provider rejects a prompt due to content policy / moderation,
this agent rewrites it keeping the same narrative, characters, emotions, and plot
while removing explicit violence, weapons, etc.
"""

import os
import re
from typing import Optional


# Fallback dictionary for when LLM is unavailable
_SOFTEN_REPLACEMENTS = {
    "weapon": "object",
    "gun": "device",
    "knife": "tool",
    "sword": "staff",
    "blood": "red light",
    "violence": "dramatic tension",
    "fight": "intense confrontation",
    "combat": "athletic struggle",
    "kill": "defeat",
    "death": "dramatic ending",
    "attack": "sudden approach",
    "battle": "dramatic challenge",
    "murder": "mystery",
    "assault": "fierce approach",
    "bomb": "blast of light",
    "explosion": "dramatic flash",
    "shooting": "pursuit",
    "stab": "sharp gesture",
    "war": "conflict",
    "destroy": "overcome",
    "torture": "suffering",
    "brutal": "intense",
    "gore": "dramatic imagery",
}

_SAFETY_PREFIX = "Cinematic professional production. "


class PromptSoftener:
    """
    Rewrites prompts rejected by content moderation.
    Uses LLM (OpenRouter/DeepSeek) when available, falls back to dictionary replacement.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.client = None
        self.model = "deepseek/deepseek-chat-v3-0324"

        if self.api_key:
            try:
                from openai import OpenAI
                if os.getenv("OPENROUTER_API_KEY"):
                    self.client = OpenAI(
                        api_key=self.api_key,
                        base_url="https://openrouter.ai/api/v1"
                    )
                else:
                    self.client = OpenAI(api_key=self.api_key)
                print("[SOFTENER] Initialized with LLM support")
            except ImportError:
                print("[SOFTENER] Warning: openai not installed, using dictionary fallback")

    async def soften(self, original_prompt: str, error_message: str) -> str:
        """
        Rewrite a rejected prompt to pass moderation.

        Args:
            original_prompt: The prompt that was rejected
            error_message: Error message from the provider

        Returns:
            Softened prompt string
        """
        print(f"[SOFTENER] Prompt rejected, softening... Error: {error_message[:100]}")

        if self.client:
            try:
                return self._soften_with_llm(original_prompt, error_message)
            except Exception as e:
                print(f"[SOFTENER] LLM softening failed ({e}), using dictionary fallback")

        return self._soften_with_dictionary(original_prompt)

    def _soften_with_llm(self, original_prompt: str, error_message: str) -> str:
        """Use LLM to intelligently rewrite the prompt."""
        system_prompt = """You are a prompt safety editor for AI video generation.
A video generation API rejected the prompt below due to content policy violation.

Your task: rewrite the prompt keeping the SAME narrative, characters, emotions, plot,
and visual style — but make it safe for content moderation.

Rules:
- Replace explicit violence → dramatic tension, implied danger, shadows, silhouettes
- Replace weapons → neutral objects or remove
- Replace gore/blood → atmospheric lighting effects (red glow, shadows)
- Add safety anchors: "cinematic professional production", "artistic", "dramatic"
- Keep English language throughout
- Keep all structured audio (SFX:/Ambient:/Music:) sections intact
- Keep all technical parameters (aspect ratio, resolution, negative prompt)
- Keep camera movements and lighting descriptions
- Keep character descriptions and dialogue (colon syntax)
- Output ONLY the rewritten prompt, nothing else — no explanations, no quotes"""

        user_msg = f"Rejection reason: {error_message}\n\nOriginal prompt:\n{original_prompt}"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=1500,
            timeout=30,
        )

        softened = response.choices[0].message.content.strip()

        # Remove any wrapping quotes the LLM might add
        if softened.startswith('"') and softened.endswith('"'):
            softened = softened[1:-1]

        print(f"[SOFTENER] LLM softened prompt ({len(original_prompt)} → {len(softened)} chars)")
        return softened

    def _soften_with_dictionary(self, original_prompt: str) -> str:
        """Fallback: dictionary-based word replacement + safety prefix."""
        softened = original_prompt

        for word, replacement in _SOFTEN_REPLACEMENTS.items():
            softened = re.sub(
                rf'\b{re.escape(word)}\b',
                replacement,
                softened,
                flags=re.IGNORECASE,
            )

        # Add safety prefix if not already there
        if "cinematic professional" not in softened.lower():
            softened = _SAFETY_PREFIX + softened

        print(f"[SOFTENER] Dictionary softened prompt ({len(original_prompt)} → {len(softened)} chars)")
        return softened


# Detection helpers

MODERATION_KEYWORDS = (
    "moderation",
    "content policy",
    "safety",
    "blocked",
    "invalid prompt",
    "unsafe",
    "violat",
    "prohibited",
    "not allowed",
    "policy violation",
)


def is_moderation_error(error_message: str) -> bool:
    """Check if an error message indicates content moderation rejection."""
    lower = error_message.lower()
    return any(kw in lower for kw in MODERATION_KEYWORDS)


# Singleton
_softener: Optional[PromptSoftener] = None


def get_prompt_softener() -> PromptSoftener:
    """Get or create the prompt softener singleton."""
    global _softener
    if _softener is None:
        _softener = PromptSoftener()
    return _softener
