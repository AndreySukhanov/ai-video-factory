"""
RQ Worker for background job processing
"""
import redis
from rq import Worker, Queue
from app.core.config import settings
from app.core.db import SessionLocal
from app.services.generation_service import process_job
from app.models import Job as JobModel

# Redis connection
redis_conn = redis.from_url(settings.REDIS_URL)

def job_processor(job_id: int):
    """
    Process a single job
    This function will be called by RQ worker
    """
    db = SessionLocal()
    try:
        process_job(db, job_id)
    finally:
        db.close()

if __name__ == '__main__':
    print(f"Starting RQ worker, connecting to {settings.REDIS_URL}")
    queue = Queue('default', connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    worker.work()

