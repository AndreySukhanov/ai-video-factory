import json
import hashlib
from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.ai_orchestrator.llm_client import LLMClient
from app.models.trend import Trend, StoryIdea, TrendSnapshot
from .base import TrendSource, TrendItem
from .youtube_trends import YouTubeTrendsSource
from .google_trends import GoogleTrendsSource
from .tiktok_trends import TikTokTrendsSource
from app.core.config import settings


class TrendAnalyzer:
    """Orchestrates trend fetching and LLM analysis into story ideas."""

    def __init__(self):
        self.llm_client = LLMClient()
        self.sources: List[TrendSource] = []
        self._init_sources()

    def _init_sources(self):
        """Initialize available trend sources based on config."""
        # YouTube (requires API key)
        if settings.YOUTUBE_API_KEY:
            self.sources.append(YouTubeTrendsSource())

        # Google Trends (free, always available via RSS)
        self.sources.append(GoogleTrendsSource())

        # TikTok via Apify (leading signal for YouTube Shorts trends)
        # Note: ApifyScraper (YouTube via Apify) removed — duplicates YouTubeTrendsSource and wastes Apify credits
        if settings.APIFY_API_TOKEN:
            self.sources.append(TikTokTrendsSource())

        print(f"[TRENDS] Initialized {len(self.sources)} trend sources: "
              f"{[s.source_name for s in self.sources]}")

    @staticmethod
    def _trend_hash(title: str, source: str, url: str) -> str:
        """Generate stable hash for trend matching across fetches."""
        key = f"{title.lower().strip()}|{source}|{url}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def fetch_all_trends(self, db: Session, region: str = "US", category: str = "",
                         max_per_source: int = 20) -> List[Trend]:
        """Fetch trends from all sources. Clear old region data, insert fresh."""
        # Delete old trends for this region so the page always shows fresh data
        old_count = db.query(Trend).filter(Trend.region == region).delete()
        db.flush()
        if old_count:
            print(f"[TRENDS] Cleared {old_count} old trends for region {region}")

        all_trends = []

        for source in self.sources:
            try:
                items = source.fetch_trends(region=region, category=category,
                                            max_results=max_per_source)
                for item in items:
                    title_hash = self._trend_hash(item.title, item.source, item.url)

                    # Check if trend already exists (upsert by url+source+region)
                    existing = db.query(Trend).filter(
                        Trend.url == item.url,
                        Trend.source == item.source,
                        Trend.region == region,
                    ).first()

                    if existing:
                        old_velocity = existing.velocity_score or 0
                        existing.score = item.score
                        existing.velocity_score = item.velocity_score
                        existing.view_count = item.view_count
                        existing.published_at = item.published_at
                        existing.fetched_at = func.now()
                        existing.keywords_json = json.dumps(item.keywords)
                        if item.duration_sec and not existing.duration_sec:
                            existing.duration_sec = item.duration_sec

                        # Classify trend stage based on velocity change
                        if old_velocity > 0:
                            if item.velocity_score > old_velocity * 1.2:
                                existing.trend_stage = "rising"
                            elif item.velocity_score < old_velocity * 0.7:
                                existing.trend_stage = "declining"
                            else:
                                existing.trend_stage = "peaking"
                        else:
                            existing.trend_stage = "rising"

                        trend = existing
                    else:
                        trend = Trend(
                            title=item.title,
                            description=item.description,
                            source=item.source,
                            region=region,
                            category=item.category,
                            score=item.score,
                            velocity_score=item.velocity_score,
                            view_count=item.view_count,
                            published_at=item.published_at,
                            duration_sec=item.duration_sec or None,
                            trend_stage="rising",
                            keywords_json=json.dumps(item.keywords),
                            url=item.url,
                        )
                        db.add(trend)

                    # Save snapshot for history tracking
                    snapshot = TrendSnapshot(
                        trend_title_hash=title_hash,
                        title=item.title,
                        source=item.source,
                        view_count=item.view_count,
                        velocity_score=item.velocity_score,
                        score=item.score,
                    )
                    db.add(snapshot)

                    all_trends.append(trend)
            except Exception as e:
                print(f"[TRENDS] Error fetching from {source.source_name}: {e}")

        # Prune old trends (older than 14 days)
        cutoff = datetime.utcnow() - timedelta(days=14)
        old_count = db.query(Trend).filter(Trend.fetched_at < cutoff).count()
        if old_count > 0:
            db.query(Trend).filter(Trend.fetched_at < cutoff).delete()
            print(f"[TRENDS] Pruned {old_count} old trends")

        # Prune old snapshots (older than 30 days)
        snap_cutoff = datetime.utcnow() - timedelta(days=30)
        db.query(TrendSnapshot).filter(TrendSnapshot.snapshot_at < snap_cutoff).delete()

        db.commit()
        for t in all_trends:
            db.refresh(t)

        print(f"[TRENDS] Saved {len(all_trends)} trends to DB")

        # Enrich top trends with competition analysis (Phase 6)
        self._enrich_with_competition(db, all_trends, region, top_n=5)

        return all_trends

    def _enrich_with_competition(self, db: Session, trends: List[Trend],
                                region: str, top_n: int = 5):
        """Add competition analysis to top N trends by velocity. Quota-conscious."""
        yt_source = None
        for s in self.sources:
            if isinstance(s, YouTubeTrendsSource):
                yt_source = s
                break

        if not yt_source:
            return

        # Sort by velocity, only analyze top_n
        sorted_trends = sorted(trends, key=lambda t: t.velocity_score or 0, reverse=True)

        for trend in sorted_trends[:top_n]:
            search_query = trend.title[:50]
            competition = yt_source.estimate_competition(search_query, region)
            trend.competition_level = competition

            # Opportunity = high velocity + low competition
            velocity_norm = min(1.0, (trend.velocity_score or 0) / 10000)
            trend.opportunity_score = round(velocity_norm * (1.0 - competition), 3)

        db.commit()
        for t in sorted_trends[:top_n]:
            db.refresh(t)

        print(f"[TRENDS] Enriched top {top_n} trends with competition data")

    def analyze_trends(self, db: Session, trends: List[Trend] = None,
                       max_ideas: int = 5, genre: str = "",
                       channel_niche: str = "", niche_keywords: list = None,
                       content_style: str = "") -> List[StoryIdea]:
        """Use LLM to generate story ideas from trends."""
        if trends is None:
            # Get latest trends, sorted by velocity
            trends = db.query(Trend).order_by(Trend.velocity_score.desc()).limit(30).all()

        if not trends:
            print("[TRENDS] No trends to analyze")
            return []

        # Build enriched trend summary for LLM
        trend_texts = []
        for t in trends:
            keywords = json.loads(t.keywords_json) if t.keywords_json else []
            parts = [f"- {t.title} (source: {t.source}, score: {t.score:.0f}"]
            if t.velocity_score:
                parts.append(f", velocity: {t.velocity_score:.0f} views/hr")
            if t.trend_stage and t.trend_stage != "unknown":
                parts.append(f", stage: {t.trend_stage}")
            if t.competition_level is not None:
                level = "high" if t.competition_level > 0.6 else ("medium" if t.competition_level > 0.3 else "low")
                parts.append(f", competition: {level}")
            if t.opportunity_score is not None:
                parts.append(f", opportunity: {t.opportunity_score:.0%}")
            parts.append(f", keywords: {', '.join(keywords[:5])})")
            trend_texts.append("".join(parts))

        trends_summary = "\n".join(trend_texts)
        genre_instruction = f"Focus on the genre: {genre}." if genre else "Choose the best genre for each idea."

        # Niche filter instructions
        niche_instruction = ""
        if channel_niche:
            niche_instruction += f"\nChannel niche: {channel_niche}. All ideas MUST fit this niche."
        if niche_keywords:
            niche_instruction += f"\nRelevant keywords to incorporate: {', '.join(niche_keywords)}."
        if content_style:
            niche_instruction += f"\nContent style: {content_style}. Match this visual/tonal style."

        system_prompt = """You are a viral YouTube Shorts content strategist and SEO expert.
Analyze trending topics and generate compelling micro-drama story ideas (30-60 second videos).
Each idea should be a complete mini-story that could go viral.

PRIORITIZE trends that are "rising" with low competition — these are the best opportunities.

TITLE PATTERNS that work on Shorts:
- "POV: [relatable situation]"
- "Wait for it..."
- "[Situation] Part X"
- "Nobody expected what happened next..."
- "What would you do if..."
- "The [adjective] [noun] that changed everything"

HOOK TYPES (first 3 seconds of video):
- question: Start with a provocative question
- shocking_stat: Open with a surprising fact or number
- pov: First-person perspective setup
- cliffhanger: Tease the ending at the start
- contrast: Show before/after or expectation vs reality

Return valid JSON."""

        user_prompt = f"""Based on these current trends (sorted by velocity/growth speed):

{trends_summary}

Generate {max_ideas} YouTube Shorts story ideas. {genre_instruction}{niche_instruction}

For EACH idea, also provide:
- A hook type for the first 3 seconds
- An SEO-optimized YouTube title (under 100 chars)
- 5-8 relevant YouTube tags
- 2 alternative angles (different hook/perspective)

Return JSON:
{{
  "ideas": [
    {{
      "idea_text": "Complete story idea description (2-3 sentences)",
      "genre": "drama|comedy|horror|thriller|romance|sci-fi|mystery",
      "virality_score": 0.0-1.0,
      "based_on_trends": ["trend title 1"],
      "hook_type": "question|shocking_stat|pov|cliffhanger|contrast",
      "suggested_title": "SEO-optimized YouTube title under 100 chars",
      "suggested_tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
      "variants": [
        {{
          "angle": "Alternative angle description",
          "hook_type": "different_hook",
          "suggested_title": "Alternative title"
        }},
        {{
          "angle": "Another angle description",
          "hook_type": "another_hook",
          "suggested_title": "Another title"
        }}
      ]
    }}
  ]
}}"""

        try:
            result = self.llm_client.generate_structured_output(system_prompt, user_prompt)
            ideas_data = result.get("ideas", [])
        except Exception as e:
            print(f"[TRENDS] LLM analysis error: {e}")
            ideas_data = []

        # Save story ideas to DB
        story_ideas = []
        trend_id = trends[0].id if trends else None

        for idea_data in ideas_data:
            idea = StoryIdea(
                trend_id=trend_id,
                idea_text=idea_data.get("idea_text", ""),
                genre=idea_data.get("genre", "drama"),
                virality_score=float(idea_data.get("virality_score", 0.5)),
                status="pending",
                hook_type=idea_data.get("hook_type"),
                suggested_title=idea_data.get("suggested_title"),
                suggested_tags_json=json.dumps(idea_data.get("suggested_tags", [])),
                variants_json=json.dumps(idea_data.get("variants", [])),
            )
            db.add(idea)
            story_ideas.append(idea)

        db.commit()
        for idea in story_ideas:
            db.refresh(idea)

        print(f"[TRENDS] Generated {len(story_ideas)} story ideas")

        # Notify via Telegram
        if story_ideas:
            try:
                from app.services.monitoring import notify_new_ideas
                notify_new_ideas(story_ideas)
            except Exception as e:
                print(f"[TRENDS] Notification error: {e}")

        return story_ideas


# Job handler for RQ worker
def handle_fetch_trends_job(region: str = "US", category: str = "",
                            max_per_source: int = 20, max_ideas: int = 5,
                            genre: str = ""):
    """RQ job handler: fetch trends and generate ideas."""
    from app.core.db import SessionLocal
    db = SessionLocal()
    try:
        analyzer = TrendAnalyzer()
        trends = analyzer.fetch_all_trends(db, region=region, category=category,
                                           max_per_source=max_per_source)
        if trends:
            analyzer.analyze_trends(db, trends=trends, max_ideas=max_ideas, genre=genre)
    finally:
        db.close()
