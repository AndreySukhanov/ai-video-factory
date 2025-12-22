import sys
import os
import json
import time

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.core.db import SessionLocal, engine, Base
from app.models import User, Project, Job, Episode, Scene, Asset
from app.services.generation_service import start_project_generation, process_job

def init_db():
    print("Initializing DB...")
    Base.metadata.create_all(bind=engine)

def create_project(db):
    print("Creating project...")
    project = Project(
        title="Demo Project",
        logline="A programmer tries to fix a bug but accidentally creates an AI that takes over the coffee machine.",
        genre="Comedy",
        target_platform="tiktok",
        total_episodes=1,
        episode_duration_sec=30,
        status="generating"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

def run_jobs(db):
    print("Running jobs...")
    while True:
        job = db.query(Job).filter(Job.status == "queued").first()
        if not job:
            print("No more queued jobs.")
            break
        
        print(f"Processing job {job.id}: {job.type}")
        process_job(db, job.id)
        
        # Check for new jobs
        db.expire_all()

def verify_results(db, project_id):
    print("\nVerifying results...")
    project = db.query(Project).filter(Project.id == project_id).first()
    print(f"Project: {project.title}")
    print(f"Logline: {project.logline}")
    
    episodes = db.query(Episode).filter(Episode.project_id == project_id).all()
    print(f"Episodes: {len(episodes)}")
    
    for ep in episodes:
        print(f"  Episode {ep.number}: {ep.title}")
        print(f"  Synopsis: {ep.synopsis}")
        
        scenes = db.query(Scene).filter(Scene.episode_id == ep.id).all()
        print(f"  Scenes: {len(scenes)}")
        
        for scene in scenes:
            print(f"    Scene {scene.number}: {scene.what_happens[:50]}...")
            print(f"    Visual Prompt: {scene.visual_prompt[:50]}...")
            
            assets = db.query(Asset).filter(Asset.scene_id == scene.id).all()
            for asset in assets:
                print(f"      Asset ({asset.type}): {asset.url}")

def main():
    init_db()
    db = SessionLocal()
    
    try:
        project = create_project(db)
        start_project_generation(db, project.id)
        run_jobs(db)
        verify_results(db, project.id)
    finally:
        db.close()

if __name__ == "__main__":
    main()
