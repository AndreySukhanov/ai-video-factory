"""
Simple job processor for MVP demo
Processes all queued jobs sequentially
"""
from app.core.db import SessionLocal
from app.services.generation_service import process_job
from app.models import Job
import time

def process_all_jobs():
    """Process all queued jobs"""
    db = SessionLocal()
    
    max_iterations = 50  # Prevent infinite loops
    iteration = 0
    
    while iteration < max_iterations:
        # Get all queued jobs
        jobs = db.query(Job).filter(Job.status == "queued").all()
        
        if not jobs:
            print("No more queued jobs")
            break
        
        print(f"\nIteration {iteration + 1}: Found {len(jobs)} queued jobs")
        
        for job in jobs:
            print(f"Processing job {job.id}: {job.type}")
            try:
                process_job(db, job.id)
                print(f"  ✓ Job {job.id} completed")
            except Exception as e:
                print(f"  ✗ Job {job.id} failed: {e}")
        
        iteration += 1
        time.sleep(1)  # Small delay between iterations
    
    db.close()
    print("\n✓ All jobs processed!")

if __name__ == "__main__":
    print("Starting job processor...")
    process_all_jobs()
