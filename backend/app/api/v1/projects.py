from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.db import get_db
from app.models import Project, Episode
from app.schemas import project as schemas
from app.services import generation_service

router = APIRouter()


@router.post("/", response_model=schemas.Project)
def create_project(project_in: schemas.ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        title=f"New Project based on: {project_in.idea[:20]}...", # Temporary title
        logline=project_in.idea,
        genre=project_in.genre,
        target_platform=project_in.target_platform,
        total_episodes=project_in.episodes_count,
        episode_duration_sec=project_in.episode_duration_sec,
        reference_image_url=project_in.reference_image_url,  # Store reference image
        status="generating"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Start generation
    generation_service.start_project_generation(db, project.id)
    
    return project

@router.get("/", response_model=List[schemas.Project])
def read_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    projects = db.query(Project).offset(skip).limit(limit).all()
    return projects

@router.get("/{project_id}", response_model=schemas.Project)
def read_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.get("/{project_id}/full", response_model=schemas.ProjectFull)
def read_project_full(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.put("/{project_id}", response_model=schemas.Project)
def update_project(project_id: int, update: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in update.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"success": True, "message": f"Project {project_id} deleted"}
