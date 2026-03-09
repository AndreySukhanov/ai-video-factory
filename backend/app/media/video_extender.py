"""
Veo Video Extender - extends Veo-generated videos by 7 seconds at a time.
Can extend up to 20 times for a max of ~148 seconds total (8 + 20*7).

Flow:
1. Extract last frame from current video
2. Use last frame as reference_image for next 8s generation
3. Concatenate segments
4. Repeat N times
"""

import os
import uuid
import tempfile
import subprocess
import requests
from typing import Optional
from app.core.config import settings


class VeoVideoExtender:
    """
    Extends Veo videos by generating continuation clips from the last frame.
    Each extension adds ~7 seconds (8s clip, first frame overlaps).
    """

    MAX_EXTENSIONS = 20  # Max extensions (8 + 20*7 = 148s max)

    def __init__(self):
        self.uploads_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "uploads",
        )
        self.static_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "static",
        )
        os.makedirs(self.uploads_dir, exist_ok=True)

    def extract_last_frame(self, video_path: str) -> str:
        """Extract last frame from video file, return path to PNG."""
        # Get duration
        probe_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{video_path}"'
        probe_result = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
        duration = float(probe_result.stdout.strip()) if probe_result.stdout.strip() else 8.0

        # Extract frame at 0.1s before end
        last_frame_time = max(0, duration - 0.1)
        frame_filename = f"ext_frame_{uuid.uuid4().hex[:8]}.png"
        frame_path = os.path.join(self.uploads_dir, frame_filename)

        cmd = f'ffmpeg -y -ss {last_frame_time} -i "{video_path}" -vframes 1 -q:v 2 "{frame_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)

        if result.returncode != 0 or not os.path.exists(frame_path):
            raise RuntimeError(f"Failed to extract frame: {result.stderr[:200]}")

        return frame_path

    def concatenate_videos(self, video_paths: list[str], output_path: str) -> str:
        """Concatenate multiple video files using FFmpeg."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for vp in video_paths:
                f.write(f"file '{vp}'\n")
            concat_list = f.name

        try:
            cmd = (
                f'ffmpeg -y -f concat -safe 0 -i "{concat_list}" '
                f'-c:v libx264 -preset fast -crf 23 -c:a aac "{output_path}"'
            )
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg concat failed: {result.stderr[:300]}")
            return output_path
        finally:
            os.unlink(concat_list)

    def extend_video(
        self,
        video_url: str,
        prompt: str,
        extensions_count: int = 1,
        aspect_ratio: str = "9:16",
        model: str = "gemini",
        quality_mode: str = "fast",
    ) -> dict:
        """
        Extend a video by generating continuation clips.

        Args:
            video_url: URL of the original video
            prompt: Visual prompt for continuation (motion-focused)
            extensions_count: Number of 7s extensions (1-20)
            aspect_ratio: Video aspect ratio
            model: Video model to use
            quality_mode: fast or standard

        Returns:
            dict with extended_video_url, total_duration, segments_count
        """
        from app.media.video_provider_gemini import GeminiVeoProvider

        extensions_count = min(extensions_count, self.MAX_EXTENSIONS)
        print(f"[EXTENDER] Starting {extensions_count} extensions for: {video_url[:60]}...")

        # Download original video
        original_path = os.path.join(self.uploads_dir, f"ext_orig_{uuid.uuid4().hex[:8]}.mp4")
        resp = requests.get(video_url, timeout=120)
        resp.raise_for_status()
        with open(original_path, "wb") as f:
            f.write(resp.content)

        video_segments = [original_path]
        current_video_path = original_path

        provider = GeminiVeoProvider(
            use_fast=(quality_mode == "fast"),
            use_fl=True,  # Frame chaining required
            aspect_ratio=aspect_ratio
        )

        for i in range(extensions_count):
            print(f"[EXTENDER] Extension {i + 1}/{extensions_count}...")

            # Extract last frame
            frame_path = self.extract_last_frame(current_video_path)

            # Upload frame to make it accessible
            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            frame_filename = os.path.basename(frame_path)
            frame_url = f"{base_url}/uploads/{frame_filename}"

            # Generate continuation (8s, fl model, motion-only prompt)
            try:
                continuation_url = provider.generate_clip(
                    visual_prompt=prompt,
                    duration_sec=8,
                    aspect_ratio=aspect_ratio,
                    reference_image_url=frame_url,
                )
            except Exception as e:
                print(f"[EXTENDER] Extension {i + 1} failed: {e}")
                break

            # Download continuation
            cont_path = os.path.join(self.uploads_dir, f"ext_seg_{uuid.uuid4().hex[:8]}.mp4")
            cont_resp = requests.get(continuation_url, timeout=120)
            cont_resp.raise_for_status()
            with open(cont_path, "wb") as f:
                f.write(cont_resp.content)

            video_segments.append(cont_path)
            current_video_path = cont_path

        # Concatenate all segments
        output_filename = f"extended_{uuid.uuid4().hex[:8]}.mp4"
        extended_dir = os.path.join(self.static_dir, "extended")
        os.makedirs(extended_dir, exist_ok=True)
        output_path = os.path.join(extended_dir, output_filename)

        if len(video_segments) > 1:
            self.concatenate_videos(video_segments, output_path)
        else:
            import shutil
            shutil.copy(video_segments[0], output_path)

        # Get total duration
        probe_cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{output_path}"'
        duration_result = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
        total_duration = float(duration_result.stdout.strip()) if duration_result.stdout.strip() else None

        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        extended_url = f"{base_url}/static/extended/{output_filename}"

        print(f"[EXTENDER] Done! {len(video_segments)} segments, {total_duration}s total: {extended_url}")

        # Cleanup temp segments (keep final output)
        for seg in video_segments:
            try:
                os.unlink(seg)
            except:
                pass

        return {
            "extended_video_url": extended_url,
            "total_duration": total_duration,
            "segments_count": len(video_segments),
        }
