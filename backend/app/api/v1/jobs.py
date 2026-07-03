from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from app.core.db import get_db
from app.models import Job, Episode, Scene
from app.schemas import job as schemas

router = APIRouter()


@router.get("/", response_model=List[schemas.Job])
def list_jobs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all jobs with optional filtering"""
    query = db.query(Job)
    
    if status:
        query = query.filter(Job.status == status)
    if job_type:
        query = query.filter(Job.type == job_type)
    
    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
    return jobs


@router.get("/project/{project_id}", response_model=List[schemas.JobWithProgress])
def get_project_jobs(project_id: int, db: Session = Depends(get_db)):
    """
    Get all jobs related to a project with progress information.
    This includes jobs for story generation, scenes, and rendering.
    """
    # Get all episode IDs for this project
    episode_ids = [e.id for e in db.query(Episode.id).filter(Episode.project_id == project_id).all()]
    
    # Get all scene IDs for these episodes
    scene_ids = []
    if episode_ids:
        scene_ids = [s.id for s in db.query(Scene.id).filter(Scene.episode_id.in_(episode_ids)).all()]
    
    jobs = []
    
    # Get story generation job
    story_jobs = db.query(Job).filter(
        Job.type == "GENERATE_STORY",
        Job.payload_json.contains(f'"project_id": {project_id}')
    ).all()
    jobs.extend(story_jobs)
    
    # Get scene generation jobs
    for ep_id in episode_ids:
        ep_jobs = db.query(Job).filter(
            Job.type.in_(["GENERATE_SCENES", "RENDER_EPISODE"]),
            Job.payload_json.contains(f'"episode_id": {ep_id}')
        ).all()
        jobs.extend(ep_jobs)
    
    # Get scene prompt and media jobs
    for scene_id in scene_ids:
        scene_jobs = db.query(Job).filter(
            Job.type.in_(["GENERATE_SCENE_PROMPTS", "GENERATE_SCENE_MEDIA"]),
            Job.payload_json.contains(f'"scene_id": {scene_id}')
        ).all()
        jobs.extend(scene_jobs)
    
    # Calculate progress for each job
    result = []
    for job in jobs:
        progress = 0
        if job.status == "done":
            progress = 100
        elif job.status == "in_progress":
            progress = 50  # Could be more granular based on job type
        elif job.status == "queued":
            progress = 0
        
        # Parse payload to get episode/scene IDs
        payload = {}
        try:
            payload = json.loads(job.payload_json) if job.payload_json else {}
        except Exception:
            pass
        
        result.append({
            "id": job.id,
            "type": job.type,
            "status": job.status,
            "progress": progress,
            "payload_json": job.payload_json,
            "result_json": job.result_json,
            "error_text": job.error_text,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "episode_id": payload.get("episode_id"),
            "scene_id": payload.get("scene_id"),
            "project_id": payload.get("project_id", project_id)
        })
    
    return result


@router.get("/{job_id}", response_model=schemas.Job)
def read_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
