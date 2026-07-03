import hmac
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.v1 import jobs, projects, characters, websocket, upload, episodes, trends, scheduler, youtube, analytics, review, proxy, pipeline_templates
from app.core.config import settings
from app.core.db import engine, Base

# Import all models to register them with SQLAlchemy
from app.models import (Project, Episode, Scene, Asset, Job, Character, User,
                        Trend, StoryIdea, TrendSnapshot, ScheduledTask, YouTubeChannel,
                        YouTubeUpload, VideoAnalytics, ReviewItem, PipelineTemplate)

# Create database tables on startup
Base.metadata.create_all(bind=engine)

# Lightweight migration: add missing columns to existing tables
def _migrate_add_columns():
    """Add new columns that create_all won't add to existing tables."""
    from sqlalchemy import text, inspect
    insp = inspect(engine)
    # Add 'region' to 'trends' table if missing
    if "trends" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("trends")]
        if "region" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN region VARCHAR DEFAULT 'US'"))
                print("[MIGRATE] Added 'region' column to trends table")

    # Add 'duration_sec' to 'trends' table if missing
    if "trends" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("trends")]
        if "duration_sec" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN duration_sec INTEGER"))
                print("[MIGRATE] Added 'duration_sec' column to trends table")

    # Add 'thumbnail_url' to 'trends' table if missing
    if "trends" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("trends")]
        if "thumbnail_url" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN thumbnail_url VARCHAR"))
                print("[MIGRATE] Added 'thumbnail_url' column to trends table")

    # Add 'youtube_upload_id' to 'review_items' table if missing
    if "review_items" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("review_items")]
        if "youtube_upload_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE review_items ADD COLUMN youtube_upload_id INTEGER"))
                print("[MIGRATE] Added 'youtube_upload_id' column to review_items table")

    # Add 'narrative_structure' and 'regenerable' to 'story_ideas' table if missing
    if "story_ideas" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("story_ideas")]
        if "narrative_structure" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE story_ideas ADD COLUMN narrative_structure VARCHAR"))
                print("[MIGRATE] Added 'narrative_structure' column to story_ideas table")
        if "regenerable" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE story_ideas ADD COLUMN regenerable VARCHAR"))
                print("[MIGRATE] Added 'regenerable' column to story_ideas table")
        if "analysis_json" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE story_ideas ADD COLUMN analysis_json TEXT"))
                print("[MIGRATE] Added 'analysis_json' column to story_ideas table")

    # Add 'character_card', 'voice_description', 'seed' to 'characters' table if missing
    if "characters" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("characters")]
        if "character_card" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE characters ADD COLUMN character_card TEXT"))
                print("[MIGRATE] Added 'character_card' column to characters table")
        if "voice_description" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE characters ADD COLUMN voice_description VARCHAR"))
                print("[MIGRATE] Added 'voice_description' column to characters table")
        if "seed" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE characters ADD COLUMN seed INTEGER"))
                print("[MIGRATE] Added 'seed' column to characters table")

    # Add 'content_type' to 'trends' table if missing
    if "trends" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("trends")]
        if "content_type" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN content_type VARCHAR DEFAULT 'other'"))
                print("[MIGRATE] Added 'content_type' column to trends table")

    # Add viral_coef fields to 'trends' table if missing
    if "trends" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("trends")]
        if "subscriber_count" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN subscriber_count INTEGER"))
                print("[MIGRATE] Added 'subscriber_count' column to trends table")
        if "viral_coef" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN viral_coef REAL"))
                print("[MIGRATE] Added 'viral_coef' column to trends table")
        if "is_anomaly" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN is_anomaly INTEGER DEFAULT 0"))
                print("[MIGRATE] Added 'is_anomaly' column to trends table")
        if "matched_keyword" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN matched_keyword VARCHAR"))
                print("[MIGRATE] Added 'matched_keyword' column to trends table")
        if "niche" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE trends ADD COLUMN niche VARCHAR"))
                print("[MIGRATE] Added 'niche' column to trends table")

    # Add voiceover columns to 'episodes' if missing (Phase 1: TTS support)
    if "episodes" in insp.get_table_names():
        columns = [c["name"] for c in insp.get_columns("episodes")]
        for col_name, col_sql in [
            ("voiceover_url", "ALTER TABLE episodes ADD COLUMN voiceover_url VARCHAR"),
            ("voiceover_words_json", "ALTER TABLE episodes ADD COLUMN voiceover_words_json TEXT"),
            ("voiceover_provider", "ALTER TABLE episodes ADD COLUMN voiceover_provider VARCHAR"),
            ("video_with_voiceover_url", "ALTER TABLE episodes ADD COLUMN video_with_voiceover_url VARCHAR"),
            ("video_with_captions_url", "ALTER TABLE episodes ADD COLUMN video_with_captions_url VARCHAR"),
            ("video_with_music_url", "ALTER TABLE episodes ADD COLUMN video_with_music_url VARCHAR"),
        ]:
            if col_name not in columns:
                with engine.begin() as conn:
                    conn.execute(text(col_sql))
                    print(f"[MIGRATE] Added '{col_name}' column to episodes table")

