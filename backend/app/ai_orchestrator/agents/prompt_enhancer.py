"""
Prompt Enhancer Agent - улучшает пользовательские промты для видео генерации
через LLM, добавляя профессиональные кинематографические детали.
"""
import json
from typing import Optional
from app.core.config import settings


class PromptEnhancer:
    """
    Улучшает простые промты пользователя для генерации видео,
    добавляя детали камеры, освещения, стиля и качества.
    Использует OpenRouter с DeepSeek или OpenAI.
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
        duration: int = 4
    ) -> str:
        """
        Улучшает промт пользователя через LLM.
        """
        if not self.use_real_api or not self.client:
            return self._basic_enhance(user_prompt, aspect_ratio)
        
        system_prompt = """You are a professional prompt engineer for AI video generation (Veo 3, Runway, Pika).
Your task is to enhance user prompts to produce cinematic, high-quality vertical videos.

IMPORTANT RULES:
1. Keep the ORIGINAL meaning and subject of the user's prompt
2. Add professional cinematography terms (camera movement, lighting, style)
3. Specify shot composition appropriate for vertical video
4. Add quality enhancers (cinematic, film grain, shallow depth of field)
5. Keep the enhanced prompt concise but detailed (max 200 words)
6. ALWAYS respond in the SAME LANGUAGE as the user's original prompt
7. DO NOT add characters or elements not mentioned by user
8. Focus on visual quality, not story changes
9. Return ONLY JSON, nothing else"""

        format_info = {
            "9:16": "vertical mobile format, portrait orientation, close-up or medium shots work best",
            "16:9": "horizontal cinematic format, wide shots and establishing shots work well",
            "1:1": "square format, centered compositions, suitable for social media"
        }
        
        user_request = f"""Enhance this video generation prompt:

ORIGINAL PROMPT: "{user_prompt}"

VIDEO FORMAT: {aspect_ratio} ({format_info.get(aspect_ratio, 'vertical')})
DURATION: {duration} seconds

Return JSON with:
{{
  "enhanced_prompt": "Your improved cinematographic prompt here",
  "camera": "brief camera movement description",
  "lighting": "lighting style",
  "mood": "emotional mood"
}}"""

        try:
            print(f"[PROMPT ENHANCER] Calling {self.model}...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_request}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            # Try to extract JSON from response
            if "{" in content and "}" in content:
                json_str = content[content.find("{"):content.rfind("}")+1]
                result = json.loads(json_str)
            else:
                result = json.loads(content)
            
            if result and result.get("enhanced_prompt"):
                enhanced = result["enhanced_prompt"]
                print(f"[PROMPT ENHANCER] Original: {user_prompt[:50]}...")
                print(f"[PROMPT ENHANCER] Enhanced: {enhanced[:100]}...")
                return enhanced
            else:
                print("[PROMPT ENHANCER] No enhanced prompt in response, using basic enhance")
                return self._basic_enhance(user_prompt, aspect_ratio)
                
        except Exception as e:
            print(f"[PROMPT ENHANCER] Error: {e}, falling back to basic enhance")
            return self._basic_enhance(user_prompt, aspect_ratio)
    
    def _basic_enhance(self, prompt: str, aspect_ratio: str) -> str:
        """
        Базовое улучшение промта без GPT.
        Добавляет стандартные качественные модификаторы.
        """
        # Определяем ориентацию
        if aspect_ratio == "9:16":
            format_hint = "vertical mobile video, portrait orientation"
        elif aspect_ratio == "16:9":
            format_hint = "horizontal cinematic video, widescreen"
        else:
            format_hint = "square format video"
        
        # Добавляем качественные модификаторы
        quality_modifiers = [
            "cinematic",
            "high quality",
            "professional lighting",
            "shallow depth of field"
        ]
        
        # Собираем улучшенный промт
        enhanced = f"{prompt}. {format_hint}, {', '.join(quality_modifiers)}"
        
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

