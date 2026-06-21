from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.db import get_db
from app.models.trend import Trend, StoryIdea, TrendSnapshot
from app.schemas.trend import (
    TrendRead, TrendFetchRequest, TrendFetchResponse,
    StoryIdeaRead, TrendAnalyzeRequest, TrendAnalyzeResponse,
    IdeaApproveResponse, IdeaGenerateRequest, IdeaGenerateResponse,
    TrendGenerateRequest, TrendGenerateResponse,
    NicheInfo, NichesResponse,
    TrendPatternRead, ExtractPatternResponse, CloneBriefResponse, CloneEpisode,
)
from app.models.trend_pattern import TrendPattern
from app.services.trendwatcher.trend_analyzer import TrendAnalyzer
from app.services.trendwatcher.niches import list_niches, resolve_lang

router = APIRouter()
_analyzer = None


def _get_analyzer() -> TrendAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = TrendAnalyzer()
    return _analyzer


@router.post("/fetch", response_model=TrendFetchResponse)
def fetch_trends(request: TrendFetchRequest, db: Session = Depends(get_db)):
    """Fetch trends from all configured sources and save to DB.

    If `niche` is provided (e.g. "astrology"), uses niche-specific hashtags/queries
    instead of `keywords`/defaults. Niches are defined in `app.services.trendwatcher.niches`.
    """
    analyzer = _get_analyzer()
    trends = analyzer.fetch_all_trends(
        db, region=request.region, category=request.category,
        max_per_source=request.max_per_source,
        keywords=request.keywords,
        platforms=request.platforms,
        niche=request.niche,
    )
    return TrendFetchResponse(
        success=True,
        count=len(trends),
        trends=[TrendRead.model_validate(t) for t in trends]
    )


@router.get("/niches", response_model=NichesResponse)
def get_niches(lang: str = Query("en", description="Display language: en | ru")):
    """Return list of available niches with localized display names."""
    niches = list_niches(lang=lang)
    return NichesResponse(niches=[NicheInfo(**n) for n in niches])


@router.get("/", response_model=List[TrendRead])
def list_trends(
    source: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    niche: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),  # velocity, viral_coef, score
    anomaly_only: bool = Query(False),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List trends with optional filtering and sorting."""
    query = db.query(Trend)
    if source:
        query = query.filter(Trend.source == source)
    if region:
        query = query.filter(Trend.region == region)
    if category:
        query = query.filter(Trend.category == category)
    if niche:
        query = query.filter(Trend.niche == niche)
    if anomaly_only:
        query = query.filter(Trend.is_anomaly == 1)

    if sort_by == "viral_coef":
        query = query.order_by(Trend.viral_coef.desc().nullslast())
    elif sort_by == "score":
        query = query.order_by(Trend.score.desc())
    else:
        query = query.order_by(Trend.velocity_score.desc(), Trend.fetched_at.desc())

    trends = query.offset(skip).limit(limit).all()
    # Convert is_anomaly int to bool for schema
    for t in trends:
        t.is_anomaly = bool(t.is_anomaly)
    return trends


@router.get("/history/{trend_id}")
def get_trend_history(trend_id: int, db: Session = Depends(get_db)):
    """Get velocity history snapshots for a trend."""
    import hashlib

    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")

    key = f"{trend.title.lower().strip()}|{trend.source}|{trend.url}"
    title_hash = hashlib.sha256(key.encode()).hexdigest()[:32]

    snapshots = db.query(TrendSnapshot).filter(
        TrendSnapshot.trend_title_hash == title_hash
    ).order_by(TrendSnapshot.snapshot_at.asc()).all()

    return {
        "trend_id": trend.id,
        "title": trend.title,
        "trend_stage": trend.trend_stage,
        "snapshots": [
            {
                "view_count": s.view_count,
                "velocity_score": s.velocity_score,
                "score": s.score,
                "snapshot_at": s.snapshot_at.isoformat() if s.snapshot_at else None,
            }
            for s in snapshots
        ]
    }


@router.post("/analyze", response_model=TrendAnalyzeResponse)
def analyze_trends(request: TrendAnalyzeRequest, db: Session = Depends(get_db)):
    """Analyze recent trends with LLM to generate story ideas."""
    analyzer = _get_analyzer()
    ideas = analyzer.analyze_trends(
        db, max_ideas=request.max_ideas, genre=request.genre
    )
    return TrendAnalyzeResponse(
        success=True,
        count=len(ideas),
        ideas=[StoryIdeaRead.model_validate(i) for i in ideas]
    )


@router.get("/ideas", response_model=List[StoryIdeaRead])
def list_ideas(
    status: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List story ideas with optional filtering."""
    query = db.query(StoryIdea)
    if status:
        query = query.filter(StoryIdea.status == status)
    if genre:
        query = query.filter(StoryIdea.genre == genre)
    query = query.order_by(StoryIdea.created_at.desc())
    ideas = query.offset(skip).limit(limit).all()
    return ideas