_migrate_add_columns()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# API-key auth: включается, если в .env задан API_AUTH_KEY.
# Исключения: OPTIONS (CORS preflight), OAuth-callback YouTube (редирект Google
# приходит без заголовков), openapi.json (чтобы работал /docs),
# proxy/image (грузится через <img src>, браузер не шлёт заголовки;
# защищён собственным whitelist хостов).
_AUTH_EXEMPT_PATHS = {f"{settings.API_V1_STR}/openapi.json"}
_AUTH_EXEMPT_PREFIXES = (
    f"{settings.API_V1_STR}/youtube/auth/callback",
    f"{settings.API_V1_STR}/proxy/image",
)


@app.middleware("http")
async def api_key_auth(request, call_next):
    if settings.API_AUTH_KEY and request.url.path.startswith("/api/"):
        path = request.url.path
        exempt = (
            request.method == "OPTIONS"
            or path in _AUTH_EXEMPT_PATHS
            or path.startswith(_AUTH_EXEMPT_PREFIXES)
        )
        if not exempt:
            provided = request.headers.get("x-api-key") or ""
            if not hmac.compare_digest(provided, settings.API_AUTH_KEY):
                return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)

# CORS middleware - MUST be added before routes
cors_origins = [o.strip().rstrip("/") for o in (settings.CORS_ALLOW_ORIGINS or "").split(",") if o.strip()]
frontend_origin = (settings.FRONTEND_URL or "").strip().rstrip("/")
if frontend_origin and frontend_origin not in cors_origins:
    cors_origins.append(frontend_origin)

# Convenience for local dev when FRONTEND_URL uses localhost/127.0.0.1
if frontend_origin.startswith("http://localhost:"):
    local_alt = frontend_origin.replace("http://localhost:", "http://127.0.0.1:", 1)
    if local_alt not in cors_origins:
        cors_origins.append(local_alt)
elif frontend_origin.startswith("http://127.0.0.1:"):
    local_alt = frontend_origin.replace("http://127.0.0.1:", "http://localhost:", 1)
    if local_alt not in cors_origins:
        cors_origins.append(local_alt)

allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploaded images
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Static files for merged videos
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# API routes
app.include_router(jobs.router, prefix=f"{settings.API_V1_STR}/jobs", tags=["jobs"])
app.include_router(projects.router, prefix=f"{settings.API_V1_STR}/projects", tags=["projects"])
app.include_router(characters.router, prefix=f"{settings.API_V1_STR}/projects", tags=["characters"])
app.include_router(websocket.router, prefix=f"{settings.API_V1_STR}", tags=["websocket"])
app.include_router(upload.router, prefix=f"{settings.API_V1_STR}/upload", tags=["upload"])
app.include_router(episodes.router, prefix=f"{settings.API_V1_STR}/episodes", tags=["episodes"])
app.include_router(trends.router, prefix=f"{settings.API_V1_STR}/trends", tags=["trends"])
app.include_router(scheduler.router, prefix=f"{settings.API_V1_STR}/scheduler", tags=["scheduler"])
app.include_router(youtube.router, prefix=f"{settings.API_V1_STR}/youtube", tags=["youtube"])
app.include_router(analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(review.router, prefix=f"{settings.API_V1_STR}/review", tags=["review"])
app.include_router(proxy.router, prefix=f"{settings.API_V1_STR}/proxy", tags=["proxy"])
app.include_router(pipeline_templates.router, prefix=f"{settings.API_V1_STR}/pipeline-templates", tags=["pipeline-templates"])

@app.get("/")
def root():
    return {"message": "Welcome to AI Video Factory API"}

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.PROJECT_NAME}

