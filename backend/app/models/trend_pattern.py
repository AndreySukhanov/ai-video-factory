from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base


class TrendPattern(Base):
    """Structured pattern extracted from a viral trend.

    The fields below are all derived from one LLM call on the transcript + metadata.
    The downstream "Clone" endpoint uses these to build a generation brief.
    """
    __tablename__ = "trend_patterns"

    id = Column(Integer, primary_key=True, index=True)
    trend_id = Column(Integer, ForeignKey("trends.id"), nullable=False, index=True, unique=True)

    transcript = Column(Text, nullable=True)  # raw transcript (whisper or YT captions)
    transcript_source = Column(String, nullable=True)  # "youtube-captions" | "whisper" | "title-only"

    # Core structure (JSON-serialized)
    hook = Column(Text, nullable=True)  # first 3-5 seconds, hook phrase
    story_beats_json = Column(Text, nullable=True)  # [{start, end, what_happens, emotion}, ...]
    characters_json = Column(Text, nullable=True)  # [{role, gender, age_range, appearance, voice_tone}, ...]
    title_formula = Column(Text, nullable=True)  # template like "POV: I {action} and {outcome}"
    cta_structure_json = Column(Text, nullable=True)  # {app_name, cta_phrase, position} | null
    visual_style_json = Column(Text, nullable=True)  # {lighting, location, framing, color_palette}

    viral_mechanic = Column(String, nullable=True)  # "pov_story" | "soulmate_sketch" | "before_after" | "tutorial" | "list" | "skit" | "other"

    # Ready-to-use brief for our generation pipeline
    adaptation_brief = Column(Text, nullable=True)  # idea text usable in /generate
    anchor_prompt = Column(Text, nullable=True)  # visual anchor (ANCHOR+VARIABLE pattern)
    character_card = Column(Text, nullable=True)  # character card text

    extracted_at = Column(DateTime(timezone=True), server_default=func.now())
    llm_model = Column(String, nullable=True)  # which model produced this pattern

    trend = relationship("Trend")
