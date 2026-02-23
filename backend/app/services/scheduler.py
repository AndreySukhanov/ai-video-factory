"""
Scheduler service using rq-scheduler for recurring and one-time tasks.
"""
import json
from datetime import datetime, timedelta
from typing import Optional
import redis
from app.core.config import settings


_scheduler = None


def _get_scheduler():
    """Get or create rq-scheduler instance."""
    global _scheduler
    if _scheduler is None:
        try:
            from rq_scheduler import Scheduler
            conn = redis.from_url(settings.REDIS_URL)
            _scheduler = Scheduler(queue_name='default', connection=conn)
        except Exception as e:
            print(f"[SCHEDULER] Failed to initialize: {e}")
            return None
    return _scheduler


def schedule_recurring_trend_fetch(
    interval_seconds: int = None,
    region: str = "US",
    max_per_source: int = 20,
    max_ideas: int = 5,
    genre: str = "",
) -> Optional[str]:
    """Schedule recurring trend fetch + analysis."""
    scheduler = _get_scheduler()
    if scheduler is None:
        return None

    if interval_seconds is None:
        interval_seconds = settings.TREND_FETCH_INTERVAL_HOURS * 3600

    from app.services.trendwatcher.trend_analyzer import handle_fetch_trends_job

    job = scheduler.schedule(
        scheduled_time=datetime.utcnow(),
        func=handle_fetch_trends_job,
        kwargs={
            "region": region,
            "max_per_source": max_per_source,
            "max_ideas": max_ideas,
            "genre": genre,
        },
        interval=interval_seconds,
        repeat=None,  # Repeat forever
        meta={"task_type": "fetch_trends"},
    )
    print(f"[SCHEDULER] Recurring trend fetch scheduled every {interval_seconds}s, job_id={job.id}")
    return job.id


def schedule_one_time_task(
    func_path: str,
    run_at: datetime = None,
    kwargs: dict = None,
) -> Optional[str]:
    """Schedule a one-time task."""
    scheduler = _get_scheduler()
    if scheduler is None:
        return None

    if run_at is None:
        run_at = datetime.utcnow() + timedelta(seconds=5)

    job = scheduler.enqueue_at(
        run_at,
        func_path,
        **(kwargs or {}),
    )
    print(f"[SCHEDULER] One-time task scheduled at {run_at}, job_id={job.id}")
    return job.id


def cancel_all_trend_fetches():
    """Cancel all recurring trend fetch jobs."""
    scheduler = _get_scheduler()
    if scheduler is None:
        return

    cancelled = 0
    for job in scheduler.get_jobs():
        meta = job.meta or {}
        if meta.get("task_type") == "fetch_trends":
            scheduler.cancel(job)
            cancelled += 1

    print(f"[SCHEDULER] Cancelled {cancelled} trend fetch jobs")
    return cancelled


def get_scheduled_jobs():
    """List all scheduled jobs."""
    scheduler = _get_scheduler()
    if scheduler is None:
        return []

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "func_name": job.func_name if hasattr(job, 'func_name') else str(job.func),
            "meta": job.meta or {},
            "enqueued_at": str(job.enqueued_at) if job.enqueued_at else None,
        })
    return jobs
