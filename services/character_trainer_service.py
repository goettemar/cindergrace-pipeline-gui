"""Service for generating character training datasets using Qwen Image Edit."""
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
class ViewPreset:
    """A preset view for character training."""
    name: str
    edit_prompt: str
    caption: str  # Caption for LoRA training


# 15 Standard views for comprehensive LoRA training
VIEW_PRESETS: List[ViewPreset] = [
    ViewPreset(
        name="01_front_neutral",
        edit_prompt="show the character from the front, facing the camera directly, neutral expression",
        caption="front view, facing camera, neutral expression"
    ),
    ViewPreset(
        name="02_front_smile",
        edit_prompt="show the character from the front, facing the camera, with a gentle smile",
        caption="front view, facing camera, gentle smile"
    ),
    ViewPreset(
        name="03_three_quarter_left",
        edit_prompt="turn the character slightly to face left, three-quarter view",
        caption="three-quarter view, facing left"
    ),
    ViewPreset(
        name="04_three_quarter_right",
        edit_prompt="turn the character slightly to face right, three-quarter view",
        caption="three-quarter view, facing right"
    ),
    ViewPreset(
        name="05_profile_left",
        edit_prompt="show the character's left profile, side view facing left",
        caption="left profile, side view"
    ),
    ViewPreset(
        name="06_profile_right",
        edit_prompt="show the character's right profile, side view facing right",
        caption="right profile, side view"
    ),
    ViewPreset(
        name="07_back_view",
        edit_prompt="show the character from behind, back view",
        caption="back view, from behind"
    ),
    ViewPreset(
        name="08_looking_up",
        edit_prompt="show the character looking upward, chin raised",
        caption="looking up, chin raised"
    ),
    ViewPreset(
        name="09_looking_down",
        edit_prompt="show the character looking downward, chin lowered",
        caption="looking down, chin lowered"
    ),
    ViewPreset(
        name="10_closeup_face",
        edit_prompt="close-up shot of the character's face, portrait view",
        caption="close-up portrait, face detail"
    ),
    ViewPreset(
        name="11_full_body",
        edit_prompt="show the full body of the character, head to toe",
        caption="full body shot, head to toe"
    ),
    ViewPreset(
        name="12_upper_body",
        edit_prompt="show the upper body of the character, bust shot from waist up",
        caption="upper body, bust shot"
    ),
    ViewPreset(
        name="13_head_tilt_left",
        edit_prompt="show the character with head tilted to the left",
        caption="head tilted left"
    ),
    ViewPreset(
        name="14_head_tilt_right",
        edit_prompt="show the character with head tilted to the right",
        caption="head tilted right"
    ),
    ViewPreset(
        name="15_dynamic_pose",
        edit_prompt="show the character in a dynamic action pose",
        caption="dynamic pose, action shot"
    ),
]


@dataclass
class ViewResult:
    """Result of generating a single view."""
    success: bool
    preset: ViewPreset
    image_path: Optional[str] = None
    caption_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class TrainingSetResult:
    """Result of generating a complete training set."""
    success: bool
    character_name: str
    output_dir: str
    views: List[ViewResult] = field(default_factory=list)
    successful_count: int = 0
    duration_seconds: float = 0
    error: Optional[str] = None


