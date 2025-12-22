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

    class Config:
        env_file = ".env"

settings = Settings()
