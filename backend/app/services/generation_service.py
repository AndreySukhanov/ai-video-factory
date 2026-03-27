import json
import redis
from rq import Queue
from sqlalchemy.orm import Session
from app.models import Project, Job, Episode, Scene, Asset
from app.ai_orchestrator.llm_client import LLMClient
from app.ai_orchestrator.agents import StoryAgent, EpisodeAgent, ShotPromptAgent
from app.media import VideoProviderMock
from app.media.video_provider_minimax import MiniMaxProvider
from app.media.video_provider_pika import PikaVideoProvider
from app.core.config import settings

# Initialize agents
llm_client = LLMClient()
story_agent = StoryAgent(llm_client)
episode_agent = EpisodeAgent(llm_client)
shot_prompt_agent = ShotPromptAgent(llm_client)

# Video provider selection (priority: Replicate MiniMax > Pika/fal.ai > Mock)
if settings.REPLICATE_API_TOKEN:
    video_provider = MiniMaxProvider()
    print("[VIDEO] Using MiniMax Video-01 via Replicate for video generation")
elif settings.VIDEO_API_KEY or settings.FAL_KEY:
    video_provider = PikaVideoProvider()
    print("[VIDEO] Using Pika via fal.ai for video generation")
else:
    video_provider = VideoProviderMock()
    print("[WARNING] Using Mock video provider (no API keys configured)")

# Redis Queue connection (lazy initialization)
_redis_conn = None
_job_queue = None

def _get_job_queue():
    """Get Redis Queue connection lazily"""
    global _redis_conn, _job_queue
    if _job_queue is None:
        try:
            _redis_conn = redis.from_url(settings.REDIS_URL)
            _job_queue = Queue('default', connection=_redis_conn)
        except redis.exceptions.ConnectionError as e:
            print(f"[WARNING] Redis connection failed: {e}")
            return None
    return _job_queue

def enqueue_job(job_id: int):
    """Enqueue a job to Redis Queue for processing by the worker"""
    job_queue = _get_job_queue()
    if job_queue is None:
        print(f"[WARNING] Redis not available. Job {job_id} will be processed synchronously.")
        # Process job synchronously if Redis is not available
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            process_job(db, job_id)
        finally:
            db.close()
        return
    
    from app.worker import job_processor
    job_queue.enqueue(job_processor, job_id)
    print(f"Job {job_id} enqueued to Redis Queue")