class CharacterTrainerService:
    """Service for generating character training datasets."""

    # Default workflow - can be changed via set_workflow()
    DEFAULT_WORKFLOW = "gcl_qwen_image_edit_2509.json"
    WORKFLOW_PREFIX = "gcl_"
    # Store datasets under ComfyUI for training compatibility
    OUTPUT_SUBDIR = "output/character_training"

    # Node IDs in the Qwen Edit workflow (both versions use same IDs)
    NODES = {
        "input_image": "78",
        "positive_prompt": "111",
        "negative_prompt": "110",
        "sampler": "3",
        "save_image": "60",
    }

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.api = ComfyUIAPI(self.config.get_comfy_url())
        self._workflow: Optional[Dict[str, Any]] = None
        self._workflow_file: str = self.DEFAULT_WORKFLOW

    def set_workflow(self, workflow_file: str) -> None:
        """Set the workflow file to use for generation."""
        self._workflow_file = workflow_file
        self._workflow = None  # Reset cached workflow

    def get_available_workflows(self) -> List[Tuple[str, str]]:
        """Get list of available gcl_ workflows.

        Returns:
            List of (display_name, filename) tuples
        """
        workflow_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config/workflow_templates"
        )

        workflows = []
        if os.path.exists(workflow_dir):
            for f in os.listdir(workflow_dir):
                if f.startswith(self.WORKFLOW_PREFIX) and f.endswith(".json"):
                    # Create display name from filename
                    display = f.replace(self.WORKFLOW_PREFIX, "").replace(".json", "").replace("_", " ").title()
                    workflows.append((display, f))

        return sorted(workflows, key=lambda x: x[0])

    def get_view_presets(self) -> List[ViewPreset]:
        """Get all available view presets."""
        return VIEW_PRESETS.copy()

    def _load_workflow(self) -> Dict[str, Any]:
        """Load the Qwen Image Edit workflow."""
        if self._workflow is None:
            workflow_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config/workflow_templates",
                self._workflow_file
            )
            self._workflow = self.api.load_workflow(workflow_path)
        return copy.deepcopy(self._workflow)

    def _get_output_dir(self, character_name: str) -> str:
        """Get the output directory for a character's training set.

        Stores datasets under ComfyUI directory for training compatibility.
        If the directory already exists with files, moves them to temp first.
        """
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in character_name)

        # Store under ComfyUI directory for training compatibility
        comfy_root = self.config.get_comfy_root()
        base_dir = os.path.join(comfy_root, self.OUTPUT_SUBDIR)
        output_dir = os.path.join(base_dir, safe_name)

        # If directory exists and has files, move to temp
        if os.path.exists(output_dir) and os.listdir(output_dir):
            self._backup_existing_dataset(output_dir, safe_name, base_dir)

        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _backup_existing_dataset(self, output_dir: str, safe_name: str, base_dir: str) -> None:
        """Move existing dataset to temp folder before regenerating."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_dir = os.path.join(base_dir, "temp", f"{safe_name}_{timestamp}")

        os.makedirs(os.path.dirname(temp_dir), exist_ok=True)

        try:
            shutil.move(output_dir, temp_dir)
            logger.info(f"Moved existing dataset to: {temp_dir}")
        except Exception as e:
            logger.warning(f"Could not move existing dataset: {e}")
            # If move fails, try to clear the directory
            for f in os.listdir(output_dir):
                try:
                    fpath = os.path.join(output_dir, f)
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                except Exception:
                    pass

    def _upload_image(self, image_path: str) -> str:
        """Copy image to ComfyUI input folder."""
        comfy_root = self.config.get_comfy_root()
        input_dir = os.path.join(comfy_root, "input")
        os.makedirs(input_dir, exist_ok=True)

        filename = f"char_train_{int(time.time())}_{os.path.basename(image_path)}"
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

    def _find_output_image(self, start_time: float, prefix: str) -> Optional[str]:
        """Find image file generated after start_time."""
        comfy_root = self.config.get_comfy_root()
        output_patterns = [
            os.path.join(comfy_root, "output", f"{prefix}*.png"),
            os.path.join(comfy_root, "output", "ComfyUI*.png"),
        ]

        time.sleep(1)  # Wait for file to appear

        for pattern in output_patterns:
            for filepath in glob.glob(pattern):
                if os.path.getmtime(filepath) > start_time:
                    return filepath

        return None

    def generate_view(
        self,
        base_image_path: str,
        preset: ViewPreset,
        character_name: str,
        output_dir: str,
        steps: int = 8,
        cfg: float = 1.0,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> ViewResult:
        """
        Generate a single view using Qwen Image Edit.

        Args:
            base_image_path: Path to the base character image
            preset: View preset to generate
            character_name: Name of the character (for captions)
            output_dir: Directory to save output
            steps: Sampling steps
            cfg: CFG scale
            callback: Progress callback

        Returns:
            ViewResult with image path or error
        """
        if not os.path.exists(base_image_path):
            return ViewResult(
                success=False,
                preset=preset,
                error=f"Base image not found: {base_image_path}"
            )

        uploaded_image = None
        start_time = time.time()

        try:
            if callback:
                callback(0.1, f"Uploading base image...")

            uploaded_image = self._upload_image(base_image_path)

            if callback:
                callback(0.2, f"Configuring workflow for {preset.name}...")

            workflow = self._load_workflow()

            # Set input image
            workflow[self.NODES["input_image"]]["inputs"]["image"] = uploaded_image

            # Set edit prompt
            workflow[self.NODES["positive_prompt"]]["inputs"]["prompt"] = preset.edit_prompt

            # Set empty negative prompt
            workflow[self.NODES["negative_prompt"]]["inputs"]["prompt"] = ""

            # Set sampling parameters
            sampler = workflow[self.NODES["sampler"]]["inputs"]
            sampler["steps"] = steps
            sampler["cfg"] = cfg

            # Set output prefix
            output_prefix = f"{character_name}_{preset.name}"
            workflow[self.NODES["save_image"]]["inputs"]["filename_prefix"] = output_prefix

            if callback:
                callback(0.3, f"Queuing {preset.name}...")

            generation_start = time.time()
            prompt_id = self.api.queue_prompt(workflow)
            logger.info(f"Queued view generation: {prompt_id} for {preset.name}")

            # Monitor progress
            def progress_wrapper(pct, status):
                if callback:
                    scaled = 0.3 + (pct * 0.6)
                    callback(scaled, status)

            result = self.api.monitor_progress(
                prompt_id,
                callback=progress_wrapper,
                timeout=300  # 5 minutes
            )

            if result["status"] != "success":
                return ViewResult(
                    success=False,
                    preset=preset,
                    error=result.get("error", "Generation failed")
                )

            if callback:
                callback(0.95, f"Saving {preset.name}...")

            # Find and move output image
            image_path = self._find_output_image(generation_start, output_prefix)

            if image_path:
                # Move to output directory
                dest_filename = f"{preset.name}.png"
                dest_path = os.path.join(output_dir, dest_filename)
                shutil.move(image_path, dest_path)
                image_path = dest_path

                # Save caption file
                caption_path = os.path.join(output_dir, f"{preset.name}.txt")
                full_caption = f"{character_name}, {preset.caption}"
                with open(caption_path, "w") as f:
                    f.write(full_caption)

                if callback:
                    callback(1.0, f"Completed {preset.name}")

                return ViewResult(
                    success=True,
                    preset=preset,
                    image_path=dest_path,
                    caption_path=caption_path
                )
            else:
                return ViewResult(
                    success=False,
                    preset=preset,
                    error="Output image not found"
                )

        except Exception as e:
            logger.error(f"View generation failed for {preset.name}: {e}", exc_info=True)
            return ViewResult(
                success=False,
                preset=preset,
                error=str(e)
            )
        finally:
            if uploaded_image:
                self._cleanup_image(uploaded_image)

    def generate_training_set(
        self,
        base_image_path: str,
        character_name: str,
        presets: Optional[List[ViewPreset]] = None,
        steps: int = 8,
        cfg: float = 1.0,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> TrainingSetResult:
        """
        Generate a complete training set with all views.

        Args:
            base_image_path: Path to the base character image
            character_name: Name of the character
            presets: List of presets to use (defaults to all 15)
            steps: Sampling steps
            cfg: CFG scale
            callback: Progress callback

        Returns:
            TrainingSetResult with all generated views
        """
        start_time = time.time()

        if not os.path.exists(base_image_path):
            return TrainingSetResult(
                success=False,
                character_name=character_name,
                output_dir="",
                error=f"Base image not found: {base_image_path}"
            )

        presets = presets or VIEW_PRESETS
        output_dir = self._get_output_dir(character_name)
        views: List[ViewResult] = []
        successful_count = 0

        # Copy base image to output
        base_dest = os.path.join(output_dir, "00_base_image.png")
        shutil.copy2(base_image_path, base_dest)

        # Save base caption
        base_caption_path = os.path.join(output_dir, "00_base_image.txt")
        with open(base_caption_path, "w") as f:
            f.write(f"{character_name}, reference image")

        for i, preset in enumerate(presets):
            if callback:
                overall = i / len(presets)
                callback(overall, f"Generating {preset.name} ({i + 1}/{len(presets)})")

            def view_callback(pct, status):
                if callback:
                    view_progress = (i + pct) / len(presets)
                    callback(view_progress, f"{preset.name}: {status}")

            result = self.generate_view(
                base_image_path=base_image_path,
                preset=preset,
                character_name=character_name,
                output_dir=output_dir,
                steps=steps,
                cfg=cfg,
                callback=view_callback,
            )

            views.append(result)
            if result.success:
                successful_count += 1
            else:
                logger.warning(f"View {preset.name} failed: {result.error}")

        duration = time.time() - start_time

        # Generate metadata file
        self._save_metadata(output_dir, character_name, views, duration)

        return TrainingSetResult(
            success=successful_count > 0,
            character_name=character_name,
            output_dir=output_dir,
            views=views,
            successful_count=successful_count,
            duration_seconds=duration,
            error=None if successful_count > 0 else "All views failed"
        )

    def _save_metadata(
        self,
        output_dir: str,
        character_name: str,
        views: List[ViewResult],
        duration: float
    ) -> None:
        """Save metadata JSON for the training set."""
        import json

        metadata = {
            "character_name": character_name,
            "generation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": round(duration, 2),
            "total_views": len(views),
            "successful_views": sum(1 for v in views if v.success),
            "views": [
                {
                    "name": v.preset.name,
                    "success": v.success,
                    "caption": v.preset.caption,
                    "image": os.path.basename(v.image_path) if v.image_path else None,
                    "error": v.error
                }
                for v in views
            ]
        }

        metadata_path = os.path.join(output_dir, "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Saved training set metadata to {metadata_path}")


__all__ = [
    "CharacterTrainerService",
    "ViewPreset",
    "ViewResult",
    "TrainingSetResult",
    "VIEW_PRESETS"
]
