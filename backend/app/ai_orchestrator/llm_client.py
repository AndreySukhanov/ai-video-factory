import os
from typing import Dict, Any
from app.core.config import settings
import json

class LLMClient:
    """
    Client for interacting with OpenAI LLM
    """
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.use_real_api = bool(self.api_key)
        
        if self.use_real_api:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                print("Warning: openai package not installed, using mock")
                self.use_real_api = False
    
    def generate_structured_output(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output from LLM
        """
        if not self.use_real_api:
            print("Using mock LLM response (no API key)")
            return self._mock_response(user_prompt)
        
        try:
            print(f"Calling OpenAI API...")
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            print(f"OpenAI API response received")
            return result
            
        except Exception as e:
            print(f"OpenAI API error: {e}, falling back to mock")
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
