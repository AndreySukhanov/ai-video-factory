from abc import ABC, abstractmethod

class VideoProvider(ABC):
    @abstractmethod
    def generate_clip(self, visual_prompt: str, duration_sec: int, *, aspect_ratio: str = "9:16") -> str:
        """
        Returns URL or ID of the generated video clip.
        """
        pass
