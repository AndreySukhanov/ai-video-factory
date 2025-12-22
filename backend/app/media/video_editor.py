import subprocess
import os
import json
from typing import List, Dict, Optional
from pathlib import Path
import tempfile

class VideoEditor:
    """
    FFmpeg-based video editor for combining scenes and adding subtitles
    """
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        
    def check_ffmpeg_installed(self) -> bool:
        """Check if FFmpeg is installed"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def download_video(self, url: str, output_path: str) -> bool:
        """Download video from URL"""
        try:
            import requests
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"Error downloading video: {e}")
            return False
    
    def create_subtitle_file(
        self, 
        dialogues: List[Dict], 
        output_path: str,
        start_time: float = 0.0
    ) -> str:
        """
        Create SRT subtitle file from dialogue list
        
        Args:
            dialogues: List of {"character": "Name", "text": "..."}
            output_path: Path to save .srt file
            start_time: Starting time offset in seconds
            
        Returns:
            Path to created subtitle file
        """
        srt_content = []
        current_time = start_time
        
        for idx, dialogue in enumerate(dialogues, 1):
            character = dialogue.get("character", "")
            text = dialogue.get("text", "")
            
            # Estimate duration based on text length (rough: 3 chars per second)
            duration = max(2.0, len(text) / 15.0)
            
            start = self._format_srt_time(current_time)
            end = self._format_srt_time(current_time + duration)
            
            srt_content.append(f"{idx}")
            srt_content.append(f"{start} --> {end}")
            srt_content.append(f"{character}: {text}" if character else text)
            srt_content.append("")  # Empty line between subtitles
            
            current_time += duration
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_content))
        
        return output_path
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time in SRT format: HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def combine_videos(
        self,
        video_paths: List[str],
        output_path: str,
        subtitle_path: Optional[str] = None,
        aspect_ratio: str = "9:16"
    ) -> bool:
        """
        Combine multiple videos into one with optional subtitles
        
        Args:
            video_paths: List of paths to video files
            output_path: Path for output video
            subtitle_path: Optional path to SRT subtitle file
            aspect_ratio: Target aspect ratio
            
        Returns:
            True if successful
        """
        if not video_paths:
            raise ValueError("No videos to combine")
        
        # Create concat file for FFmpeg
        concat_file = os.path.join(self.temp_dir, "concat_list.txt")
        with open(concat_file, 'w') as f:
            for video_path in video_paths:
                # Escape single quotes in path
                escaped_path = video_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",  # Video codec
            "-preset", "fast",
            "-crf", "23",  # Quality (lower = better, 18-28 is good)
            "-c:a", "aac",  # Audio codec
            "-b:a", "128k"
        ]
        
        # Add subtitles if provided
        if subtitle_path and os.path.exists(subtitle_path):
            # Subtitle filter with styling for vertical video
            subtitle_filter = (
                f"subtitles={subtitle_path}:"
                f"force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                f"Outline=2,Shadow=1,MarginV=50,Alignment=2'"
            )
            cmd.extend(["-vf", subtitle_filter])
        
        cmd.append(output_path)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Clean up temp file
            if os.path.exists(concat_file):
                os.remove(concat_file)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}")
            return False
    
    def combine_videos_with_transitions(
        self,
        video_paths: List[str],
        output_path: str,
        transition_type: str = "fade",
        transition_duration: float = 0.5,
        subtitle_path: Optional[str] = None
    ) -> bool:
        """
        Combine videos with transitions between them
        
        Args:
            video_paths: List of video file paths
            output_path: Output video path
            transition_type: Type of transition (fade, dissolve, wipe, slide, none)
            transition_duration: Transition duration in seconds
            subtitle_path: Optional SRT subtitle file
            
        Returns:
            True if successful
        """
        if not video_paths:
            raise ValueError("No videos to combine")
        
        if len(video_paths) == 1:
            # Single video - just copy with optional subtitles
            return self.combine_videos(video_paths, output_path, subtitle_path)
        
        n = len(video_paths)
        td = transition_duration
        
        # Build complex filtergraph for transitions
        # Each video needs to be loaded as separate input
        inputs = []
        for path in video_paths:
            inputs.extend(["-i", path])
        
        # Build the filter chain
        filter_parts = []
        
        # Get video durations and prepare streams
        for i in range(n):
            # Normalize each video stream
            filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}];")
            if self._has_audio(video_paths[i]):
                filter_parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}];")
        
        # Build transition chain based on type
        if transition_type == "none":
            # Simple concatenation without transitions
            v_concat = "".join([f"[v{i}]" for i in range(n)])
            a_concat = "".join([f"[a{i}]" for i in range(n) if self._has_audio(video_paths[i])])
            filter_parts.append(f"{v_concat}concat=n={n}:v=1:a=0[vout];")
            if a_concat:
                filter_parts.append(f"{a_concat}concat=n={n}:v=0:a=1[aout]")
        else:
            # Apply transitions using xfade filter
            xfade_transition = self._get_xfade_transition(transition_type)
            
            # Chain xfade filters
            current_video = "v0"
            for i in range(1, n):
                next_video = f"v{i}"
                out_label = f"xf{i}" if i < n - 1 else "vout"
                
                # Calculate offset (duration of previous video minus transition)
                # We'll use a fixed estimate since getting exact duration is complex
                offset = 5.0 - td  # Assuming ~5 second clips
                
                filter_parts.append(
                    f"[{current_video}][{next_video}]xfade=transition={xfade_transition}:duration={td}:offset={offset * i}[{out_label}];"
                )
                current_video = out_label
            
            # Handle audio with acrossfade
            if any(self._has_audio(p) for p in video_paths):
                audio_streams = [f"a{i}" for i in range(n) if self._has_audio(video_paths[i])]
                if len(audio_streams) > 1:
                    current_audio = audio_streams[0]
                    for i, next_audio in enumerate(audio_streams[1:], 1):
                        out_label = f"af{i}" if i < len(audio_streams) - 1 else "aout"
                        filter_parts.append(
                            f"[{current_audio}][{next_audio}]acrossfade=d={td}[{out_label}];"
                        )
                        current_audio = out_label
                elif audio_streams:
                    filter_parts.append(f"[{audio_streams[0]}]acopy[aout];")
        
        # Combine filter parts
        filter_complex = "".join(filter_parts).rstrip(";")
        
        # Build ffmpeg command
        cmd = ["ffmpeg", "-y"] + inputs
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[vout]"])
        
        # Add audio if available
        if "[aout]" in filter_complex:
            cmd.extend(["-map", "[aout]"])
        
        # Add subtitles as a separate pass if needed
        if subtitle_path and os.path.exists(subtitle_path):
            # First render without subtitles, then add them
            temp_output = output_path.replace(".mp4", "_temp.mp4")
            cmd.extend([
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                temp_output
            ])
        else:
            cmd.extend([
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Add subtitles in second pass if needed
            if subtitle_path and os.path.exists(subtitle_path):
                temp_output = output_path.replace(".mp4", "_temp.mp4")
                self._add_subtitles(temp_output, subtitle_path, output_path)
                os.remove(temp_output)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}")
            # Fallback to simple concatenation
            print("Falling back to simple concatenation...")
            return self.combine_videos(video_paths, output_path, subtitle_path)
    
    def _get_xfade_transition(self, transition_type: str) -> str:
        """Map transition type to FFmpeg xfade transition name"""
        transitions = {
            "fade": "fade",
            "dissolve": "dissolve",
            "wipe": "wiperight",
            "wipe_left": "wipeleft",
            "wipe_up": "wipeup",
            "wipe_down": "wipedown",
            "slide": "slideright",
            "slide_left": "slideleft",
            "slide_up": "slideup",
            "slide_down": "slidedown",
            "circle": "circleopen",
            "zoom": "zoomin",
            "blur": "fadeblack",
            "pixelize": "pixelize",
            "radial": "radial",
            "smooth": "smoothleft",
        }
        return transitions.get(transition_type, "fade")
    
    def _has_audio(self, video_path: str) -> bool:
        """Check if video has audio stream"""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a",
                 "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path],
                capture_output=True, text=True
            )
            return "audio" in result.stdout
        except:
            return False
    
    def _add_subtitles(self, input_path: str, subtitle_path: str, output_path: str) -> bool:
        """Add subtitles to video"""
        # Escape path for subtitles filter
        escaped_sub = subtitle_path.replace("\\", "/").replace(":", "\\:")
        
        subtitle_filter = (
            f"subtitles='{escaped_sub}':"
            f"force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
            f"Outline=2,Shadow=1,MarginV=50,Alignment=2'"
        )
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error adding subtitles: {e.stderr}")
            return False
    
    def add_background_music(
        self,
        video_path: str,
        music_path: str,
        output_path: str,
        music_volume: float = 0.3
    ) -> bool:
        """
        Add background music to video
        
        Args:
            video_path: Input video path
            music_path: Background music path
            output_path: Output video path
            music_volume: Music volume (0.0 to 1.0)
            
        Returns:
            True if successful
        """
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex",
            f"[1:a]volume={music_volume}[music];[0:a][music]amix=inputs=2:duration=first",
            "-c:v", "copy",
            "-c:a", "aac",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error adding music: {e.stderr}")
            return False

    def add_cinematic_effects(
        self,
        input_path: str,
        output_path: str,
        vignette: float = 0.3,
        color_temperature: str = "neutral",
        film_grain: float = 0.0,
        letterbox: bool = False,
        contrast: float = 1.0,
        saturation: float = 1.0,
        brightness: float = 0.0
    ) -> bool:
        """
        Add cinematic color grading and visual effects
        
        Args:
            input_path: Input video path
            output_path: Output video path
            vignette: Vignette intensity (0.0 to 1.0)
            color_temperature: Color temp preset (warm, cool, cinematic, vintage, noir, neutral)
            film_grain: Film grain amount (0.0 to 1.0)
            letterbox: Add cinematic 2.35:1 letterbox bars
            contrast: Contrast multiplier (default 1.0)
            saturation: Saturation multiplier (default 1.0)
            brightness: Brightness adjustment (-1.0 to 1.0)
            
        Returns:
            True if successful
        """
        filters = []
        
        # Color temperature presets
        color_presets = {
            "warm": "colorbalance=rs=0.12:gs=-0.04:bs=-0.12",
            "cool": "colorbalance=rs=-0.1:gs=0.02:bs=0.15",
            "cinematic": "colorbalance=rs=0.05:gs=-0.02:bs=-0.08,eq=saturation=0.85:contrast=1.1",
            "vintage": "colorbalance=rs=0.15:gs=0.05:bs=-0.1,eq=saturation=0.7:gamma=1.1",
            "noir": "colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3,eq=contrast=1.2",
            "golden": "colorbalance=rs=0.18:gs=0.08:bs=-0.15,eq=saturation=1.1",
            "teal_orange": "colorbalance=rs=0.1:gs=-0.05:bs=-0.1:rh=-0.05:gh=0.05:bh=0.1",
            "neutral": ""
        }
        
        if color_temperature in color_presets and color_presets[color_temperature]:
            filters.append(color_presets[color_temperature])
        
        # Vignette effect
        if vignette > 0:
            vignette_angle = 3.14159 / 4  # PI/4
            filters.append(f"vignette=angle={vignette_angle}:mode=backward:x0=0.5:y0=0.5")
        
        # Brightness, contrast, saturation adjustment
        if brightness != 0 or contrast != 1.0 or saturation != 1.0:
            filters.append(f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}")
        
        # Film grain (noise)
        if film_grain > 0:
            grain_intensity = int(film_grain * 30)
            filters.append(f"noise=c0s={grain_intensity}:c0f=t+u")
        
        # Letterbox for cinematic 2.35:1 aspect
        if letterbox:
            filters.append("pad=iw:iw/2.35:0:(oh-ih)/2:black")
        
        if not filters:
            # No effects, just copy
            filters = ["copy"]
        
        filter_str = ",".join(filters)
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", filter_str,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            output_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error adding cinematic effects: {e.stderr}")
            return False

    def create_animated_ass_subtitles(
        self,
        dialogues: List[Dict],
        output_path: str,
        style: str = "modern",
        video_width: int = 720,
        video_height: int = 1280
    ) -> str:
        """
        Create ASS subtitle file with animated styles for TikTok-style captions
        
        Args:
            dialogues: List of {"character": "Name", "text": "...", "emotion": "..."}
            output_path: Path to save .ass file
            style: Style preset (modern, cinematic, minimal, bold, neon, typewriter)
            video_width: Video width for positioning
            video_height: Video height for positioning
            
        Returns:
            Path to created subtitle file
        """
        # ASS styles for different presets
        style_configs = {
            "modern": {
                "name": "Modern",
                "fontname": "Arial",
                "fontsize": 42,
                "primarycolor": "&HFFFFFF",
                "outlinecolor": "&H000000",
                "backcolor": "&H80000000",
                "bold": 1,
                "outline": 3,
                "shadow": 1,
                "alignment": 2,
                "marginv": 80
            },
            "cinematic": {
                "name": "Cinematic",
                "fontname": "Georgia",
                "fontsize": 36,
                "primarycolor": "&HFFFFCC",
                "outlinecolor": "&H333333",
                "backcolor": "&H00000000",
                "bold": 0,
                "outline": 2,
                "shadow": 2,
                "alignment": 2,
                "marginv": 100
            },
            "minimal": {
                "name": "Minimal",
                "fontname": "Helvetica Neue",
                "fontsize": 32,
                "primarycolor": "&HFFFFFF",
                "outlinecolor": "&H00000000",
                "backcolor": "&H00000000",
                "bold": 0,
                "outline": 0,
                "shadow": 0,
                "alignment": 2,
                "marginv": 60
            },
            "bold": {
                "name": "Bold",
                "fontname": "Impact",
                "fontsize": 48,
                "primarycolor": "&HFFFFFF",
                "outlinecolor": "&H000000",
                "backcolor": "&H00000000",
                "bold": 1,
                "outline": 4,
                "shadow": 2,
                "alignment": 2,
                "marginv": 70
            },
            "neon": {
                "name": "Neon",
                "fontname": "Arial Black",
                "fontsize": 40,
                "primarycolor": "&HFF00FF",
                "outlinecolor": "&HFFFF00",
                "backcolor": "&H00000000",
                "bold": 1,
                "outline": 2,
                "shadow": 0,
                "alignment": 2,
                "marginv": 80
            },
            "typewriter": {
                "name": "Typewriter",
                "fontname": "Courier New",
                "fontsize": 34,
                "primarycolor": "&HFFFFFF",
                "outlinecolor": "&H000000",
                "backcolor": "&H40000000",
                "bold": 0,
                "outline": 1,
                "shadow": 0,
                "alignment": 2,
                "marginv": 70
            }
        }
        
        cfg = style_configs.get(style, style_configs["modern"])
        
        # ASS header
        ass_content = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {cfg['name']},{cfg['fontname']},{cfg['fontsize']},{cfg['primarycolor']},&H000000FF,{cfg['outlinecolor']},{cfg['backcolor']},{cfg['bold']},0,0,0,100,100,0,0,1,{cfg['outline']},{cfg['shadow']},{cfg['alignment']},20,20,{cfg['marginv']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        current_time = 0.0
        
        for dialogue in dialogues:
            character = dialogue.get("character", "")
            text = dialogue.get("text", "")
            emotion = dialogue.get("emotion", "")
            
            # Estimate duration based on text length
            words = len(text.split())
            duration = max(2.0, words * 0.4)  # ~150 words per minute reading speed
            
            start = self._format_ass_time(current_time)
            end = self._format_ass_time(current_time + duration)
            
            # Add character name prefix if present
            display_text = f"{{\\b1}}{character}:\\N{{\\b0}}{text}" if character else text
            
            # Add emotion-based effects
            if emotion:
                if emotion.lower() in ["angry", "shouting"]:
                    display_text = f"{{\\fsp5\\fs{cfg['fontsize'] + 6}}}{display_text}"
                elif emotion.lower() in ["whisper", "quiet"]:
                    display_text = f"{{\\fsp0\\fs{cfg['fontsize'] - 4}\\alpha&H40&}}{display_text}"
                elif emotion.lower() in ["excited", "happy"]:
                    display_text = f"{{\\c&H00FFFF&}}{display_text}"
            
            # Add fade in/out effect
            fade_ms = 150
            display_text = f"{{\\fad({fade_ms},{fade_ms})}}{display_text}"
            
            ass_content += f"Dialogue: 0,{start},{end},{cfg['name']},,0,0,0,,{display_text}\n"
            
            current_time += duration + 0.1  # Small gap between subtitles
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)
        
        return output_path

    def _format_ass_time(self, seconds: float) -> str:
        """Format time in ASS format: H:MM:SS.cc (centiseconds)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def add_text_overlay(
        self,
        input_path: str,
        output_path: str,
        text: str,
        position: str = "top",
        font_size: int = 48,
        font_color: str = "white",
        background: bool = True,
        duration: float = None
    ) -> bool:
        """
        Add text overlay/watermark to video
        
        Args:
            input_path: Input video path
            output_path: Output video path
            text: Text to display
            position: Position (top, bottom, center, top-left, top-right, bottom-left, bottom-right)
            font_size: Font size
            font_color: Font color (white, black, yellow, etc.)
            background: Add semi-transparent background box
            duration: Show for first N seconds (None = entire video)
            
        Returns:
            True if successful
        """
        # Position mapping
        positions = {
            "top": "x=(w-text_w)/2:y=50",
            "bottom": "x=(w-text_w)/2:y=h-text_h-50",
            "center": "x=(w-text_w)/2:y=(h-text_h)/2",
            "top-left": "x=20:y=50",
            "top-right": "x=w-text_w-20:y=50",
            "bottom-left": "x=20:y=h-text_h-50",
            "bottom-right": "x=w-text_w-20:y=h-text_h-50"
        }
        
        pos = positions.get(position, positions["top"])
        
        # Build drawtext filter
        box_filter = ":box=1:boxcolor=black@0.5:boxborderw=10" if background else ""
        time_filter = f":enable='lt(t,{duration})'" if duration else ""
        
        text_filter = (
            f"drawtext=text='{text}':{pos}:"
            f"fontsize={font_size}:fontcolor={font_color}"
            f"{box_filter}{time_filter}"
        )
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", text_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error adding text overlay: {e.stderr}")
            return False

    def create_intro_outro(
        self,
        input_path: str,
        output_path: str,
        title: str,
        episode_number: int = None,
        intro_duration: float = 3.0,
        outro_duration: float = 2.0,
        style: str = "fade"
    ) -> bool:
        """
        Add intro and outro to video with title cards
        
        Args:
            input_path: Input video path
            output_path: Output video path
            title: Series/episode title
            episode_number: Episode number (optional)
            intro_duration: Intro duration in seconds
            outro_duration: Outro duration in seconds
            style: Transition style (fade, zoom, slide)
            
        Returns:
            True if successful
        """
        # Get video dimensions
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "csv=s=x:p=0", input_path
        ]
        
        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            dims = result.stdout.strip().split('x')
            width = int(dims[0]) if len(dims) > 0 else 720
            height = int(dims[1]) if len(dims) > 1 else 1280
        except:
            width, height = 720, 1280
        
        # Create intro title card
        episode_text = f"Episode {episode_number}" if episode_number else ""
        
        intro_filter = (
            f"color=c=black:s={width}x{height}:d={intro_duration},"
            f"drawtext=text='{title}':fontcolor=white:fontsize=60:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-40:alpha='min(1,t)'"
        )
        
        if episode_text:
            intro_filter += (
                f",drawtext=text='{episode_text}':fontcolor=gray:fontsize=36:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+40:alpha='min(1,t-0.5)'"
            )
        
        # Outro filter
        outro_filter = (
            f"color=c=black:s={width}x{height}:d={outro_duration},"
            f"drawtext=text='To be continued...':fontcolor=white:fontsize=40:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:alpha='1-max(0,(t-{outro_duration-1}))'"
        )
        
        # Complex filter for concatenation with crossfade
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", intro_filter,
            "-i", input_path,
            "-f", "lavfi", "-i", outro_filter,
            "-filter_complex",
            "[0:v][1:v]xfade=transition=fade:duration=0.5:offset={:.1f}[v1];"
            "[v1][2:v]xfade=transition=fade:duration=0.5:offset={:.1f}[vout]".format(
                intro_duration - 0.5,
                intro_duration + 10 - 0.5  # Approximate, would need actual duration
            ),
            "-map", "[vout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error creating intro/outro: {e.stderr}")
            # Fallback: just copy the video
            return False

    def adjust_speed(
        self,
        input_path: str,
        output_path: str,
        speed: float = 1.0
    ) -> bool:
        """
        Adjust video playback speed
        
        Args:
            input_path: Input video path
            output_path: Output video path
            speed: Speed multiplier (0.5 = half speed, 2.0 = double speed)
            
        Returns:
            True if successful
        """
        if speed <= 0:
            return False
        
        # Video PTS and audio tempo adjustments
        video_filter = f"setpts={1/speed}*PTS"
        audio_filter = f"atempo={speed}" if 0.5 <= speed <= 2.0 else f"atempo={min(2.0, max(0.5, speed))}"
        
        # For speeds outside 0.5-2.0, chain atempo filters
        if speed < 0.5:
            audio_filter = f"atempo=0.5,atempo={speed/0.5}"
        elif speed > 2.0:
            audio_filter = f"atempo=2.0,atempo={speed/2.0}"
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:v", video_filter,
            "-filter:a", audio_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error adjusting speed: {e.stderr}")
            return False

    def apply_lut(
        self,
        input_path: str,
        output_path: str,
        lut_path: str
    ) -> bool:
        """
        Apply a LUT (Look Up Table) for professional color grading
        
        Args:
            input_path: Input video path
            output_path: Output video path
            lut_path: Path to .cube LUT file
            
        Returns:
            True if successful
        """
        if not os.path.exists(lut_path):
            print(f"LUT file not found: {lut_path}")
            return False
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"lut3d={lut_path}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error applying LUT: {e.stderr}")
            return False

    def add_ken_burns_effect(
        self,
        image_path: str,
        output_path: str,
        duration: float = 5.0,
        direction: str = "zoom_in"
    ) -> bool:
        """
        Create Ken Burns (pan and zoom) effect from a still image
        
        Args:
            image_path: Input image path
            output_path: Output video path
            duration: Duration in seconds
            direction: Effect direction (zoom_in, zoom_out, pan_left, pan_right)
            
        Returns:
            True if successful
        """
        effects = {
            "zoom_in": "zoompan=z='min(zoom+0.001,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s=720x1280:fps=30",
            "zoom_out": "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.001))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s=720x1280:fps=30",
            "pan_left": "zoompan=z='1.1':x='if(lte(on,1),0,min(iw,x+1))':y='ih/2-(ih/zoom/2)':d={d}:s=720x1280:fps=30",
            "pan_right": "zoompan=z='1.1':x='if(lte(on,1),iw,max(0,x-1))':y='ih/2-(ih/zoom/2)':d={d}:s=720x1280:fps=30"
        }
        
        frames = int(duration * 30)
        effect = effects.get(direction, effects["zoom_in"]).format(d=frames)
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-vf", effect,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error creating Ken Burns effect: {e.stderr}")
            return False