def start_project_generation(db: Session, project_id: int):
    job = Job(
        type="GENERATE_STORY",
        status="queued",
        payload_json=json.dumps({"project_id": project_id})
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Enqueue job to Redis Queue
    enqueue_job(job.id)
    
    return job

def process_job(db: Session, job_id: int):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return
    
    job.status = "in_progress"
    db.commit()
    
    try:
        payload = json.loads(job.payload_json)
        
        if job.type == "GENERATE_STORY":
            _handle_generate_story(db, job, payload)
        elif job.type == "GENERATE_SCENES":
            _handle_generate_scenes(db, job, payload)
        elif job.type == "GENERATE_SCENE_PROMPTS":
            _handle_generate_scene_prompts(db, job, payload)
        elif job.type == "GENERATE_SCENE_MEDIA":
            _handle_generate_scene_media(db, job, payload)
        elif job.type == "RENDER_EPISODE":
            from app.services.render_service import handle_render_episode_job
            handle_render_episode_job(db, job, payload)
            
        job.status = "done"
        db.commit()
    except Exception as e:
        job.status = "failed"
        job.error_text = str(e)
        db.commit()

def _handle_generate_story(db: Session, job: Job, payload: dict):
    from app.models import Character
    from app.media.character_generator import CharacterGenerator
    
    project_id = payload["project_id"]
    project = db.query(Project).filter(Project.id == project_id).first()
    
    story_data = story_agent.generate_series_structure(
        idea=project.logline,
        genre=project.genre,
        target_platform=project.target_platform,
        episodes_count=project.total_episodes,
        episode_duration=project.episode_duration_sec
    )
    
    project.title = story_data.get("series_title", project.title)
    project.logline = story_data.get("logline", project.logline)
    project.status = "generating"
    
    # Generate character images for consistency
    character_generator = CharacterGenerator()
    characters_data = story_data.get("characters", [])
    
    # Build character cards via LLM if not already provided
    from app.ai_orchestrator.agents import get_story_generator
    story_gen = get_story_generator()

    for char_data in characters_data:
        try:
            # Generate character image
            char_result = character_generator.generate_character(
                name=char_data.get("name", "Character"),
                description=char_data.get("description", ""),
                style="realistic"
            )

            # Auto-generate character_card for Veo 3.1
            char_card = char_data.get("character_card", "")
            if not char_card and char_data.get("description"):
                char_card = story_gen.build_character_card(
                    char_data["description"], project.genre or "drama"
                )

            character = Character(
                project_id=project.id,
                name=char_data.get("name"),
                role=char_data.get("role", "support"),
                description=char_data.get("description"),
                reference_image_url=char_result["image_url"],
                appearance_prompt=char_result["prompt"],
                character_card=char_card or None,
                voice_description=char_data.get("voice_description"),
            )
            db.add(character)
        except Exception as e:
            print(f"Warning: Failed to generate character {char_data.get('name')}: {e}")
            character = Character(
                project_id=project.id,
                name=char_data.get("name"),
                role=char_data.get("role", "support"),
                description=char_data.get("description")
            )
            db.add(character)
    
    db.commit()
    
    # Debug: print story data
    print(f"Story data received: {json.dumps(story_data, indent=2, ensure_ascii=False)}")
    print(f"Episodes in story_data: {len(story_data.get('episodes', []))}")
    
    # Create episodes
    for ep_data in story_data.get("episodes", []):
        print(f"Creating episode {ep_data.get('number')}: {ep_data.get('title')}")
        episode = Episode(
            project_id=project.id,
            number=ep_data["number"],
            title=ep_data["title"],
            hook=ep_data["hook"],
            synopsis=ep_data["synopsis"],
            status="pending"
        )
        db.add(episode)
        db.commit()
        db.refresh(episode)
        
        # Create next job
        next_job = Job(
            type="GENERATE_SCENES",
            status="queued",
            payload_json=json.dumps({"episode_id": episode.id})
        )
        db.add(next_job)
        db.commit()
        db.refresh(next_job)
        enqueue_job(next_job.id)
        print(f"Created and enqueued GENERATE_SCENES job for episode {episode.id}")
    
    print(f"Story generation completed. Created {len(story_data.get('episodes', []))} episodes")

def _handle_generate_scenes(db: Session, job: Job, payload: dict):
    episode_id = payload["episode_id"]
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    
    # Need characters from project/story context, simplifying for MVP
    characters = [] 
    
    script_data = episode_agent.generate_script(
        synopsis=episode.synopsis,
        characters=characters,
        duration_sec=60 # Default
    )
    
    for scene_data in script_data.get("scenes", []):
        scene = Scene(
            episode_id=episode.id,
            number=scene_data["scene_number"],
            duration_sec=scene_data["duration_sec"],
            what_happens=scene_data["what_happens"],
            dialogue_json=json.dumps(scene_data.get("dialogue", []))
        )
        db.add(scene)
        db.commit()
        db.refresh(scene)
        
        # Create next job
        next_job = Job(
            type="GENERATE_SCENE_PROMPTS",
            status="queued",
            payload_json=json.dumps({"scene_id": scene.id})
        )
        db.add(next_job)
        db.commit()
        db.refresh(next_job)
        enqueue_job(next_job.id)

def _handle_generate_scene_prompts(db: Session, job: Job, payload: dict):
    from app.models import Character
    
    scene_id = payload["scene_id"]
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id).first()
    
    # Get all project characters with their appearance data
    project_characters = db.query(Character).filter(
        Character.project_id == project.id
    ).all()
    
    # Build character list with descriptions
    characters = []
    character_appearances = {}
    
    for char in project_characters:
        characters.append({
            "name": char.name,
            "role": char.role,
            "description": char.description
        })
        # Store appearance prompt for consistency
        if char.appearance_prompt:
            character_appearances[char.name] = char.appearance_prompt
    
    # Get previous scene's prompt for consistency
    previous_prompt = None
    if scene.number > 1:
        prev_scene = db.query(Scene).filter(
            Scene.episode_id == episode.id,
            Scene.number == scene.number - 1
        ).first()
        if prev_scene and prev_scene.visual_prompt:
            previous_prompt = prev_scene.visual_prompt
    
    # Extract visual_tags_en from linked StoryIdea's analysis_json (Trendsee-style)
    visual_tags = None
    try:
        from app.models.trend import StoryIdea
        idea = db.query(StoryIdea).filter(StoryIdea.project_id == project.id).first()
        if idea and idea.analysis_json:
            import json as _json
            analysis = _json.loads(idea.analysis_json)
            visual_tags = analysis.get("visual_search_assets", {}).get("visual_tags_en")
    except Exception:
        pass

    # Generate prompt with full character context
    prompt_data = shot_prompt_agent.generate_visual_prompt(
        scene_description=scene.what_happens,
        characters=characters,
        character_appearances=character_appearances,
        visual_tags=visual_tags,
    )
    
    scene.visual_prompt = prompt_data.get("visual_prompt", "")
    
    # Store character descriptions for future reference
    if prompt_data.get("character_descriptions"):
        scene_meta = {
            "character_descriptions": prompt_data.get("character_descriptions"),
            "camera": prompt_data.get("camera"),
            "mood": prompt_data.get("mood")
        }
        # Could store this in scene metadata if needed
    
    db.commit()
    
    # Create next job
    next_job = Job(
        type="GENERATE_SCENE_MEDIA",
        status="queued",
        payload_json=json.dumps({"scene_id": scene.id})
    )
    db.add(next_job)
    db.commit()
    db.refresh(next_job)
    enqueue_job(next_job.id)

