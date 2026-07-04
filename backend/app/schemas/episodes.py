"""Pydantic schemas for episode generation (extracted from api/v1/episodes.py
so the service layer does not import models from the router)."""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# Whitelisted video models — unknown values are rejected (422) instead of
# silently falling through to a fallback provider.
ALLOWED_VIDEO_MODELS = {
    "wavespeed", "wavespeed-standard", "wavespeed-v15", "laozhang",
    "vertex", "gemini", "kling", "minimax", "pika", "fal", "mock",
}


class EpisodeGenerateRequest(BaseModel):
    """Request body for episode generation"""
    prompt: str = Field(..., min_length=10, max_length=2000, description="Visual prompt for video generation")
    duration: int = Field(default=4, description="Video duration in seconds (4/6/8 for Veo; 5/10 for Kling; 6 for MiniMax)")
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio")
    reference_image_url: Optional[str] = Field(default=None, description="Optional reference image URL (first frame for I2V)")
    last_frame_image_url: Optional[str] = Field(default=None, description="Last frame image URL for transition videos (Veo 3.1 -fl models)")
    subject_reference_url: Optional[str] = Field(default=None, description="Character reference for identity consistency (MiniMax S2V-01)")
    reference_images: Optional[List[str]] = Field(default=None, description="1-3 reference images for Veo 3.1 R2V character consistency")
    model: str = Field(default="laozhang", description="Video model: seedance, wavespeed, laozhang, vertex, gemini, kling, or minimax")
    session_id: Optional[str] = Field(default=None, description="WebSocket session ID for progress updates")
    seed: Optional[int] = Field(default=None, description="Fixed seed for visual stability")
    negative_prompt: Optional[str] = Field(default=None, description="Negative prompt (noun format: text overlays, subtitles, cartoon)")
    quality_mode: str = Field(default="fast", description="Quality mode: fast or standard. For gemini/vertex.")
    generate_audio: bool = Field(default=True, description="Generate audio with video. Disable for cheaper LaoZhang ($0.10/s vs $0.15/s)")
    variants_count: int = Field(default=1, ge=1, le=4, description="Number of variants to generate (for standard mode)")
    use_timestamps: bool = Field(default=False, description="Use multi-shot timestamp prompting (gemini/vertex, duration>=6)")
    narrative_structure: Optional[str] = Field(default=None, description="Narrative structure for timestamp prompting")

    @field_validator("model")
    @classmethod
    def _validate_model(cls, v: str) -> str:
        if v not in ALLOWED_VIDEO_MODELS:
            raise ValueError(f"Unknown model '{v}'. Allowed: {sorted(ALLOWED_VIDEO_MODELS)}")
        return v


class EpisodeGenerateResponse(BaseModel):
    """Response body for episode generation"""
    success: bool
    video_url: Optional[str] = None
    variants: Optional[List[str]] = None  # Multiple video URLs when variants_count > 1
    status: str
    duration: Optional[int] = None
    generation_time: Optional[float] = None
    quality_mode: Optional[str] = None
    error: Optional[str] = None
