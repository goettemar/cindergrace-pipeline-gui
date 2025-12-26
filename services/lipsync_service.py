"""Lipsync Service - Audio processing and Wan is2v workflow control."""
import os
import subprocess
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Optional, Tuple, Callable, List
from pathlib import Path

from infrastructure.config_manager import ConfigManager
from infrastructure.comfy_api.client import ComfyUIAPI
from infrastructure.logger import get_logger
from services.video.last_frame_extractor import LastFrameExtractor

logger = get_logger(__name__)


# Resolution presets for video generation
RESOLUTION_PRESETS = {
    "480p": (832, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "480p_portrait": (480, 832),
    "720p_portrait": (720, 1280),
    "640x640": (640, 640),  # Square fallback
}


@dataclass
class AudioInfo:
    """Information about an audio file."""
    path: str
    duration: float  # seconds
    sample_rate: int
    channels: int
    format: str


@dataclass
class LipsyncJob:
    """Represents a lipsync generation job."""
    image_path: str
    audio_path: str
    prompt: str
    negative_prompt: str
    width: int
    height: int
    output_name: str
    steps: int = 4
    cfg: float = 1.0
    fps: int = 16
    chunk_length: int = 77  # frames per chunk


@dataclass
class BatchSegment:
    """A segment for batch lipsync generation."""
    audio_path: str
    start_time: float
    end_time: float
    segment_index: int
    use_last_frame: bool = False  # Use last frame from previous segment as start image


@dataclass
class BatchResult:
    """Result of batch lipsync generation."""
    success: bool
    videos: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_segments: int = 0
    completed_segments: int = 0


class LipsyncService:
    """Service for lipsync video generation using Wan 2.2 is2v."""

    MAX_DURATION_SECONDS = 14.0  # ~3 chunks at 77 frames each @ 16fps
    DEFAULT_WORKFLOW = "gcl_wan_2.2_is2v.json"

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.api: Optional[ComfyUIAPI] = None
        self._ffmpeg_path = self._find_ffmpeg()
        self._frame_extractor = LastFrameExtractor()

    def _find_ffmpeg(self) -> str:
        """Find ffmpeg executable."""
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
        # Common locations
        for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
            if os.path.isfile(path):
                return path
        return "ffmpeg"  # Hope it's in PATH

    def _get_api(self) -> ComfyUIAPI:
        """Get or create ComfyUI API client."""
        if self.api is None:
            comfy_url = self.config.get("comfy_url", "http://127.0.0.1:8188")
            self.api = ComfyUIAPI(server_url=comfy_url)
        return self.api

    def get_audio_info(self, audio_path: str) -> Optional[AudioInfo]:
        """Get information about an audio file using ffprobe.

        Args:
            audio_path: Path to audio file

        Returns:
            AudioInfo object or None if failed
        """
        if not os.path.isfile(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return None

        try:
            # Get duration
            result = subprocess.run(
                [
                    self._ffmpeg_path.replace("ffmpeg", "ffprobe"),
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-show_entries", "stream=sample_rate,channels",
                    "-of", "csv=p=0",
                    audio_path
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.error(f"ffprobe failed: {result.stderr}")
                return None

            lines = result.stdout.strip().split("\n")

            # Parse output
            duration = 0.0
            sample_rate = 44100
            channels = 2

            for line in lines:
                parts = line.split(",")
                if len(parts) >= 1:
                    try:
                        # Try to parse as duration
                        duration = float(parts[0])
                    except ValueError:
                        pass
                if len(parts) >= 2:
                    try:
                        sample_rate = int(parts[0])
                        channels = int(parts[1])
                    except ValueError:
                        pass

            # Get format from extension
            fmt = Path(audio_path).suffix.lower().lstrip(".")

            return AudioInfo(
                path=audio_path,
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                format=fmt
            )
        except subprocess.TimeoutExpired:
            logger.error("ffprobe timed out")
            return None
        except Exception as e:
            logger.error(f"Failed to get audio info: {e}")
            return None

    def trim_audio(
        self,
        input_path: str,
        output_path: str,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        max_duration: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Trim audio file to specified time range.

        Args:
            input_path: Source audio file
            output_path: Destination path
            start_time: Start time in seconds
            end_time: End time in seconds (None = to end)
            max_duration: Maximum duration (overrides end_time if shorter)

        Returns:
            Tuple of (success, message)
        """
        if not os.path.isfile(input_path):
            return False, f"Input file not found: {input_path}"

        # Calculate duration
        if end_time is not None:
            duration = end_time - start_time
        else:
            duration = None

        if max_duration is not None:
            if duration is None or duration > max_duration:
                duration = max_duration

        # Build ffmpeg command
        cmd = [
            self._ffmpeg_path,
            "-y",  # Overwrite output
            "-i", input_path,
            "-ss", str(start_time),
        ]

        if duration is not None:
            cmd.extend(["-t", str(duration)])

        # Output settings - convert to WAV for best compatibility
        cmd.extend([
            "-acodec", "pcm_s16le",
            "-ar", "16000",  # 16kHz for wav2vec2
            "-ac", "1",  # Mono
            output_path
        ])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                logger.error(f"ffmpeg trim failed: {result.stderr}")
                return False, f"Trim failed: {result.stderr[:200]}"

            logger.info(f"Audio trimmed: {input_path} -> {output_path}")
            return True, f"Audio trimmed successfully"

        except subprocess.TimeoutExpired:
            return False, "Trim operation timed out"
        except Exception as e:
            logger.error(f"Trim failed: {e}")
            return False, f"Trim failed: {str(e)}"

    def copy_to_comfy_input(self, file_path: str, filename: str) -> Tuple[bool, str]:
        """Copy a file to ComfyUI's input directory.

        Args:
            file_path: Source file path
            filename: Target filename in ComfyUI input

        Returns:
            Tuple of (success, target_path or error message)
        """
        comfy_root = self.config.get_comfy_root()
        if not comfy_root:
            return False, "ComfyUI root not configured"

        input_dir = os.path.join(comfy_root, "input")
        os.makedirs(input_dir, exist_ok=True)

        target_path = os.path.join(input_dir, filename)

        try:
            shutil.copy2(file_path, target_path)
            logger.info(f"Copied to ComfyUI input: {target_path}")
            return True, target_path
        except Exception as e:
            logger.error(f"Failed to copy to ComfyUI input: {e}")
            return False, str(e)

    def prepare_workflow(self, job: LipsyncJob, workflow: dict) -> dict:
        """Update workflow with job parameters.

        Args:
            job: LipsyncJob with all parameters
            workflow: Workflow dictionary to update

        Returns:
            Updated workflow dictionary
        """
        # Update LoadImage (Node 52)
        if "52" in workflow:
            workflow["52"]["inputs"]["image"] = os.path.basename(job.image_path)

        # Update LoadAudio (Node 58)
        if "58" in workflow:
            workflow["58"]["inputs"]["audio"] = os.path.basename(job.audio_path)

        # Update positive prompt (Node 6)
        if "6" in workflow:
            workflow["6"]["inputs"]["text"] = job.prompt

        # Update negative prompt (Node 7) - keep default if not specified
        if "7" in workflow and job.negative_prompt:
            workflow["7"]["inputs"]["text"] = job.negative_prompt

        # Update resolution in WanSoundImageToVideo (Node 93)
        if "93" in workflow:
            workflow["93"]["inputs"]["width"] = job.width
            workflow["93"]["inputs"]["height"] = job.height

        # Update steps (Node 103)
        if "103" in workflow:
            workflow["103"]["inputs"]["value"] = job.steps

        # Update CFG (Node 105)
        if "105" in workflow:
            workflow["105"]["inputs"]["value"] = job.cfg

        # Update output filename (Node 113)
        if "113" in workflow:
            workflow["113"]["inputs"]["filename_prefix"] = f"lipsync/{job.output_name}"

        # Update FPS in CreateVideo (Node 82)
        if "82" in workflow:
            workflow["82"]["inputs"]["fps"] = job.fps

        return workflow

    def generate_lipsync(
        self,
        job: LipsyncJob,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        workflow_file: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Generate lipsync video.

        Args:
            job: LipsyncJob with all parameters
            progress_callback: Optional callback for progress updates
            workflow_file: Optional workflow filename (defaults to DEFAULT_WORKFLOW)

        Returns:
            Tuple of (success, output_path or error message)
        """
        api = self._get_api()

        # Load workflow
        workflow_dir = self.config.get("workflow_dir", "config/workflow_templates")
        selected_workflow = workflow_file or self.DEFAULT_WORKFLOW
        workflow_path = os.path.join(workflow_dir, selected_workflow)

        if not os.path.isfile(workflow_path):
            return False, f"Workflow not found: {workflow_path}"

        try:
            workflow = api.load_workflow(workflow_path)
        except Exception as e:
            return False, f"Failed to load workflow: {e}"

        # Copy files to ComfyUI input
        image_filename = f"lipsync_image_{os.path.basename(job.image_path)}"
        success, result = self.copy_to_comfy_input(job.image_path, image_filename)
        if not success:
            return False, f"Failed to copy image: {result}"

        audio_filename = f"lipsync_audio_{os.path.basename(job.audio_path)}"
        success, result = self.copy_to_comfy_input(job.audio_path, audio_filename)
        if not success:
            return False, f"Failed to copy audio: {result}"

        # Update job paths to use ComfyUI input filenames
        job.image_path = image_filename
        job.audio_path = audio_filename

        # Prepare workflow
        workflow = self.prepare_workflow(job, workflow)

        # Queue job
        if progress_callback:
            progress_callback(0.1, "Queuing job...")

        try:
            prompt_id = api.queue_prompt(workflow)
        except Exception as e:
            return False, f"Failed to queue job: {e}"

        # Monitor progress
        if progress_callback:
            progress_callback(0.2, "Generating lipsync video...")

        try:
            result = api.monitor_progress(
                prompt_id,
                callback=lambda pct, status: progress_callback(
                    0.2 + pct * 0.7, status
                ) if progress_callback else None
            )
        except Exception as e:
            return False, f"Generation failed: {e}"

        if progress_callback:
            progress_callback(0.95, "Finalizing...")

        # Get output path
        comfy_root = self.config.get_comfy_root()
        if comfy_root:
            output_dir = os.path.join(comfy_root, "output", "lipsync")
            # Find the generated video
            if os.path.isdir(output_dir):
                videos = sorted(
                    [f for f in os.listdir(output_dir) if f.endswith(('.mp4', '.webm'))],
                    key=lambda x: os.path.getmtime(os.path.join(output_dir, x)),
                    reverse=True
                )
                if videos:
                    output_path = os.path.join(output_dir, videos[0])
                    if progress_callback:
                        progress_callback(1.0, "Complete!")
                    return True, output_path

        if progress_callback:
            progress_callback(1.0, "Complete (output path unknown)")
        return True, "Generation complete (check ComfyUI output/lipsync/)"

    def get_resolution(self, preset: str) -> Tuple[int, int]:
        """Get resolution from preset name.

        Args:
            preset: Resolution preset name (e.g., '720p', '1080p')

        Returns:
            Tuple of (width, height)
        """
        return RESOLUTION_PRESETS.get(preset, (1280, 720))

    def generate_character_image(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        workflow_file: str,
        seed: int = -1,
        steps: int = 20,
        cfg: float = 7.0,
        lora_name: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[bool, str]:
        """Generate a character image using Flux.

        Args:
            prompt: Text prompt for generation
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            workflow_file: Flux workflow file (gcp_*)
            seed: Random seed (-1 for random)
            steps: Sampling steps
            cfg: CFG scale
            lora_name: Optional LoRA name (cg_* format)
            progress_callback: Optional progress callback

        Returns:
            Tuple of (success, image_path or error message)
        """
        api = self._get_api()

        # Load workflow
        workflow_dir = self.config.get("workflow_dir", "config/workflow_templates")
        workflow_path = os.path.join(workflow_dir, workflow_file)

        if not os.path.isfile(workflow_path):
            return False, f"Workflow not found: {workflow_path}"

        try:
            workflow = api.load_workflow(workflow_path)
        except Exception as e:
            return False, f"Failed to load workflow: {e}"

        # Update workflow parameters
        # Find and update relevant nodes
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})

            # Update prompt nodes
            if class_type == "CLIPTextEncode":
                title = node_data.get("_meta", {}).get("title", "").lower()
                if "positive" in title or "prompt" in title:
                    inputs["text"] = prompt
                elif "negative" in title:
                    inputs["text"] = negative_prompt

            # Update sampler
            if class_type in ["KSampler", "KSamplerAdvanced"]:
                if seed != -1:
                    inputs["seed"] = seed
                inputs["steps"] = steps
                inputs["cfg"] = cfg

            # Update latent image size
            if class_type in ["EmptyLatentImage", "EmptySD3LatentImage"]:
                inputs["width"] = width
                inputs["height"] = height

            # Update LoRA if specified
            if lora_name and class_type == "LoraLoader":
                inputs["lora_name"] = f"{lora_name}.safetensors"

        if progress_callback:
            progress_callback(0.1, "Queuing generation...")

        try:
            prompt_id = api.queue_prompt(workflow)
        except Exception as e:
            return False, f"Failed to queue: {e}"

        if progress_callback:
            progress_callback(0.2, "Generating image...")

        try:
            result = api.monitor_progress(
                prompt_id,
                callback=lambda pct, status: progress_callback(
                    0.2 + pct * 0.7, status
                ) if progress_callback else None
            )
        except Exception as e:
            return False, f"Generation failed: {e}"

        # Find output image
        comfy_root = self.config.get_comfy_root()
        if comfy_root:
            output_dir = os.path.join(comfy_root, "output")
            if os.path.isdir(output_dir):
                # Find most recent PNG
                pngs = []
                for f in os.listdir(output_dir):
                    if f.endswith('.png'):
                        full_path = os.path.join(output_dir, f)
                        pngs.append((full_path, os.path.getmtime(full_path)))

                if pngs:
                    pngs.sort(key=lambda x: x[1], reverse=True)
                    if progress_callback:
                        progress_callback(1.0, "Complete!")
                    return True, pngs[0][0]

        return False, "Generation complete but output not found"

    def generate_batch_lipsync(
        self,
        base_image_path: str,
        segments: List[BatchSegment],
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        workflow_file: str,
        output_prefix: str = "lipsync_batch",
        steps: int = 4,
        cfg: float = 1.0,
        fps: int = 16,
        use_last_frame_chaining: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> BatchResult:
        """Generate lipsync videos for multiple audio segments with frame chaining.

        Args:
            base_image_path: Starting character image
            segments: List of audio segments to process
            prompt: Text prompt for movement/emotion
            negative_prompt: Negative prompt
            width: Video width
            height: Video height
            workflow_file: Lipsync workflow file
            output_prefix: Prefix for output files
            steps: Sampling steps
            cfg: CFG scale
            fps: Frames per second
            use_last_frame_chaining: Use last frame of segment N as start for N+1
            progress_callback: Callback (current_segment, total_segments, status)

        Returns:
            BatchResult with generated videos
        """
        result = BatchResult(
            success=True,
            total_segments=len(segments)
        )

        if not segments:
            result.success = False
            result.errors.append("No segments provided")
            return result

        current_image = base_image_path
        temp_dir = tempfile.mkdtemp(prefix="lipsync_batch_")

        for i, segment in enumerate(segments):
            if progress_callback:
                progress_callback(i + 1, len(segments), f"Processing segment {i + 1}/{len(segments)}")

            # Create job for this segment
            job = LipsyncJob(
                image_path=current_image,
                audio_path=segment.audio_path,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                output_name=f"{output_prefix}_seg{i + 1:03d}",
                steps=steps,
                cfg=cfg,
                fps=fps
            )

            # Generate lipsync for this segment
            success, video_path = self.generate_lipsync(
                job,
                progress_callback=None,
                workflow_file=workflow_file
            )

            if success and os.path.isfile(video_path):
                result.videos.append(video_path)
                result.completed_segments += 1

                # Extract last frame for chaining
                if use_last_frame_chaining and i < len(segments) - 1:
                    last_frame = self._frame_extractor.extract(video_path)
                    if last_frame:
                        current_image = last_frame
                        logger.info(f"Using last frame for next segment: {last_frame}")
                    else:
                        logger.warning(f"Could not extract last frame from {video_path}")
            else:
                error_msg = video_path if not success else "Unknown error"
                result.errors.append(f"Segment {i + 1}: {error_msg}")
                logger.error(f"Segment {i + 1} failed: {error_msg}")

        result.success = result.completed_segments == result.total_segments

        if progress_callback:
            status = "Complete!" if result.success else f"Completed with {len(result.errors)} errors"
            progress_callback(len(segments), len(segments), status)

        return result

    def concatenate_videos(
        self,
        video_paths: List[str],
        output_path: str,
        crossfade_duration: float = 0.5
    ) -> Tuple[bool, str]:
        """Concatenate multiple videos into one with optional crossfade.

        Args:
            video_paths: List of video file paths
            output_path: Output file path
            crossfade_duration: Duration of crossfade between clips (0 for hard cut)

        Returns:
            Tuple of (success, output_path or error message)
        """
        if not video_paths:
            return False, "No videos to concatenate"

        if len(video_paths) == 1:
            shutil.copy2(video_paths[0], output_path)
            return True, output_path

        try:
            if crossfade_duration > 0:
                # Complex filter for crossfade
                filter_parts = []
                for i, _ in enumerate(video_paths):
                    filter_parts.append(f"[{i}:v][{i}:a]")

                # Build xfade filter chain
                # This is simplified - full implementation would need proper filter graph
                # For now, use simple concat
                crossfade_duration = 0

            # Create concat file
            concat_file = os.path.join(tempfile.gettempdir(), "concat_list.txt")
            with open(concat_file, "w") as f:
                for vp in video_paths:
                    f.write(f"file '{vp}'\n")

            cmd = [
                self._ffmpeg_path,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                output_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            # Cleanup
            os.remove(concat_file)

            if result.returncode != 0:
                return False, f"Concatenation failed: {result.stderr[:200]}"

            return True, output_path

        except Exception as e:
            logger.error(f"Video concatenation failed: {e}")
            return False, str(e)
