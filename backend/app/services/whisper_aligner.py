"""Whisper-based forced alignment for TTS providers without native word-timestamps.

Uses faster-whisper (CTranslate2 backend, INT8 by default for CPU). On first call the
model is downloaded from HuggingFace and cached on disk (~/.cache/huggingface).

The aligner runs ASR on the audio, then greedy-aligns Whisper's recognized words to the
known TTS transcript: 5-word lookahead window, substring fallback, neighbor interpolation
for misses. This matches the OpenReels pattern, ported from TypeScript to Python.
"""
import re
import tempfile
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.media.tts_provider_base import WordTimestamp


def _normalize(word: str) -> str:
    return re.sub(r"[^a-z0-9'а-яё]", "", word.lower())


class WhisperAligner:
    """Lazy-loaded singleton; first transcribe() call downloads the model."""

    _model = None
    _model_name: Optional[str] = None

    @classmethod
    def _get_model(cls):
        if cls._model is not None and cls._model_name == settings.WHISPER_MODEL:
            return cls._model
        from faster_whisper import WhisperModel
        print(
            f"[WHISPER] Loading model={settings.WHISPER_MODEL} "
            f"device={settings.WHISPER_DEVICE} compute_type={settings.WHISPER_COMPUTE_TYPE} (first call downloads)"
        )
        cls._model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        cls._model_name = settings.WHISPER_MODEL
        return cls._model

    def align(self, audio: bytes | str, text: str, *, audio_format: str = "mp3") -> list[WordTimestamp]:
        """Align audio to known transcript, producing word-level timestamps.

        Args:
            audio: raw audio bytes OR path to existing audio file
            text: known transcript text (the same text passed to TTS)
            audio_format: file extension for bytes input (default mp3)

        Returns list of WordTimestamp matching the ORIGINAL transcript tokens, with
        timings interpolated for tokens Whisper missed.
        """
        if not text or not text.strip():
            return []

        if isinstance(audio, bytes):
            with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as f:
                tmp_path = f.name
                f.write(audio)
        else:
            tmp_path = audio

        try:
            model = self._get_model()
            segments, _info = model.transcribe(
                tmp_path,
                word_timestamps=True,
                beam_size=1,
                vad_filter=False,
            )

            hyp: list[WordTimestamp] = []
            for seg in segments:
                if not seg.words:
                    continue
                for w in seg.words:
                    hyp.append(WordTimestamp(word=w.word.strip(), start=float(w.start), end=float(w.end)))

            if not hyp:
                raise RuntimeError(
                    f"Whisper produced 0 words for {len(text.split())}-token transcript. "
                    "Audio may be silent or corrupt."
                )

            return self._align_to_transcript(text, hyp)
        finally:
            if isinstance(audio, bytes):
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    @staticmethod
    def _align_to_transcript(text: str, hyp: list[WordTimestamp]) -> list[WordTimestamp]:
        ref_words = [w for w in text.split() if _normalize(w)]
        if not ref_words:
            return []

        result: list[WordTimestamp] = []
        hi = 0
        n = len(hyp)

        for rw in ref_words:
            nr = _normalize(rw)
            if not nr:
                continue

            best = -1
            for j in range(hi, min(hi + 5, n)):
                nh = _normalize(hyp[j].word)
                if nr == nh:
                    best = j
                    break
                if nr and nh and (nr in nh or nh in nr) and best == -1:
                    best = j

            if best >= 0:
                result.append(WordTimestamp(word=rw, start=hyp[best].start, end=hyp[best].end))
                hi = best + 1
            else:
                prev_end = result[-1].end if result else 0.0
                est_dur = max(0.1, len(rw) * 0.06)
                result.append(WordTimestamp(word=rw, start=prev_end, end=prev_end + est_dur))

        return result
