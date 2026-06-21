import httpx
from app.core.config import settings
from app.media.tts_provider_base import TTSProvider, TTSResult

OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "alloy"


class OpenAITTS(TTSProvider):
    """OpenAI TTS — returns MP3 audio without word timestamps.

    Word-level alignment requires WhisperAligner (Phase 1.1). For now, callers
    that pick OpenAI TTS get audio only; captions overlay will fall back to
    sentence-level timing until Whisper is wired in.
    """

    def __init__(self, voice: str | None = None, model: str | None = None):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.api_key = api_key
        self.voice = voice or DEFAULT_VOICE
        self.model = model or DEFAULT_MODEL

    def generate(self, text: str, *, voice_id: str | None = None) -> TTSResult:
        body = {
            "model": self.model,
            "voice": voice_id or self.voice,
            "input": text,
            "response_format": "mp3",
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                OPENAI_TTS_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI TTS error {resp.status_code}: {resp.text[:500]}")
            audio = resp.content

        return TTSResult(audio=audio, words=[], audio_format="mp3")
