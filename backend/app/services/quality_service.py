import json
from app.models import Asset, Episode
from app.ai_orchestrator.llm_client import LLMClient

class QualityService:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def check_technical_quality(self, asset: Asset) -> dict:
        # Mock technical check
        return {
            "technical_ok": True,
            "duration_ok": True,
            "aspect_ratio_ok": True
        }

    def check_content_quality(self, episode: Episode, assets: list[Asset]) -> dict:
        # Mock content check via LLM
        prompt = f"""
        Evaluate the quality of the generated video clips for this episode.
        Episode: {episode.title}
        Synopsis: {episode.synopsis}
        Assets: {len(assets)} clips.

        Return strictly valid JSON:
        {{
          "overall_score": 0.85,
          "coherence": 0.9,
          "mood_match": 0.8,
          "comments": "Good match."
        }}
        """
        response = self.llm.generate_text(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"overall_score": 0.0, "comments": "Failed to evaluate"}