def _handle_generate_scene_media(db: Session, job: Job, payload: dict):
    from app.models import Character
    
    scene_id = payload["scene_id"]
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = db.query(Project).filter(Project.id == episode.project_id).first()
    
    # Collect ALL character reference images for this scene
    reference_images = []
    primary_reference = None
    
    # Priority 1: Scene-specific reference image
    if scene.reference_image_url:
        primary_reference = scene.reference_image_url
        reference_images.append(scene.reference_image_url)
    
    # Priority 2: Get ALL characters mentioned in dialogue
    characters_in_scene = []
    if scene.dialogue_json:
        try:
            dialogues = json.loads(scene.dialogue_json)
            # Get unique character names from dialogue
            char_names = set(d.get("character") for d in dialogues if d.get("character"))
            
            for char_name in char_names:
                character = db.query(Character).filter(
                    Character.project_id == project.id,
                    Character.name == char_name
                ).first()
                
                if character:
                    characters_in_scene.append(character)
                    if character.reference_image_url:
                        reference_images.append(character.reference_image_url)
                        if not primary_reference:
                            primary_reference = character.reference_image_url
        except json.JSONDecodeError:
            pass
    
    # Priority 3: If no specific characters, get main character
    if not reference_images:
        main_character = db.query(Character).filter(
            Character.project_id == project.id,
            Character.role == "main"
        ).first()
        
        if main_character and main_character.reference_image_url:
            primary_reference = main_character.reference_image_url
            reference_images.append(main_character.reference_image_url)
    
    # Priority 4: Project-wide reference image
    if not primary_reference and project.reference_image_url:
        primary_reference = project.reference_image_url
        reference_images.append(project.reference_image_url)
    
    # Build enhanced prompt with character card injection (Veo 3.1 best practice)
    enhanced_prompt = scene.visual_prompt
    if characters_in_scene:
        cards = []
        for char in characters_in_scene:
            # Prefer character_card (Veo 3.1 optimized), fall back to appearance_prompt
            card = char.character_card or char.appearance_prompt
            if card:
                cards.append(card)

        if cards:
            # Prepend character cards to the prompt (Veo 3.1: character description first)
            enhanced_prompt = f"{'. '.join(cards)}. {scene.visual_prompt}"
    
    # Generate video with reference
    video_url = video_provider.generate_clip(
        visual_prompt=enhanced_prompt,
        duration_sec=scene.duration_sec,
        reference_image_url=primary_reference
    )
    
    asset = Asset(
        scene_id=scene.id,
        type="scene_video",
        url=video_url
    )
    db.add(asset)
    db.commit()
    
    # Check if all scenes for this episode have videos
    all_scenes = db.query(Scene).filter(Scene.episode_id == episode.id).all()
    scenes_with_video = db.query(Scene).join(Asset).filter(
        Scene.episode_id == episode.id,
        Asset.type == "scene_video"
    ).count()
    
    # If all scenes have videos, trigger episode rendering
    if scenes_with_video == len(all_scenes):
        render_job = Job(
            type="RENDER_EPISODE",
            status="queued",
            payload_json=json.dumps({"episode_id": episode.id})
        )
        db.add(render_job)
        db.commit()
        db.refresh(render_job)
        enqueue_job(render_job.id)


