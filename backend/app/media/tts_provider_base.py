from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float


@dataclass
class TTSResult:
    audio: bytes
    words: list[WordTimestamp] = field(default_factory=list)
    audio_format: str = "mp3"


class TTSProvider(ABC):
    @abstractmethod
    def generate(self, text: str, *, voice_id: str | None = None) -> TTSResult:
        """Synthesize speech for `text`. Returns audio bytes + optional word-level timestamps."""
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__
