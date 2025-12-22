"""
Event emitter for broadcasting job progress updates
Bridges synchronous job processing with async WebSocket notifications
"""
import asyncio
import json
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import threading


@dataclass
class JobEvent:
    """Represents a job progress event"""
    project_id: int
    job_id: int
    job_type: str
    status: str
    progress: int = 0
    message: Optional[str] = None
    episode_id: Optional[int] = None
    scene_id: Optional[int] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            "type": "job_update",
            "project_id": self.project_id,
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "episode_id": self.episode_id,
            "scene_id": self.scene_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class EventEmitter:
    """
    Simple event emitter for job progress updates.
    Supports both sync and async listeners.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._listeners: Dict[str, List[Callable]] = {}
        self._event_queue: List[JobEvent] = []
        self._initialized = True
    
    def on(self, event: str, callback: Callable):
        """Register an event listener"""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)
    
    def off(self, event: str, callback: Callable):
        """Remove an event listener"""
        if event in self._listeners:
            self._listeners[event] = [
                cb for cb in self._listeners[event] if cb != callback
            ]
    
    def emit(self, event: str, data: Any):
        """Emit an event synchronously"""
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Event listener error: {e}")
    
    async def emit_async(self, event: str, data: Any):
        """Emit an event asynchronously"""
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    print(f"Async event listener error: {e}")
    
    def emit_job_update(
        self,
        project_id: int,
        job_id: int,
        job_type: str,
        status: str,
        progress: int = 0,
        message: str = None,
        episode_id: int = None,
        scene_id: int = None
    ):
        """Convenience method to emit a job update event"""
        event = JobEvent(
            project_id=project_id,
            job_id=job_id,
            job_type=job_type,
            status=status,
            progress=progress,
            message=message,
            episode_id=episode_id,
            scene_id=scene_id
        )
        self._event_queue.append(event)
        self.emit("job_update", event)
    
    def get_recent_events(self, project_id: int = None, limit: int = 50) -> List[JobEvent]:
        """Get recent events, optionally filtered by project"""
        events = self._event_queue
        if project_id is not None:
            events = [e for e in events if e.project_id == project_id]
        return events[-limit:]
    
    def clear_events(self, project_id: int = None):
        """Clear event queue"""
        if project_id is None:
            self._event_queue.clear()
        else:
            self._event_queue = [
                e for e in self._event_queue if e.project_id != project_id
            ]


# Global event emitter instance
event_emitter = EventEmitter()


def emit_job_progress(
    project_id: int,
    job_id: int,
    job_type: str,
    status: str,
    progress: int = 0,
    message: str = None,
    episode_id: int = None,
    scene_id: int = None
):
    """Helper function to emit job progress from anywhere in the app"""
    event_emitter.emit_job_update(
        project_id=project_id,
        job_id=job_id,
        job_type=job_type,
        status=status,
        progress=progress,
        message=message,
        episode_id=episode_id,
        scene_id=scene_id
    )
