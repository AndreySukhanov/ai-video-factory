import os
import re
from typing import Dict, Any
from app.core.config import settings
import json

# Strip ```json ... ``` markdown fences that Claude likes to wrap JSON in
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_json_fences(text: str) -> str:
    return _JSON_FENCE_RE.sub("", text.strip()).strip()


class LLMClient:
    """
    Client for interacting with LLM.

    Provider priority (auto):
      1. LaoZhang + Claude Opus (if LAOZHANG_API_KEY set)
      2. OpenRouter + DeepSeek V4 (if OPENROUTER_API_KEY set)
      3. OpenAI gpt-4-turbo (if OPENAI_API_KEY set)
      4. Mock

    Override via env: LLM_PROVIDER=laozhang|openrouter|openai, LLM_MODEL=<model_id>
    """

    def __init__(self):
        provider = (settings.LLM_PROVIDER or "").lower()
        if not provider:
            if settings.LAOZHANG_API_KEY:
                provider = "laozhang"
            elif settings.OPENROUTER_API_KEY:
                provider = "openrouter"
            elif settings.OPENAI_API_KEY:
                provider = "openai"

        self.provider = provider
        self.use_real_api = provider in ("laozhang", "openrouter", "openai")
        self.is_claude = False

        if not self.use_real_api:
            return

        try:
            from openai import OpenAI
        except ImportError:
            print("[LLM CLIENT] Warning: openai package not installed, using mock")
            self.use_real_api = False
            return

        if provider == "laozhang":
            self.client = OpenAI(
                api_key=settings.LAOZHANG_API_KEY,
                base_url=settings.LAOZHANG_BASE_URL,
            )
            self.model = settings.LLM_MODEL or "claude-opus-4-8"
            self.is_claude = self.model.startswith("claude")
            print(f"[LLM CLIENT] Using LaoZhang with {self.model}")
        elif provider == "openrouter":
            self.client = OpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
            )
            self.model = settings.LLM_MODEL or "deepseek/deepseek-v4-pro"
            print(f"[LLM CLIENT] Using OpenRouter with {self.model}")
        else:  # openai
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.LLM_MODEL or "gpt-4-turbo-preview"
            print(f"[LLM CLIENT] Using OpenAI with {self.model}")

    def generate_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Dict[str, Any] = None,
        images_base64: list[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output from LLM.

        If `images_base64` is given (list of base64-encoded JPEG strings), the user
        message is sent as multimodal content (Opus 4.8 and OpenAI Vision will see
        the images directly). LaoZhang passes through OpenAI-style image_url content.
        """
        if not self.use_real_api:
            print("[LLM CLIENT] Using mock response (no API key)")
            return self._mock_response(user_prompt)

        try:
            print(f"[LLM CLIENT] Calling {self.model}{' (multimodal)' if images_base64 else ''}...")

            if images_base64:
                user_content: Any = [{"type": "text", "text": user_prompt}]
                for b64 in images_base64:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    })
            else:
                user_content = user_prompt

            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.7,
                "timeout": 180 if images_base64 else 90,
            }
            # Claude on LaoZhang ignores response_format and wraps in markdown.
            # Instead nudge it via system prompt + parse with fence stripping.
            if self.is_claude:
                kwargs["messages"][0]["content"] = (
                    f"{system_prompt}\n\n"
                    "Respond with a single JSON object. Do not wrap it in markdown fences."
                )
                kwargs["max_tokens"] = 4096
            else:
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)
            raw = response.choices[0].message.content
            result = json.loads(_strip_json_fences(raw))
            print(f"[LLM CLIENT] Response received")
            return result

        except Exception as e:
            print(f"[LLM CLIENT] API error: {e}, falling back to mock")
            return self._mock_response(user_prompt)
    
    def _mock_response(self, prompt: str) -> Dict[str, Any]:
        """Fallback mock response"""
        if "idea" in prompt.lower() or "series" in prompt.lower():
            return {
                "series_title": "Generated Series",
                "logline": "A compelling story based on your idea",
                "characters": [
                    {"name": "Alex", "role": "main", "description": "The protagonist"},
                    {"name": "Jordan", "role": "support", "description": "The sidekick"}
                ],
                "episodes": [
                    {
                        "number": 1,
                        "title": "Episode 1",
                        "hook": "An intriguing start",
                        "synopsis": "The story begins"
                    }
                ]
            }
        elif "synopsis" in prompt.lower() or "script" in prompt.lower():
            return {
                "scenes": [
                    {
                        "scene_number": 1,
                        "duration_sec": 5,
                        "what_happens": "Opening scene",
                        "dialogue": [{"character": "Alex", "text": "Hello!"}]
                    }
                ]
            }
        elif "visual" in prompt.lower() or "prompt" in prompt.lower():
            return {
                "visual_prompt": "cinematic 9:16 shot, high quality, detailed",
                "style": "realistic"
            }
        return {}
