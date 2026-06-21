"""Decorator that auto-injects word-level timestamps via Whisper when the wrapped
TTS provider returns audio without timings (e.g. OpenAI TTS).

   inner.generate(text)
     │
     ├── words.length > 0 ──► passthrough (ElevenLabs)
     │
     └── words.length == 0 ──► WhisperAligner.align(audio, text)
                                   │
                                   └── interpolated WordTimestamp[]
"""
from app.media.tts_provider_base import TTSProvider, TTSResult


class AlignedTTSProvider(TTSProvider):
    def __init__(self, inner: TTSProvider, aligner=None):
        self.inner = inner
        self._aligner = aligner

    def _get_aligner(self):
        if self._aligner is None:
            from app.services.whisper_aligner import WhisperAligner
            self._aligner = WhisperAligner()
        return self._aligner

    def generate(self, text: str, *, voice_id: str | None = None) -> TTSResult:
        result = self.inner.generate(text, voice_id=voice_id)
        if not result.words and text.strip():
            try:
                aligner = self._get_aligner()
                words = aligner.align(result.audio, text, audio_format=result.audio_format)
                result = TTSResult(audio=result.audio, words=words, audio_format=result.audio_format)
            except Exception as e:
                print(f"[ALIGNED_TTS] Whisper alignment failed: {e}. Returning audio without timings.")
        return result

    @property
    def name(self) -> str:
        return f"{self.inner.name}+Whisper"
