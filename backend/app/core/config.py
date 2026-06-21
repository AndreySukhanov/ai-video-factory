from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Video Factory"
    API_V1_STR: str = "/api/v1"

    # Database
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./sql_app.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI
    OPENAI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None  # OpenRouter API key (for DeepSeek etc)

    # Video Generation
    FAL_KEY: Optional[str] = None  # fal.ai API key
    REPLICATE_API_TOKEN: Optional[str] = None  # Replicate API token
    VIDEO_API_KEY: Optional[str] = None
    VIDEO_API_BASE_URL: Optional[str] = None

    # Google Gemini API (direct Veo 3.1 access via AI Studio key)
    GEMINI_API_KEY: Optional[str] = None

    # Google Vertex AI (Veo 3.1 with generateAudio toggle — cheaper no-audio mode)
    VERTEX_PROJECT_ID: Optional[str] = None
    VERTEX_SA_KEY_PATH: Optional[str] = None  # Path to service account JSON key
    VERTEX_REGION: str = "us-central1"

    # LaoZhang (alternative Veo proxy — no charge on failure, batch, 24h lifetime)
    LAOZHANG_API_KEY: Optional[str] = None
    LAOZHANG_BASE_URL: str = "https://api.laozhang.ai/v1"

    # WaveSpeed AI (Seedance 2.0 + 1000+ models, Bearer auth, async pred-id polling)
    WAVESPEED_API_KEY: Optional[str] = None
    WAVESPEED_BASE_URL: str = "https://api.wavespeed.ai/api/v3"

    # TTS — ElevenLabs (с native word-level timestamps) и OpenAI TTS (с Whisper alignment, Phase 1.1)
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_ID: Optional[str] = None  # default voice; can be overridden per request
    ELEVENLABS_MODEL_ID: Optional[str] = None  # default: eleven_multilingual_v2

    # Whisper aligner — выровнять word-timestamps для TTS-провайдеров без нативной поддержки
    WHISPER_MODEL: str = "tiny"  # tiny (39MB) | base (74MB) | small (244MB) | medium (769MB) | large-v3 (1.5GB)
    WHISPER_DEVICE: str = "cpu"  # cpu | cuda
    WHISPER_COMPUTE_TYPE: str = "int8"  # int8 (CPU-fast) | float16 (CUDA) | float32

    # LLM model selection — if set, overrides default routing
    # Examples: "claude-opus-4-6" (via LaoZhang), "claude-opus-4-7"
    LLM_MODEL: Optional[str] = None
    # Force LaoZhang as LLM provider (uses LAOZHANG_API_KEY + LLM_MODEL)
    LLM_PROVIDER: Optional[str] = None  # "laozhang" | "openrouter" | "openai" | None (auto)

    # Backend URL for static files
    BACKEND_URL: Optional[str] = None
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ALLOW_ORIGINS: str = ""
    ALLOW_PRIVATE_URL_FETCH: bool = False

    # Trendwatcher
    YOUTUBE_API_KEY: Optional[str] = None
    APIFY_API_TOKEN: Optional[str] = None
    RAPIDAPI_KEY: Optional[str] = None  # RapidAPI key (TikTok + Instagram scrapers)
    TREND_FETCH_INTERVAL_HOURS: int = 6
    INSTAGRAM_HASHTAGS: list = ["microdrama", "aivideo", "shortfilm", "viralvideo", "aiart", "reels"]

    # YouTube Upload (OAuth 2.0)
    YOUTUBE_CLIENT_ID: Optional[str] = None
    YOUTUBE_CLIENT_SECRET: Optional[str] = None
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/v1/youtube/auth/callback"
    ENCRYPTION_KEY: Optional[str] = None  # Fernet key for encrypting tokens

    # Scheduler
    SCHEDULER_ENABLED: bool = True

    # Analytics & Monitoring
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    ALERT_EMAIL: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # Pipeline
    AUTO_PIPELINE_MAX_VIDEOS_PER_DAY: int = 6
    AUTO_PIPELINE_DEFAULT_GENRE: str = ""

    model_config = {
        "env_file": ".env",
        "extra": "ignore"  # Ignore extra env variables
    }

settings = Settings()
