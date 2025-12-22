"""
Simple background worker for processing jobs
Polls database for queued jobs and processes them
"""
import time
from app.core.db import SessionLocal
from app.services.generation_service import process_job
from app.models import Job

def run_worker():
    """
    Continuously poll for and process queued jobs
    """
    print("🚀 Worker started, polling for jobs...")
    
    while True:
        db = SessionLocal()
        try:
            # Get all queued jobs
            jobs = db.query(Job).filter(Job.status == "queued").order_by(Job.id).all()
            
            if jobs:
                print(f"\n📋 Found {len(jobs)} queued jobs")
                for job in jobs:
                    print(f"⚙️  Processing job {job.id}: {job.type}")
                    try:
                        process_job(db, job.id)
                        print(f"✅ Job {job.id} completed")
                    except Exception as e:
                        print(f"❌ Job {job.id} failed: {e}")
            
            db.close()
            time.sleep(2)  # Poll every 2 seconds
            
        except KeyboardInterrupt:
            print("\n👋 Worker stopped")
            db.close()
            break
        except Exception as e:
            print(f"❌ Worker error: {e}")
            db.close()
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
