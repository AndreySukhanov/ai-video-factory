from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
from datetime import datetime

from app.core.db import get_db
from app.core.config import settings
from app.models.schedule import ScheduledTask
from app.schemas.schedule import (
    ScheduledTaskCreate, ScheduledTaskRead, TrendFetchToggleResponse,
)
from app.services import scheduler as scheduler_service

router = APIRouter()


@router.get("/tasks", response_model=List[ScheduledTaskRead])
def list_tasks(db: Session = Depends(get_db)):
    """List all scheduled tasks."""
    tasks = db.query(ScheduledTask).order_by(ScheduledTask.created_at.desc()).all()
    return tasks


@router.post("/tasks", response_model=ScheduledTaskRead)
def create_task(task: ScheduledTaskCreate, db: Session = Depends(get_db)):
    """Create a new scheduled task."""
    db_task = ScheduledTask(
        task_type=task.task_type,
        cron_expression=task.cron_expression,
        run_at=task.run_at,
        interval_seconds=task.interval_seconds,
        payload_json=task.payload_json,
        is_recurring=task.is_recurring,
        status="active" if task.is_recurring else "pending",
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    # Schedule with rq-scheduler if recurring
    if task.is_recurring and task.task_type == "fetch_trends":
        payload = json.loads(task.payload_json) if task.payload_json else {}
        scheduler_service.schedule_recurring_trend_fetch(
            interval_seconds=task.interval_seconds or settings.TREND_FETCH_INTERVAL_HOURS * 3600,
            region=payload.get("region", "US"),
            max_per_source=payload.get("max_per_source", 20),
            max_ideas=payload.get("max_ideas", 5),
            genre=payload.get("genre", ""),
        )

    return db_task


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Cancel and delete a scheduled task."""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "cancelled"
    db.commit()

    # Cancel recurring jobs if it's a trend fetch
    if task.is_recurring and task.task_type == "fetch_trends":
        scheduler_service.cancel_all_trend_fetches()

    db.delete(task)
    db.commit()
    return {"success": True, "message": f"Task {task_id} deleted"}


@router.post("/trend-fetch/start", response_model=TrendFetchToggleResponse)
def start_trend_fetch(db: Session = Depends(get_db)):
    """Start recurring trend fetch (every TREND_FETCH_INTERVAL_HOURS)."""
    # Check if already running
    existing = db.query(ScheduledTask).filter(
        ScheduledTask.task_type == "fetch_trends",
        ScheduledTask.status == "active",
        ScheduledTask.is_recurring == True,
    ).first()

    if existing:
        return TrendFetchToggleResponse(
            success=False,
            message="Trend fetch is already running",
            task_id=existing.id,
        )

    interval = settings.TREND_FETCH_INTERVAL_HOURS * 3600

    # Save to DB
    task = ScheduledTask(
        task_type="fetch_trends",
        interval_seconds=interval,
        is_recurring=True,
        status="active",
        payload_json=json.dumps({"region": "US", "max_per_source": 20, "max_ideas": 5}),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Schedule with rq-scheduler
    scheduler_service.schedule_recurring_trend_fetch(interval_seconds=interval)

    return TrendFetchToggleResponse(
        success=True,
        message=f"Trend fetch started (every {settings.TREND_FETCH_INTERVAL_HOURS}h)",
        task_id=task.id,
    )


@router.post("/trend-fetch/stop", response_model=TrendFetchToggleResponse)
def stop_trend_fetch(db: Session = Depends(get_db)):
    """Stop recurring trend fetch."""
    tasks = db.query(ScheduledTask).filter(
        ScheduledTask.task_type == "fetch_trends",
        ScheduledTask.status == "active",
        ScheduledTask.is_recurring == True,
    ).all()

    if not tasks:
        return TrendFetchToggleResponse(
            success=False,
            message="No active trend fetch to stop",
        )

    for task in tasks:
        task.status = "paused"
    db.commit()

    scheduler_service.cancel_all_trend_fetches()

    return TrendFetchToggleResponse(
        success=True,
        message="Trend fetch stopped",
    )
