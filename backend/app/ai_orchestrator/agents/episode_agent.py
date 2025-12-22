import json
from app.ai_orchestrator.llm_client import LLMClient

class EpisodeAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_script(self, synopsis: str, characters: list, duration_sec: int) -> dict:
        system_prompt = "You are a professional screenwriter. Generate episode scripts in valid JSON format."
        
        user_prompt = f"""
        Write a script for a micro-drama episode.
        Synopsis: {synopsis}
        Characters: {json.dumps(characters)}
        Duration: {duration_sec} seconds.

        Split into 2-4 scenes.
        Return valid JSON:
        {{
          "episode_number": 1,
          "scenes": [
            {{
              "scene_number": 1,
              "duration_sec": 7,
              "what_happens": "...",
              "dialogue": [
                {{"character": "Name", "text": "..."}}
              ]
            }}
          ]
        }}
        """
        response = self.llm.generate_structured_output(system_prompt, user_prompt)
        return response if response else {}
