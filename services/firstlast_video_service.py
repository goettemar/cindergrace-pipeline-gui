"""Service for generating First/Last Frame videos using Wan 2.2."""
import copy
import glob
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from infrastructure.comfy_api.client import ComfyUIAPI
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TransitionResult:
    """Result of a single transition (frame A → frame B)."""
    success: bool
    start_image: str
    end_image: str
    video_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ClipResult:
    """Result of a clip (multiple transitions merged)."""
    success: bool
    clip_index: int
    transitions: List[TransitionResult] = field(default_factory=list)
    merged_video: Optional[str] = None
    error: Optional[str] = None


@dataclass
class GenerationResult:
    """Result of full generation job."""
    success: bool
    clips: List[ClipResult] = field(default_factory=list)
    total_transitions: int = 0
    duration_seconds: float = 0
    error: Optional[str] = None


class FirstLastVideoService:
    """Service for generating First/Last Frame transition videos."""

    DEFAULT_WORKFLOW_FILE = "config/workflow_templates/gcvfl_wan_2.2_14b_flf2v.json"
    OUTPUT_DIR = "output/firstlast"

    # Node IDs in the workflow
    NODES = {
        "start_image": "80",
        "end_image": "89",
        "positive_prompt": "90",
        "negative_prompt": "78",
        "wan_flf": "81",  # WanFirstLastFrameToVideo
        "sampler_high": "84",
        "sampler_low": "87",
        "create_video": "86",
        "save_video": "83",
    }

    # Default negative prompt (Chinese, from original workflow)
    DEFAULT_NEGATIVE = (
        "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，"
        "整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
        "画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，"
        "静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
    )

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.api = ComfyUIAPI(self.config.get_comfy_url())
        self._workflow: Optional[Dict[str, Any]] = None
        self._current_workflow_file: Optional[str] = None

    def _load_workflow(self, workflow_file: Optional[str] = None) -> Dict[str, Any]:
        """Load the First/Last Frame workflow.

        Args:
            workflow_file: Workflow filename (e.g., 'gcvfl_wan_2.2_14b_flf2v.json')
                          If None, uses DEFAULT_WORKFLOW_FILE
        """
        # Determine workflow path
        if workflow_file:
            workflow_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config/workflow_templates",
                workflow_file
            )
        else:
            workflow_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                self.DEFAULT_WORKFLOW_FILE
            )

        # Reload if different workflow or not cached
        if self._workflow is None or self._current_workflow_file != workflow_file:
            self._workflow = self.api.load_workflow(workflow_path)
            self._current_workflow_file = workflow_file
            logger.debug(f"Loaded workflow: {workflow_file or 'default'}")

        return copy.deepcopy(self._workflow)

    def _get_output_dir(self) -> str:
        """Get the output directory for generated videos."""
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            self.OUTPUT_DIR
        )
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _upload_image(self, image_path: str, prefix: str = "flf") -> str:
        """Copy image to ComfyUI input folder."""
        comfy_root = self.config.get_comfy_root()
        input_dir = os.path.join(comfy_root, "input")
        os.makedirs(input_dir, exist_ok=True)

        # Use unique filename
        filename = f"{prefix}_{int(time.time())}_{os.path.basename(image_path)}"
        target_path = os.path.join(input_dir, filename)

        shutil.copy2(image_path, target_path)
        logger.debug(f"Copied image to ComfyUI input: {filename}")

        return filename

    def _cleanup_image(self, filename: str) -> None:
        """Remove temporary image from ComfyUI input."""
        try:
            comfy_root = self.config.get_comfy_root()
            input_path = os.path.join(comfy_root, "input", filename)
            if os.path.exists(input_path):
                os.remove(input_path)
                logger.debug(f"Cleaned up image: {filename}")
        except Exception as e:
            logger.warning(f"Could not cleanup image {filename}: {e}")

    def _find_output_video(self, start_time: float, prefix: str) -> Optional[str]:
        """Find video file generated after start_time."""
        comfy_root = self.config.get_comfy_root()
        output_patterns = [
            os.path.join(comfy_root, "output", "video", f"{prefix}*.mp4"),
            os.path.join(comfy_root, "output", "video", "ComfyUI*.mp4"),
            os.path.join(comfy_root, "output", f"{prefix}*.mp4"),
        ]

        # Wait a bit for file to appear
        time.sleep(2)

        for pattern in output_patterns:
            for filepath in glob.glob(pattern):
                if os.path.getmtime(filepath) > start_time:
                    return filepath

        return None

    def generate_transition(
        self,
        start_image_path: str,
        end_image_path: str,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1280,
        height: int = 720,
        frames: int = 81,
        fps: int = 16,
        steps: int = 20,
        cfg: float = 4.0,
        output_prefix: str = "transition",
        callback: Optional[Callable[[float, str], None]] = None,
        workflow_file: Optional[str] = None,
    ) -> TransitionResult:
        """
        Generate a single transition video from start to end image.

        Args:
            start_image_path: Path to the starting image
            end_image_path: Path to the ending image
            prompt: Positive prompt describing the transition
            negative_prompt: Negative prompt (uses default if None)
            width: Output width
            height: Output height
            frames: Number of frames (81 = ~5s at 16fps)
            fps: Frames per second
            steps: Sampling steps
            cfg: CFG scale
            output_prefix: Prefix for output filename
            callback: Progress callback(progress_pct, status_text)
            workflow_file: Optional workflow filename (gcvfl_*.json)

        Returns:
            TransitionResult with video path or error
        """
        if not os.path.exists(start_image_path):
            return TransitionResult(
                success=False,
                start_image=start_image_path,
                end_image=end_image_path,
                error=f"Start image not found: {start_image_path}"
            )

        if not os.path.exists(end_image_path):
            return TransitionResult(
                success=False,
                start_image=start_image_path,
                end_image=end_image_path,
                error=f"End image not found: {end_image_path}"
            )

        uploaded_start = None
        uploaded_end = None
        start_time = time.time()

        try:
            # Step 1: Upload images
            if callback:
                callback(0.05, "Uploading images...")
            uploaded_start = self._upload_image(start_image_path, "flf_start")
            uploaded_end = self._upload_image(end_image_path, "flf_end")

            # Step 2: Load and configure workflow
            if callback:
                callback(0.1, "Configuring workflow...")
            workflow = self._load_workflow(workflow_file)

            # Set images
            workflow[self.NODES["start_image"]]["inputs"]["image"] = uploaded_start
            workflow[self.NODES["end_image"]]["inputs"]["image"] = uploaded_end

            # Set prompts
            workflow[self.NODES["positive_prompt"]]["inputs"]["text"] = prompt
            workflow[self.NODES["negative_prompt"]]["inputs"]["text"] = (
                negative_prompt or self.DEFAULT_NEGATIVE
            )

            # Set resolution and frames
            wan_node = workflow[self.NODES["wan_flf"]]["inputs"]
            wan_node["width"] = width
            wan_node["height"] = height
            wan_node["length"] = frames

            # Set FPS
            workflow[self.NODES["create_video"]]["inputs"]["fps"] = fps

            # Set sampling parameters
            for sampler_key in ["sampler_high", "sampler_low"]:
                sampler = workflow[self.NODES[sampler_key]]["inputs"]
                sampler["steps"] = steps
                sampler["cfg"] = cfg

            # Set output prefix
            workflow[self.NODES["save_video"]]["inputs"]["filename_prefix"] = f"video/{output_prefix}"

            if callback:
                callback(0.15, f"Configured: {width}x{height}, {frames} frames")

            # Step 3: Queue workflow
            if callback:
                callback(0.2, "Queuing workflow...")

            generation_start = time.time()
            prompt_id = self.api.queue_prompt(workflow)
            logger.info(f"Queued First/Last Frame job: {prompt_id}")

            # Step 4: Monitor progress
            def progress_wrapper(pct, status):
                if callback:
                    scaled = 0.2 + (pct * 0.7)
                    callback(scaled, status)

            result = self.api.monitor_progress(
                prompt_id,
                callback=progress_wrapper,
                timeout=600  # 10 minutes
            )

            if result["status"] != "success":
                return TransitionResult(
                    success=False,
                    start_image=start_image_path,
                    end_image=end_image_path,
                    error=result.get("error", "Unknown error during generation")
                )

            # Step 5: Find and move output video
            if callback:
                callback(0.95, "Collecting output...")

            video_path = self._find_output_video(generation_start, output_prefix)

            if video_path:
                # Move to our output directory
                output_dir = self._get_output_dir()
                dest_filename = f"{output_prefix}_{int(time.time())}.mp4"
                dest_path = os.path.join(output_dir, dest_filename)
                shutil.move(video_path, dest_path)
                video_path = dest_path

            if callback:
                callback(1.0, "Complete")

            return TransitionResult(
                success=True,
                start_image=start_image_path,
                end_image=end_image_path,
                video_path=video_path
            )

        except Exception as e:
            logger.error(f"First/Last Frame generation failed: {e}", exc_info=True)
            return TransitionResult(
                success=False,
                start_image=start_image_path,
                end_image=end_image_path,
                error=str(e)
            )
        finally:
            if uploaded_start:
                self._cleanup_image(uploaded_start)
            if uploaded_end:
                self._cleanup_image(uploaded_end)

    def generate_clip(
        self,
        image_paths: List[str],
        prompt: str,
        clip_index: int = 0,
        negative_prompt: Optional[str] = None,
        width: int = 1280,
        height: int = 720,
        frames: int = 81,
        fps: int = 16,
        steps: int = 20,
        cfg: float = 4.0,
        callback: Optional[Callable[[float, str], None]] = None,
        workflow_file: Optional[str] = None,
    ) -> ClipResult:
        """
        Generate a clip from multiple images (creates transitions between consecutive images).

        Args:
            image_paths: List of image paths (minimum 2)
            prompt: Positive prompt
            clip_index: Index of this clip (for naming)
            ... (same as generate_transition)

        Returns:
            ClipResult with all transition videos
        """
        if len(image_paths) < 2:
            return ClipResult(
                success=False,
                clip_index=clip_index,
                error="Need at least 2 images to create a clip"
            )

        transitions: List[TransitionResult] = []
        num_transitions = len(image_paths) - 1

        for i in range(num_transitions):
            start_img = image_paths[i]
            end_img = image_paths[i + 1]

            if callback:
                callback(
                    i / num_transitions,
                    f"Clip {clip_index + 1}: Transition {i + 1}/{num_transitions}"
                )

            def transition_callback(pct, status):
                if callback:
                    overall = (i + pct) / num_transitions
                    callback(overall, f"Clip {clip_index + 1}: {status}")

            result = self.generate_transition(
                start_image_path=start_img,
                end_image_path=end_img,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                frames=frames,
                fps=fps,
                steps=steps,
                cfg=cfg,
                output_prefix=f"clip{clip_index + 1:02d}_trans{i + 1:02d}",
                callback=transition_callback,
                workflow_file=workflow_file,
            )
            transitions.append(result)

            if not result.success:
                logger.warning(f"Transition {i + 1} failed: {result.error}")

        # Check if any transitions succeeded
        successful = [t for t in transitions if t.success]

        return ClipResult(
            success=len(successful) > 0,
            clip_index=clip_index,
            transitions=transitions,
            error=None if successful else "All transitions failed"
        )

    def generate_all_clips(
        self,
        clips: List[List[str]],
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1280,
        height: int = 720,
        frames: int = 81,
        fps: int = 16,
        steps: int = 20,
        cfg: float = 4.0,
        callback: Optional[Callable[[float, str], None]] = None,
        workflow_file: Optional[str] = None,
    ) -> GenerationResult:
        """
        Generate all clips from grouped images.

        Args:
            clips: List of clip groups, each group is a list of image paths
            prompt: Positive prompt (used for all transitions)
            ... (same parameters as generate_transition)

        Returns:
            GenerationResult with all clips
        """
        start_time = time.time()
        clip_results: List[ClipResult] = []
        total_transitions = sum(max(0, len(clip) - 1) for clip in clips)

        if total_transitions == 0:
            return GenerationResult(
                success=False,
                error="No transitions to generate (need at least 2 images per clip)"
            )

        transitions_done = 0

        for clip_idx, clip_images in enumerate(clips):
            if len(clip_images) < 2:
                logger.warning(f"Clip {clip_idx + 1} has less than 2 images, skipping")
                continue

            def clip_callback(pct, status):
                if callback:
                    clip_transitions = len(clip_images) - 1
                    overall = (transitions_done + pct * clip_transitions) / total_transitions
                    callback(overall, status)

            result = self.generate_clip(
                image_paths=clip_images,
                prompt=prompt,
                clip_index=clip_idx,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                frames=frames,
                fps=fps,
                steps=steps,
                cfg=cfg,
                callback=clip_callback,
                workflow_file=workflow_file,
            )
            clip_results.append(result)
            transitions_done += len(clip_images) - 1

        duration = time.time() - start_time
        successful_clips = [c for c in clip_results if c.success]

        return GenerationResult(
            success=len(successful_clips) > 0,
            clips=clip_results,
            total_transitions=total_transitions,
            duration_seconds=duration,
            error=None if successful_clips else "All clips failed"
        )


__all__ = ["FirstLastVideoService", "TransitionResult", "ClipResult", "GenerationResult"]
