import base64
import httpx
from app.core.config import settings
from app.media.tts_provider_base import TTSProvider, TTSResult, WordTimestamp

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "yl2ZDV1MzN4HbQJbMihG"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"


class ElevenLabsTTS(TTSProvider):
    def __init__(self, voice_id: str | None = None, model_id: str | None = None):
        api_key = settings.ELEVENLABS_API_KEY
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")
        self.api_key = api_key
        self.voice_id = voice_id or settings.ELEVENLABS_VOICE_ID or DEFAULT_VOICE_ID
        self.model_id = model_id or settings.ELEVENLABS_MODEL_ID or DEFAULT_MODEL_ID

    def generate(self, text: str, *, voice_id: str | None = None) -> TTSResult:
        vid = voice_id or self.voice_id
        url = f"{ELEVENLABS_BASE}/text-to-speech/{vid}/with-timestamps"
        body = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                url,
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                json=body,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text[:500]}")
            data = resp.json()

        audio = base64.b64decode(data["audio_base64"])
        alignment = data.get("alignment") or {}
        words = self._aggregate(
            alignment.get("characters", []),
            alignment.get("character_start_times_seconds", []),
            alignment.get("character_end_times_seconds", []),
        )
        return TTSResult(audio=audio, words=words, audio_format="mp3")

    @staticmethod
    def _aggregate(characters: list[str], starts: list[float], ends: list[float]) -> list[WordTimestamp]:
        words: list[WordTimestamp] = []
        current = ""
        w_start = -1.0
        w_end = -1.0
        for i, ch in enumerate(characters):
            s = starts[i] if i < len(starts) else 0.0
            e = ends[i] if i < len(ends) else 0.0
            if ch in (" ", "\n", "\t"):
                if current and w_start >= 0:
                    words.append(WordTimestamp(word=current, start=w_start, end=w_end))
                current = ""
                w_start = -1.0
                w_end = -1.0
            else:
                if w_start < 0:
                    w_start = s
                w_end = e
                current += ch
        if current and w_start >= 0:
            words.append(WordTimestamp(word=current, start=w_start, end=w_end))
        return words
