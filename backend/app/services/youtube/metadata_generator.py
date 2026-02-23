"""
LLM-powered YouTube metadata generation (title, description, tags).
"""
import json
from typing import Dict, List, Optional
from app.ai_orchestrator.llm_client import LLMClient


class MetadataGenerator:
    """Generate optimized YouTube Shorts metadata via LLM."""

    def __init__(self):
        self.llm_client = LLMClient()

    def generate_metadata(
        self,
        story_idea: str,
        genre: str = "",
        target_audience: str = "18-35 year olds",
    ) -> Dict:
        """
        Generate YouTube-optimized title, description, and tags.

        Returns:
            {
                "title": str,
                "description": str,
                "tags": List[str],
                "hashtags": List[str]
            }
        """
        system_prompt = """You are a YouTube Shorts SEO expert.
Generate viral-optimized metadata for a short-form video.
The title should be attention-grabbing and under 100 characters.
The description should include relevant keywords and be engaging.
Tags should be relevant for YouTube search.
Return valid JSON."""

        user_prompt = f"""Generate YouTube Shorts metadata for this video:

Story/Content: {story_idea}
Genre: {genre or 'general'}
Target Audience: {target_audience}

Return JSON:
{{
  "title": "Catchy title under 100 chars",
  "description": "Engaging description with keywords (up to 500 chars)",
  "tags": ["tag1", "tag2", "tag3", "...up to 30 tags"],
  "hashtags": ["#shorts", "#viral", "...up to 5 hashtags"]
}}"""

        try:
            result = self.llm_client.generate_structured_output(system_prompt, user_prompt)
            # Ensure title is within limits
            title = result.get("title", "Untitled Short")[:100]
            description = result.get("description", "")
            tags = result.get("tags", [])[:30]
            hashtags = result.get("hashtags", ["#shorts"])[:5]

            # Append hashtags to description
            hashtag_text = " ".join(hashtags)
            if hashtag_text:
                description = f"{description}\n\n{hashtag_text}"

            return {
                "title": title,
                "description": description[:5000],
                "tags": tags,
                "hashtags": hashtags,
            }
        except Exception as e:
            print(f"[YOUTUBE] Metadata generation error: {e}")
            return {
                "title": story_idea[:100] if story_idea else "Short Video",
                "description": story_idea or "",
                "tags": ["shorts", "viral", genre] if genre else ["shorts", "viral"],
                "hashtags": ["#shorts"],
            }

    def generate_from_trend(
        self,
        title: str,
        description: str = "",
        keywords: Optional[List[str]] = None,
        source: str = "",
        view_count: Optional[int] = None,
        velocity: float = 0.0,
        genre: str = "drama",
    ) -> Dict:
        """
        Analyze a viral trend and generate SEO-optimized metadata
        for a similar new video.

        Returns:
            {
                "title": str,
                "description": str,
                "tags": List[str],
                "hashtags": List[str],
                "idea_text": str,
                "genre": str,
            }
        """
        kw_text = ", ".join(keywords[:20]) if keywords else "none"
        views_text = f"{view_count:,}" if view_count else "unknown"

        system_prompt = """You are a YouTube Shorts viral content strategist and SEO expert.
You analyze trending videos and generate metadata for SIMILAR new videos
that can ride the same trend wave. Your goal is maximum discoverability and views.
Return valid JSON only."""

        user_prompt = f"""Analyze this viral trend and generate SEO-optimized metadata for a SIMILAR new short video:

ORIGINAL TREND:
- Title: {title}
- Description: {description[:500] if description else 'N/A'}
- Keywords: {kw_text}
- Source: {source}
- Views: {views_text}
- Velocity: {velocity:.1f} views/hr
- Preferred genre: {genre}

Generate metadata for a NEW similar video that rides this trend. Return JSON:
{{
  "title": "SEO-optimized catchy title under 100 chars, must include trending keywords",
  "description": "Full YouTube description (300-500 chars) with keywords naturally woven in. End with relevant hashtags.",
  "tags": ["up to 30 relevant YouTube tags for maximum discoverability"],
  "hashtags": ["#shorts", "plus up to 4 more trending hashtags"],
  "idea_text": "2-3 sentence concept for the new video: what happens, the hook, the twist",
  "genre": "the most fitting genre for this content"
}}"""

        try:
            result = self.llm_client.generate_structured_output(system_prompt, user_prompt)

            seo_title = result.get("title", f"Trending: {title[:80]}")[:100]
            seo_description = result.get("description", "")
            tags = result.get("tags", [])[:30]
            hashtags = result.get("hashtags", ["#shorts"])[:5]
            idea_text = result.get("idea_text", f"A short video inspired by the trend: {title}")
            detected_genre = result.get("genre", genre)

            # Append hashtags to description if not already there
            hashtag_text = " ".join(hashtags)
            if hashtag_text and hashtag_text not in seo_description:
                seo_description = f"{seo_description}\n\n{hashtag_text}"

            return {
                "title": seo_title,
                "description": seo_description[:5000],
                "tags": tags,
                "hashtags": hashtags,
                "idea_text": idea_text,
                "genre": detected_genre,
            }
        except Exception as e:
            print(f"[YOUTUBE] generate_from_trend error: {e}")
            fallback_tags = ["shorts", "viral", "trending"]
            if keywords:
                fallback_tags.extend(keywords[:10])
            return {
                "title": f"Trending: {title[:85]}"[:100],
                "description": f"Inspired by: {title}\n\n{description[:300]}\n\n#shorts #viral",
                "tags": fallback_tags[:30],
                "hashtags": ["#shorts", "#viral"],
                "idea_text": f"A short video inspired by the viral trend: {title}",
                "genre": genre,
            }