@router.post("/ideas/{idea_id}/approve", response_model=IdeaApproveResponse)
def approve_idea(idea_id: int, db: Session = Depends(get_db)):
    """Approve a story idea for generation."""
    idea = db.query(StoryIdea).filter(StoryIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    if idea.status != "pending":
        raise HTTPException(status_code=400, detail=f"Idea status is '{idea.status}', expected 'pending'")

    idea.status = "approved"
    db.commit()
    db.refresh(idea)
    return IdeaApproveResponse(success=True, idea=StoryIdeaRead.model_validate(idea))


@router.post("/ideas/{idea_id}/generate", response_model=IdeaGenerateResponse)
def generate_from_idea(idea_id: int, request: IdeaGenerateRequest = None,
                       db: Session = Depends(get_db)):
    """Approve idea, create project, and start video generation."""
    idea = db.query(StoryIdea).filter(StoryIdea.id == idea_id).first()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    if idea.status not in ("pending", "approved"):
        raise HTTPException(status_code=400,
                            detail=f"Idea status is '{idea.status}', must be 'pending' or 'approved'")

    # Mark as approved if pending
    if idea.status == "pending":
        idea.status = "approved"

    # Create a project from the idea
    from app.models import Project, Job
    import json

    project = Project(
        title=f"Trend: {idea.idea_text[:50]}...",
        logline=idea.idea_text,
        genre=idea.genre or (request.genre if request else "drama"),
        target_platform="youtube_shorts",
        status="draft",
    )
    db.add(project)
    db.flush()

    idea.project_id = project.id
    idea.status = "generated"

    # Create generation job
    job = Job(
        type="GENERATE_STORY",
        status="queued",
        payload_json=json.dumps({
            "project_id": project.id,
            "idea": idea.idea_text,
            "genre": idea.genre,
            "model": request.model if request else "laozhang",
            "duration": request.duration if request else 6,
            "aspect_ratio": request.aspect_ratio if request else "9:16",
            "from_trend": True,
        }),
    )
    db.add(job)
    db.commit()
    db.refresh(idea)
    db.refresh(project)
    db.refresh(job)

    # Enqueue the job
    try:
        from app.services.generation_service import enqueue_job
        enqueue_job(job.id)
    except Exception as e:
        print(f"[TRENDS] Failed to enqueue job: {e}")

    return IdeaGenerateResponse(
        success=True,
        idea=StoryIdeaRead.model_validate(idea),
        project_id=project.id,
        message=f"Project created (ID: {project.id}), generation job queued"
    )


@router.post("/{trend_id}/generate", response_model=TrendGenerateResponse)
def generate_from_trend(trend_id: int, request: TrendGenerateRequest = None,
                        db: Session = Depends(get_db)):
    """Analyze a trend with AI and generate a similar video project with SEO metadata."""
    import json

    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")

    # Parse keywords
    keywords = []
    try:
        keywords = json.loads(trend.keywords_json or "[]")
    except Exception:
        pass

    # Generate SEO metadata from trend
    from app.services.youtube.metadata_generator import MetadataGenerator
    gen = MetadataGenerator()
    meta = gen.generate_from_trend(
        title=trend.title,
        description=trend.description or "",
        keywords=keywords,
        source=trend.source,
        view_count=trend.view_count,
        velocity=trend.velocity_score or 0.0,
        genre=request.genre if request else "drama",
    )

    seo_title = meta["title"]
    seo_description = meta["description"]
    seo_tags = meta["tags"]
    seo_hashtags = meta["hashtags"]
    idea_text = meta["idea_text"]
    genre = meta["genre"]

    # Create StoryIdea
    idea = StoryIdea(
        trend_id=trend.id,
        idea_text=idea_text,
        genre=genre,
        virality_score=min((trend.velocity_score or 0) / 10000, 1.0),
        status="generated",
        suggested_title=seo_title,
        suggested_tags_json=json.dumps(seo_tags),
    )
    db.add(idea)
    db.flush()

    # Calculate total episodes from original video duration
    import math
    episode_duration = request.duration if request else 6
    original_duration = trend.duration_sec or 0
    if original_duration > 0:
        total_episodes = max(1, math.ceil(original_duration / episode_duration))
    else:
        total_episodes = 1

    # Create Project with SEO fields (no auto-generation — user reviews and generates manually)
    from app.models import Project

    project = Project(
        title=seo_title,
        logline=idea_text,
        genre=genre,
        target_platform="youtube_shorts",
        total_episodes=total_episodes,
        episode_duration_sec=episode_duration,
        status="draft",
        seo_title=seo_title,
        seo_description=seo_description,
        seo_tags_json=json.dumps(seo_tags),
    )
    db.add(project)
    db.flush()

    idea.project_id = project.id

    db.commit()
    db.refresh(idea)
    db.refresh(project)

    return TrendGenerateResponse(
        success=True,
        project_id=project.id,
        idea_id=idea.id,
        seo_title=seo_title,
        seo_description=seo_description,
        seo_tags=seo_tags,
        seo_hashtags=seo_hashtags,
        message=f"Project {project.id} created from trend '{trend.title[:50]}'"
    )


# ─── Phase 2: Deep pattern extraction ─────────────────────────────────────────

@router.post("/{trend_id}/extract-pattern", response_model=ExtractPatternResponse)
def extract_trend_pattern(trend_id: int, db: Session = Depends(get_db)):
    """Extract structural pattern (hook, story_beats, characters, title_formula, ...) from a trend.

    Pipeline: transcript (YouTube captions / Whisper) → LLM-structured analysis → TrendPattern row.
    Idempotent: re-running upserts on (trend_id).
    """
    from app.services.trendwatcher.pattern_extractor import extract_pattern

    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")

    try:
        pattern = extract_pattern(trend, db)
        return ExtractPatternResponse(success=True, pattern=TrendPatternRead.model_validate(pattern))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ExtractPatternResponse(success=False, error=f"Pattern extraction failed: {e}")


@router.get("/{trend_id}/pattern", response_model=ExtractPatternResponse)
def get_trend_pattern(trend_id: int, db: Session = Depends(get_db)):
    """Return previously extracted pattern for a trend (if any)."""
    pattern = db.query(TrendPattern).filter(TrendPattern.trend_id == trend_id).first()
    if not pattern:
        return ExtractPatternResponse(success=False, error="No pattern extracted yet for this trend")
    return ExtractPatternResponse(success=True, pattern=TrendPatternRead.model_validate(pattern))


# ─── Phase 3: Clone-to-brief ──────────────────────────────────────────────────

@router.post("/{trend_id}/clone-brief", response_model=CloneBriefResponse)
def clone_trend_to_brief(trend_id: int, db: Session = Depends(get_db)):
    """Return a pre-filled generation brief based on the trend's extracted pattern.

    Auto-extracts the pattern if missing. Frontend uses this to pre-fill /generate wizard.
    """
    from app.services.trendwatcher.pattern_extractor import extract_pattern

    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")

    pattern = db.query(TrendPattern).filter(TrendPattern.trend_id == trend_id).first()
    if not pattern:
        try:
            pattern = extract_pattern(trend, db)
        except Exception as e:
            return CloneBriefResponse(success=False, error=f"Pattern extraction failed: {e}")

    # Convert story_beats → episode prompts directly. Each beat becomes one episode.
    # No second LLM call: the beats are already structured.
    import json as _json
    beats: list[dict] = []
    try:
        beats = _json.loads(pattern.story_beats_json or "[]") or []
    except Exception:
        beats = []

    anchor = pattern.anchor_prompt or ""
    char_card = pattern.character_card or ""
    episodes: list[CloneEpisode] = []
    for i, beat in enumerate(beats[:8], start=1):
        action = (beat.get("what_happens") or "").strip()
        emotion = (beat.get("emotion") or "").strip()
        title = emotion.title() if emotion else f"Beat {i}"
        # Compose a Veo-ready prompt: ANCHOR (style/setting) + VARIABLE (action + emotion)
        prompt_parts = []
        if anchor:
            prompt_parts.append(anchor)
        if char_card:
            prompt_parts.append(f"Character: {char_card}")
        if action:
            prompt_parts.append(f"Action: {action}")
        if emotion:
            prompt_parts.append(f"Emotional tone: {emotion}")
        prompt_parts.append("9:16 vertical, cinematic, 6 seconds")
        episodes.append(CloneEpisode(
            number=i,
            title=title,
            synopsis=action,
            prompt=". ".join(p.rstrip(". ") for p in prompt_parts if p) + ".",
        ))

    # Wizard expects exactly N episodes; clamp episodes_count to what we actually have.
    episodes_count = len(episodes) if episodes else 5

    # Choose duration based on original (clamp to wizard limits 4-8 sec per episode)
    duration_per_episode = 6
    if trend.duration_sec and 4 <= trend.duration_sec / 5 <= 8:
        duration_per_episode = max(4, min(8, int(trend.duration_sec / 5)))

    return CloneBriefResponse(
        success=True,
        idea=pattern.adaptation_brief or trend.title,
        genre="drama",
        episodes_count=episodes_count,
        duration=duration_per_episode,
        aspect_ratio="9:16",
        anchor_prompt=pattern.anchor_prompt,
        character_card=pattern.character_card,
        suggested_title=trend.title,
        title_formula=pattern.title_formula,
        viral_mechanic=pattern.viral_mechanic,
        episodes=episodes,
    )
