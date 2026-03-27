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
from .instagram_reels import InstagramReelsTrendWatcher
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

        # Instagram Reels + TikTok via Apify (primary viral signal sources)
        if settings.APIFY_API_TOKEN:
            self.sources.append(InstagramReelsTrendWatcher())
            self.sources.append(TikTokTrendsSource())

        print(f"[TRENDS] Initialized {len(self.sources)} trend sources: "
              f"{[s.source_name for s in self.sources]}")

    @staticmethod
    def _trend_hash(title: str, source: str, url: str) -> str:
        """Generate stable hash for trend matching across fetches."""
        key = f"{title.lower().strip()}|{source}|{url}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def fetch_all_trends(self, db: Session, region: str = "US", category: str = "",
                         max_per_source: int = 20, keywords: List[str] = None) -> List[Trend]:
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
                                            max_results=max_per_source,
                                            keywords=keywords or [])
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
                        if item.thumbnail_url and not existing.thumbnail_url:
                            existing.thumbnail_url = item.thumbnail_url
                        ct = getattr(item, 'content_type', None)
                        if ct and ct != 'other':
                            existing.content_type = ct
                        if item.subscriber_count is not None:
                            existing.subscriber_count = item.subscriber_count
                        if item.viral_coef is not None:
                            existing.viral_coef = item.viral_coef
                        existing.is_anomaly = 1 if item.is_anomaly else 0
                        if item.matched_keyword:
                            existing.matched_keyword = item.matched_keyword

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
                            thumbnail_url=item.thumbnail_url or None,
                            trend_stage="rising",
                            keywords_json=json.dumps(item.keywords),
                            url=item.url,
                            content_type=getattr(item, 'content_type', 'other'),
                            subscriber_count=item.subscriber_count,
                            viral_coef=item.viral_coef,
                            is_anomaly=1 if item.is_anomaly else 0,
                            matched_keyword=item.matched_keyword,
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

    # Content types that are reproducible with AI video generation
    ACTIONABLE_TYPES = {"ai_generated", "animation", "story", "skit", "music_video"}

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

        # Filter: prioritize AI-reproducible content types
        actionable = [t for t in trends if getattr(t, 'content_type', 'other') in self.ACTIONABLE_TYPES]
        other = [t for t in trends if t not in actionable]
        # Use actionable first, then fill up with others (LLM will filter further)
        trends = (actionable + other)[:30]
        print(f"[TRENDS] Actionable: {len(actionable)}, other: {len(other)}, sending {len(trends)} to LLM")

        # Build enriched trend summary for LLM
        trend_texts = []
        for t in trends:
            keywords = json.loads(t.keywords_json) if t.keywords_json else []
            ct = getattr(t, 'content_type', 'other') or 'other'
            parts = [f"- {t.title} (source: {t.source}, type: {ct}, score: {t.score:.0f}"]
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

        system_prompt = """You are a viral pattern analyst and script generator for AI-generated YouTube Shorts (30-60s videos).

CRITICAL CONTEXT: We produce videos using AI video generation (Veo 3.1, Seedance, Kling).
We can create: animated characters, realistic human actors (AI-generated), cartoon worlds, dramatic scenes, nature, sci-fi environments, fantasy.
We CANNOT create: real celebrity likenesses, specific branded products, real news footage, specific real locations that need to be exact, live sports.

Your job: extract PATTERNS from trending AI-reproducible content and generate ideas that WE CAN PRODUCE with AI video tools.

CONTENT TYPES in the trends data:
- ai_generated: Already made with AI tools — HIGHEST priority, proven audience demand
- animation: Cartoon/animated content — we can recreate this perfectly
- story: Narrative-driven content (POV, drama, storytime) — great for AI actors
- skit: Comedy sketches — reproducible with AI characters
- music_video: Visual music content — AI can generate atmospheric visuals
- other: May or may not be reproducible — analyze carefully

A pattern = hook type + narrative formula + emotional trigger.

HOOK TYPES (first 3 seconds — the most critical moment):
- question: Start with a provocative question ("What would you do if...?")
- shocking_stat: Open with a surprising fact or number ("97% of people get this wrong")
- pov: First-person perspective setup ("POV: you just discovered...")
- cliffhanger: Tease the ending at the start ("I never expected what happened next")
- contrast: Show before/after or expectation vs reality
- mistake_warning: "Stop doing X!" or "This mistake is costing you..."
- pattern_interrupt: Unexpected visual or statement that breaks scrolling autopilot
- results_preview: Show the end result first, then the journey
- countdown: "3 things you didn't know about..." — listicle hooks
- authority: Establish credibility fast ("As a doctor / after 10 years of...")
- emotional: Raw emotional moment that creates instant empathy
- curiosity_gap: Incomplete info that demands watching ("She didn't know what was behind the door")

NARRATIVE FORMULAS:
- Hook → Conflict → Twist → CTA
- Hook → Problem → Solution → CTA
- Hook → Build-up → Payoff
- Hook → Contrast → Reveal → CTA
- Hook → List (3 items) → Surprise Item → CTA

WORKFLOW:
1. Focus on trends with type: ai_generated, animation, story, skit — these are proven to work AND we can produce them
2. Extract PATTERNS (recurring hooks, emotions, narrative arcs) from those trends
3. Generate ideas that apply those patterns — every idea MUST be producible with AI video generation
4. Skip trends about news, real celebrities, product reviews, sports — we cannot reproduce those

PRIORITIZE: "rising" stage + low competition + ai_generated/animation/story type.

REGENERABILITY: ALL ideas should be "yes" (fully AI-producible). If you can't make an idea AI-producible, don't include it.

Return valid JSON."""

        user_prompt = f"""Based on these current trends (sorted by velocity/growth speed):

{trends_summary}

Generate {max_ideas} YouTube Shorts story ideas. {genre_instruction}{niche_instruction}

FIRST identify 2-3 top patterns from the trends, THEN generate ideas applying those patterns.

For EACH idea, provide:
- A hook type (one of 12 types)
- A narrative structure formula
- An emotional trigger
- Regenerability assessment
- An SEO-optimized YouTube title (under 100 chars)
- 5-8 relevant YouTube tags
- 2 alternative angles

Return JSON:
{{
  "patterns_found": ["pattern description 1", "pattern description 2"],
  "ideas": [
    {{
      "idea_text": "Complete story idea description (2-3 sentences)",
      "genre": "drama|comedy|horror|thriller|romance|sci-fi|mystery",
      "virality_score": 0.0-1.0,
      "based_on_trends": ["trend title 1"],
      "hook_type": "question|shocking_stat|pov|cliffhanger|contrast|mistake_warning|pattern_interrupt|results_preview|countdown|authority|emotional|curiosity_gap",
      "narrative_structure": "Hook → Conflict → Twist → CTA",
      "emotional_trigger": "curiosity|fear|surprise|empathy|outrage",
      "regenerable": "yes|no: requires real person|no: visual only|no: copyrighted content",
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
      ],
      "analysis": {{
        "hook_system": {{
          "text_hook": {{"strategy": "curiosity_gap", "on_screen_text": "exact hook text"}},
          "audio_hook": {{"first_phrase": "opening spoken line"}},
          "visual_hook": {{"type": "bold_text_overlay|shocking_visual|beauty_shot", "description": "what viewer sees first"}}
        }},
        "timeline_structure": {{
          "hook": {{"timing": "0-3s", "description": "what happens"}},
          "plot": {{"timing": "3-54s", "description": "main content"}},
          "cta": {{"timing": "54-60s", "description": "call to action"}}
        }},
        "abstract_blueprint": {{
          "formula_name": "short name like 'Shock-Reveal-CTA'",
          "abstract_formula": "Show X → Reveal Y → CTA",
          "visual_skeleton": "how to visually replicate this in any niche"
        }},
        "visual_search_assets": {{
          "visual_tags_en": ["tag1 in English", "tag2", "tag3", "tag4", "tag5"],
          "dominant_colors": ["#hex1", "#hex2"],
          "setting_location": "indoor office|outdoor city|fantasy world|etc"
        }},
        "adaptation_potential": {{
          "suitable_niches": ["niche1", "niche2"],
          "adaptation_logic": "why this formula works across niches"
        }},
        "viral_formula": "one-liner: Show shocking result → Explain → CTA",
        "lifespan": "evergreen|trending_now|seasonal",
        "is_universal_template": true
      }}
    }}
  ]
}}"""

        try:
            result = self.llm_client.generate_structured_output(system_prompt, user_prompt)
            ideas_data = result.get("ideas", [])
        except Exception as e:
            print(f"[TRENDS] LLM analysis error: {e}")
            ideas_data = []

        # Clear old ideas that have no linked project (pending, approved, or generated without project)
        old_ideas = db.query(StoryIdea).filter(
            StoryIdea.project_id.is_(None)
        ).delete()
        if old_ideas:
            print(f"[TRENDS] Cleared {old_ideas} old ideas without projects")

        # Save story ideas to DB
        story_ideas = []
        trend_id = trends[0].id if trends else None

        for idea_data in ideas_data:
            analysis = idea_data.get("analysis")
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
                narrative_structure=idea_data.get("narrative_structure"),
                regenerable=idea_data.get("regenerable"),
                analysis_json=json.dumps(analysis) if analysis else None,
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
