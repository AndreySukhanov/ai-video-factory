import json
from sqlalchemy.orm import Session
from app.models import Episode, Scene, Asset, Job, Project
from app.media.video_editor import VideoEditor
import os
import tempfile

def render_episode(
    db: Session, 
    episode_id: int,
    transition_type: str = "fade",
    transition_duration: float = 0.5
) -> str:
    """
    Render a complete episode from its scenes
    
    Args:
        db: Database session
        episode_id: Episode ID to render
        transition_type: Type of transition between scenes 
                        (fade, dissolve, wipe, slide, zoom, blur, none)
        transition_duration: Duration of transition in seconds
        
    Returns:
        URL or path to rendered episode video
    """
    editor = VideoEditor()
    
    # Check FFmpeg installation
    if not editor.check_ffmpeg_installed():
        raise RuntimeError("FFmpeg is not installed. Please install FFmpeg to use video editing features.")
    
    # Get episode and scenes
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")
    
    scenes = db.query(Scene).filter(Scene.episode_id == episode_id).order_by(Scene.number).all()
    if not scenes:
        raise ValueError(f"No scenes found for episode {episode_id}")
    
    # Download scene videos
    temp_dir = tempfile.mkdtemp()
    video_paths = []
    all_dialogues = []
    
    for scene in scenes:
        # Get scene video asset
        asset = db.query(Asset).filter(
            Asset.scene_id == scene.id,
            Asset.type == "scene_video"
        ).first()
        
        if not asset:
            print(f"Warning: No video asset for scene {scene.number}")
            continue
        
        # Download video
        video_path = os.path.join(temp_dir, f"scene_{scene.number}.mp4")
        if editor.download_video(asset.url, video_path):
            video_paths.append(video_path)
            
            # Collect dialogues for subtitles
            if scene.dialogue_json:
                try:
                    dialogues = json.loads(scene.dialogue_json)
                    all_dialogues.extend(dialogues)
                except json.JSONDecodeError:
                    pass
    
    if not video_paths:
        raise ValueError("No videos could be downloaded")
    
    # Create subtitle file
    subtitle_path = None
    if all_dialogues:
        subtitle_path = os.path.join(temp_dir, "subtitles.srt")
        editor.create_subtitle_file(all_dialogues, subtitle_path)
    
    # Combine videos with transitions
    output_path = os.path.join(temp_dir, f"episode_{episode_id}_final.mp4")
    
    if transition_type and transition_type != "none":
        # Use new transition method
        success = editor.combine_videos_with_transitions(
            video_paths=video_paths,
            output_path=output_path,
            transition_type=transition_type,
            transition_duration=transition_duration,
            subtitle_path=subtitle_path
        )
    else:
        # Use simple concatenation (faster, no transitions)
        success = editor.combine_videos(
            video_paths=video_paths,
            output_path=output_path,
            subtitle_path=subtitle_path,
            aspect_ratio="9:16"
        )
    
    if not success:
        raise RuntimeError("Failed to combine videos")
    
    # TODO: Upload to storage and return URL
    # For now, return local path
    return output_path


def handle_render_episode_job(db: Session, job: Job, payload: dict):
    """
    Job handler for rendering episodes
    """
    episode_id = payload.get("episode_id")
    
    try:
        video_path = render_episode(db, episode_id)
        
        # Create asset for episode video
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        asset = Asset(
            episode_id=episode_id,
            type="episode_video",
            url=video_path,  # TODO: Upload to cloud storage
            meta_json=json.dumps({"rendered": True})
        )
        db.add(asset)
        
        # Update episode status
        episode.status = "ready"
        db.commit()

        # Check if all episodes of the project are ready → update project status
        project = db.query(Project).filter(Project.id == episode.project_id).first()
        if project:
            all_episodes = db.query(Episode).filter(Episode.project_id == project.id).all()
            if all_episodes and all(ep.status == "ready" for ep in all_episodes):
                project.status = "ready"
                db.commit()

        job.status = "done"
        job.result_json = json.dumps({"video_path": video_path})
        db.commit()
        
    except Exception as e:
        job.status = "failed"
        job.error_text = str(e)
        db.commit()
        raise
