import time
from .video_provider_base import VideoProvider

class VideoProviderMock(VideoProvider):
    def generate_clip(self, visual_prompt: str, duration_sec: int, *, aspect_ratio: str = "9:16") -> str:
        # Simulate API latency
        time.sleep(1)
        # Return a placeholder video URL
        return "https://www.w3schools.com/html/mov_bbb.mp4"
