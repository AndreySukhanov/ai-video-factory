import json
from app.ai_orchestrator.llm_client import LLMClient

class StoryAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_series_structure(self, idea: str, genre: str, target_platform: str, episodes_count: int, episode_duration: int) -> dict:
        system_prompt = "You are a professional screenwriter for vertical micro-dramas (TikTok/Reels). Generate story structures in valid JSON format."
        
        user_prompt = f"""
        Create a series structure based on this idea: "{idea}"
        Genre: {genre}
        Platform: {target_platform}
        Episodes: {episodes_count}
        Episode Duration: {episode_duration} sec

        Return valid JSON with this structure:
        {{
          "series_title": "...",
          "logline": "...",
          "characters": [
            {{"name": "...", "role": "main|support", "description": "..."}}
          ],
          "episodes": [
            {{
              "number": 1,
              "title": "...",
              "hook": "...",
              "synopsis": "..."
            }}
          ]
        }}
        """
        
        response = self.llm.generate_structured_output(system_prompt, user_prompt)
        return response if response else {}
