"""
WebSocket endpoint for real-time job progress updates
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict, Set, Optional
import json
import asyncio

from app.core.db import get_db
from app.models import Job, Episode, Scene, Project

router = APIRouter()


class SessionConnectionManager:
    """Manages WebSocket connections per session (for Simple/Story modes)"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"[WS] Session {session_id} connected")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"[WS] Session {session_id} disconnected")

    async def send_progress(self, session_id: str, progress: dict):
        """Send progress update to a specific session"""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(progress)
            except Exception as e:
                print(f"[WS] Error sending to {session_id}: {e}")
                self.disconnect(session_id)


# Global session manager for Simple/Story modes
session_manager = SessionConnectionManager()


def get_session_manager() -> SessionConnectionManager:
    """Get the global session connection manager"""
    return session_manager


class ConnectionManager:
    """Manages WebSocket connections per project"""

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, project_id: int):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
        self.active_connections[project_id].add(websocket)
        print(f"🔌 WebSocket connected for project {project_id}")
    
    def disconnect(self, websocket: WebSocket, project_id: int):
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            print(f"🔌 WebSocket disconnected for project {project_id}")
    
    async def broadcast_to_project(self, project_id: int, message: dict):
        """Send message to all connections for a project"""
        if project_id in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)
            
            # Clean up dead connections
            for conn in dead_connections:
                self.active_connections[project_id].discard(conn)
    
    async def send_job_update(self, project_id: int, job_id: int, job_type: str, 
                              status: str, progress: int = 0, message: str = None,
                              episode_id: int = None, scene_id: int = None):
        """Send a job update to all project connections"""
        update = {
            "type": "job_update",
            "job_id": job_id,
            "job_type": job_type,
            "status": status,
            "progress": progress,
            "message": message,
            "episode_id": episode_id,
            "scene_id": scene_id
        }
        await self.broadcast_to_project(project_id, update)


# Global connection manager instance
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager"""
    return manager


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: int):
    """
    WebSocket endpoint for real-time project updates
    
    Clients connect to this endpoint to receive live updates about:
    - Job status changes
    - Generation progress
    - Completion notifications
    """
    await manager.connect(websocket, project_id)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "project_id": project_id,
            "message": "Connected to real-time updates"
        })
        
        while True:
            # Keep connection alive and handle client messages
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Heartbeat timeout
                )
                
                # Handle ping/pong for keep-alive
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, project_id)


@router.websocket("/ws/session/{session_id}")
async def session_websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time generation progress (Simple/Story modes)

    Clients connect with a unique session_id and receive updates:
    - progress: percentage complete (0-100)
    - stage: current stage (enhancing, generating, processing)
    - message: human-readable status message
    - video_url: final video URL when complete
    """
    await session_manager.connect(websocket, session_id)

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Connected to generation progress"
        })

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0  # Longer timeout for video generation
                )

                if data == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

    except WebSocketDisconnect:
        session_manager.disconnect(session_id)
    except Exception as e:
        print(f"[WS] Session {session_id} error: {e}")
        session_manager.disconnect(session_id)
