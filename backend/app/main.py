import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1 import jobs, projects, characters, websocket, upload, episodes, trends, scheduler, youtube, analytics, review
from app.core.config import settings
from app.core.db import engine, Base

# Import all models to register them with SQLAlchemy
from app.models import (Project, Episode, Scene, Asset, Job, Character, User,
                        Trend, StoryIdea, TrendSnapshot, ScheduledTask, YouTubeChannel,
                        YouTubeUpload, VideoAnalytics, ReviewItem)

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

_migrate_add_columns()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS middleware - MUST be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
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

@app.get("/")
def root():
    return {"message": "Welcome to AI Video Factory API"}

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.PROJECT_NAME}

