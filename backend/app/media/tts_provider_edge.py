import asyncio

import edge_tts

from app.media.tts_provider_base import TTSProvider, TTSResult, WordTimestamp

DEFAULT_VOICE = "en-US-EmmaMultilingualNeural"


class EdgeTTS(TTSProvider):
    """Microsoft Edge TTS — free, no API key. 300+ neural voices across 70+ languages.

    Returns MP3 audio plus native word-level timestamps extracted from the WordBoundary
    stream events (no Whisper forced-alignment required).

    Voice naming: `<locale>-<Name>Neural` (e.g. `en-US-AriaNeural`, `ru-RU-SvetlanaNeural`,
    `en-US-EmmaMultilingualNeural` for cross-language). Full list:
    `edge-tts --list-voices`.
    """

    def __init__(self, voice: str | None = None):
        self.voice = voice or DEFAULT_VOICE

    def generate(self, text: str, *, voice_id: str | None = None) -> TTSResult:
        voice = voice_id or self.voice
        audio_chunks: list[bytes] = []
        words: list[WordTimestamp] = []

        async def _stream() -> None:
            communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
            async for chunk in communicate.stream():
                ctype = chunk.get("type")
                if ctype == "audio":
                    audio_chunks.append(chunk["data"])
                elif ctype == "WordBoundary":
                    start = chunk["offset"] / 1e7
                    end = start + chunk["duration"] / 1e7
                    words.append(WordTimestamp(word=chunk["text"], start=start, end=end))

        asyncio.run(_stream())

        if not audio_chunks:
            raise RuntimeError("Edge TTS returned empty audio stream")

        return TTSResult(audio=b"".join(audio_chunks), words=words, audio_format="mp3")
