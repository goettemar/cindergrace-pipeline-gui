"""Service layer for keyframe generation (Phase 1)."""
import os
import glob
import shutil
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple, Generator, Optional

from infrastructure.project_store import ProjectStore
from infrastructure.workflow_registry import WorkflowRegistry
from infrastructure.config_manager import ConfigManager
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.logger import get_logger
from domain.models import Storyboard

logger = get_logger(__name__)


class KeyframeService:
    """Encapsulate logic for running Flux keyframe generation."""

    def __init__(
        self,
        project_store: ProjectStore,
        config: ConfigManager,
        workflow_registry: WorkflowRegistry
    ):
        self.project_store = project_store
        self.config = config
        self.workflow_registry = workflow_registry

    def prepare_checkpoint(
        self,
        storyboard: Storyboard,
        workflow_file: str,
        variants_per_shot: int,
        base_seed: int
    ) -> Dict[str, Any]:
        return {
            "storyboard_file": storyboard.raw.get("storyboard_file"),
            "workflow_file": workflow_file,
            "variants_per_shot": int(variants_per_shot),
            "base_seed": int(base_seed),
            "started_at": datetime.now().isoformat(),
            "completed_shots": [],
            "current_shot": None,
            "total_images_generated": 0,
            "status": "running",
        }


class KeyframeGenerationService:
    """Service for generating keyframe variants using ComfyUI.

    Extracted from KeyframeGeneratorAddon to reduce complexity and improve testability.
    """

    def __init__(
        self,
        config: ConfigManager,
        project_store: ProjectStore,
        comfy_api: Optional[ComfyUIAPI] = None
    ):
        """
        Initialize the keyframe generation service.

        Args:
            config: Configuration manager
            project_store: Project path management
            comfy_api: Optional ComfyUI API instance
        """
        self.config = config
        self.project_store = project_store
        self.api = comfy_api
        self.is_running = False
        self.stop_requested = False

    def run_generation(
        self,
        storyboard: Storyboard,
        workflow_file: str,
        checkpoint: Dict[str, Any],
        project: Dict[str, Any],
        comfy_url: str,
        progress_callback=None
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """
        Run the complete keyframe generation process.

        Args:
            storyboard: Loaded storyboard
            workflow_file: Workflow template filename
            checkpoint: Generation checkpoint state
            project: Active project metadata
            comfy_url: ComfyUI server URL
            progress_callback: Optional progress reporting function

        Yields:
            Tuple of (images, status, progress_md, checkpoint, current_shot)
        """
        try:
            # Initialize API and test connection
            self.api = ComfyUIAPI(comfy_url)
            self.is_running = True

            conn_result = self.api.test_connection()
            if not conn_result["connected"]:
                self.is_running = False
                yield [], f"**❌ Error:** Connection failed - {conn_result['error']}", \
                      "Connection failed", checkpoint, "Error"
                return

            # Load workflow template
            workflow_path = os.path.join(self.config.get_workflow_dir(), workflow_file)
            if not os.path.exists(workflow_path):
                yield [], f"**❌ Error:** Workflow not found: `{workflow_path}`", \
                      "Workflow missing", checkpoint, "Error"
                return

            workflow = self.api.load_workflow(workflow_path)

            # Extract generation settings
            variants_per_shot = checkpoint["variants_per_shot"]
            base_seed = checkpoint["base_seed"]
            completed_shots = set(checkpoint.get("completed_shots", []))

            # Prepare output directory
            output_dir = self.project_store.ensure_dir(project, "keyframes")
            os.makedirs(output_dir, exist_ok=True)

            all_generated_images = []
            shots = storyboard.raw.get("shots", [])
            total_shots = len(shots)
            total_images_est = max(1, total_shots * variants_per_shot)
            images_done = len(completed_shots) * variants_per_shot

            logger.info(f"Starting keyframe generation: {total_shots} shots, "
                       f"{variants_per_shot} variants each")

            # Initial update
            yield [], "**Status:** 🚀 Starte Keyframe-Generation...", \
                  self._format_progress(checkpoint, total_shots), checkpoint, "**Current Shot:** None"

            # Generate keyframes for each shot
            for shot_idx, shot in enumerate(shots):
                # Check for stop request
                if self.stop_requested:
                    yield from self._handle_stop(checkpoint, all_generated_images, total_shots, project)
                    return

                shot_id = shot.get("shot_id", f"{shot_idx+1:03d}")

                # Skip already completed shots
                if shot_id in completed_shots:
                    logger.info(f"Skipping shot {shot_id} (already completed)")
                    continue

                # Generate this shot's variants
                generator = self._generate_shot(
                    shot=shot,
                    shot_idx=shot_idx,
                    shot_id=shot_id,
                    workflow=workflow,
                    variants_per_shot=variants_per_shot,
                    base_seed=base_seed,
                    output_dir=output_dir,
                    checkpoint=checkpoint,
                    total_shots=total_shots,
                    project=project,
                    images_done=images_done,
                    total_images_est=total_images_est,
                    progress_callback=progress_callback
                )

                for shot_images, status, progress_md, updated_checkpoint, current_shot in generator:
                    all_generated_images.extend(shot_images)
                    images_done += len(shot_images)
                    checkpoint = updated_checkpoint
                    yield all_generated_images, status, progress_md, checkpoint, current_shot

            # Mark as completed
            checkpoint["status"] = "completed"
            checkpoint["completed_at"] = datetime.now().isoformat()
            self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)

            status = (f"**✅ Generation Complete!** Generated {checkpoint['total_images_generated']} "
                     f"keyframes for {len(checkpoint['completed_shots'])} shots")
            progress_details = self._format_progress(checkpoint, total_shots)

            logger.info(f"Generation complete: {checkpoint['total_images_generated']} images")

            self.is_running = False
            self.stop_requested = False
            yield all_generated_images, status, progress_details, checkpoint, "Complete"

        except Exception as e:
            checkpoint["status"] = "error"
            checkpoint["error"] = str(e)
            self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)
            self.is_running = False
            self.stop_requested = False

            logger.error(f"Generation failed: {e}", exc_info=True)
            yield [], f"**❌ Error:** {str(e)}", "Generation failed", checkpoint, "Error"

    def _generate_shot(
        self,
        shot: Dict[str, Any],
        shot_idx: int,
        shot_id: str,
        workflow: Dict[str, Any],
        variants_per_shot: int,
        base_seed: int,
        output_dir: str,
        checkpoint: Dict[str, Any],
        total_shots: int,
        project: Dict[str, Any],
        images_done: int,
        total_images_est: int,
        progress_callback=None
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """Generate all variants for a single shot."""
        checkpoint["current_shot"] = shot_id
        current_shot_display = f"**Current Shot:** {shot_id} - {shot.get('description', 'No description')}"
        progress_details = self._format_progress(checkpoint, total_shots)

        if progress_callback and callable(progress_callback):
            progress_callback(min(0.95, images_done / total_images_est), desc=f"{shot_id}: Start")

        yield [], f"**Status:** ▶️ Shot {shot_id} gestartet", progress_details, \
              checkpoint, current_shot_display

        logger.info(f"Starting shot {shot_id} ({shot_idx + 1}/{total_shots})")

        shot_images = []
        filename_base = shot.get("filename_base", f"shot_{shot_id}")
        res_width, res_height = self.config.get_resolution_tuple()

        # Clean up any leftover files from previous runs for this shot
        self._cleanup_old_files(filename_base)

        # Generate variants for this shot
        for variant_idx in range(variants_per_shot):
            if self.stop_requested:
                return

            variant_generator = self._generate_variant(
                shot=shot,
                shot_id=shot_id,
                shot_idx=shot_idx,
                variant_idx=variant_idx,
                variants_per_shot=variants_per_shot,
                filename_base=filename_base,
                workflow=workflow,
                base_seed=base_seed,
                res_width=res_width,
                res_height=res_height,
                output_dir=output_dir,
                checkpoint=checkpoint,
                total_shots=total_shots,
                project=project,
                images_done=images_done,
                total_images_est=total_images_est,
                progress_callback=progress_callback,
                current_shot_display=current_shot_display
            )

            for variant_images, status, progress_md, updated_checkpoint, current_display in variant_generator:
                shot_images.extend(variant_images)
                images_done += len(variant_images)
                checkpoint = updated_checkpoint
                yield variant_images, status, progress_md, checkpoint, current_display

        # Mark shot as completed
        checkpoint["completed_shots"].append(shot_id)
        self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)

        progress_details = self._format_progress(checkpoint, total_shots)
        # Yield empty list to avoid duplicates (images already yielded during generation)
        yield [], f"**Status:** ✅ Shot {shot_id} abgeschlossen ({len(shot_images)} Bilder)", \
              progress_details, checkpoint, current_shot_display

        logger.info(f"Completed shot {shot_id}: {len(shot_images)} images generated")

    def _generate_variant(
        self,
        shot: Dict[str, Any],
        shot_id: str,
        shot_idx: int,
        variant_idx: int,
        variants_per_shot: int,
        filename_base: str,
        workflow: Dict[str, Any],
        base_seed: int,
        res_width: int,
        res_height: int,
        output_dir: str,
        checkpoint: Dict[str, Any],
        total_shots: int,
        project: Dict[str, Any],
        images_done: int,
        total_images_est: int,
        progress_callback=None,
        current_shot_display: str = ""
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """Generate a single variant for a shot."""
        variant_seed = base_seed + (shot_idx * variants_per_shot) + variant_idx
        variant_name = f"{filename_base}_v{variant_idx+1}"

        logger.info(f"Generating variant {variant_idx + 1}/{variants_per_shot} "
                   f"for shot {shot_id} (seed {variant_seed})")

        # Update workflow with shot parameters
        updated_workflow = self.api.update_workflow_params(
            workflow,
            prompt=shot.get("prompt", ""),
            seed=variant_seed,
            filename_prefix=variant_name,
            width=res_width,
            height=res_height
        )

        try:
            # Queue and monitor
            prompt_id = self.api.queue_prompt(updated_workflow)
            result = self.api.monitor_progress(prompt_id, timeout=300)

            if result["status"] == "success":
                # Copy generated images
                copied_images = self._copy_generated_images(
                    variant_name=variant_name,
                    output_dir=output_dir,
                    api_result=result
                )

                if copied_images:
                    checkpoint["total_images_generated"] += len(copied_images)

                    if progress_callback and callable(progress_callback):
                        progress_callback(
                            min(0.99, (images_done + len(copied_images)) / total_images_est),
                            desc=f"{shot_id}: Variant {variant_idx + 1}/{variants_per_shot}"
                        )

                    # Save checkpoint after each variant
                    self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)

                    variant_progress = self._format_progress(checkpoint, total_shots)
                    yield copied_images, f"**Status:** 🖼️ {shot_id} Variant {variant_idx + 1} fertig", \
                          variant_progress, checkpoint, current_shot_display

                    logger.info(f"Variant {variant_idx + 1} completed: {len(copied_images)} images")
                else:
                    logger.warning(f"Generated but failed to copy variant {variant_idx + 1}")
                    yield [], f"**Status:** ⚠️ {shot_id} Variant {variant_idx + 1} copy failed", \
                          self._format_progress(checkpoint, total_shots), checkpoint, current_shot_display
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Failed variant {variant_idx + 1}: {error_msg}")
                yield [], f"**Status:** ✗ {shot_id} Variant {variant_idx + 1} failed", \
                      self._format_progress(checkpoint, total_shots), checkpoint, current_shot_display

        except Exception as e:
            logger.error(f"Error generating variant {variant_idx + 1}: {e}", exc_info=True)
            yield [], f"**Status:** ✗ {shot_id} Variant {variant_idx + 1} error: {e}", \
                  self._format_progress(checkpoint, total_shots), checkpoint, current_shot_display

    def _copy_generated_images(
        self,
        variant_name: str,
        output_dir: str,
        api_result: Dict[str, Any],
        max_retries: int = 30,
        retry_delay: float = 1.0
    ) -> List[str]:
        """Move generated images from ComfyUI output to project directory.

        Includes retry mechanism to handle race condition where ComfyUI reports
        success via WebSocket before the file is fully written to disk.
        """
        import time
        moved_images = []

        # Move from ComfyUI output directory
        try:
            comfy_output = self.project_store.comfy_output_dir()

            # Try multiple patterns to find the images
            patterns = [
                os.path.join(comfy_output, f"{variant_name}_*.png"),  # Direct in output/
                os.path.join(comfy_output, f"{variant_name}*.png"),   # Fallback pattern
            ]

            logger.debug(f"Searching for images matching '{variant_name}' in {comfy_output}")

            # Retry loop to wait for file to appear on disk
            for attempt in range(max_retries):
                seen_sources = set()
                seen_destinations = set()

                for pattern in patterns:
                    matches = glob.glob(pattern)

                    for src in matches:
                        if src in seen_sources:
                            continue
                        seen_sources.add(src)

                        dest = os.path.join(output_dir, os.path.basename(src))

                        if dest in seen_destinations:
                            logger.warning(f"Skipping duplicate destination: {dest}")
                            continue
                        seen_destinations.add(dest)

                        # MOVE instead of copy to avoid duplicates
                        shutil.move(src, dest)
                        moved_images.append(dest)
                        logger.info(f"Moved image: {os.path.basename(src)} → {output_dir}")

                if moved_images:
                    break  # Found and moved files, exit retry loop

                if attempt < max_retries - 1:
                    logger.debug(f"No files found yet, retry {attempt + 1}/{max_retries} in {retry_delay}s")
                    time.sleep(retry_delay)

            if not moved_images:
                logger.warning(f"No images found for pattern '{variant_name}' after {max_retries} retries")
                logger.warning(f"Tried patterns: {patterns}")
                # List what's actually in the directory for debugging
                try:
                    all_files = [f for f in os.listdir(comfy_output) if f.endswith('.png')]
                    logger.debug(f"PNG files in {comfy_output}: {all_files[:10]}")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to move images for {variant_name}: {e}", exc_info=True)

        return moved_images

    def _cleanup_old_files(self, filename_base: str) -> int:
        """Move leftover files from ComfyUI output directory to temp folder.

        This prevents picking up old files from failed/previous runs.
        Files are moved to output/temp/{timestamp}/ instead of deleted.

        Args:
            filename_base: Base filename for the shot (e.g., 'opening-scene')

        Returns:
            Number of files moved
        """
        try:
            comfy_output = self.project_store.comfy_output_dir()
            pattern = os.path.join(comfy_output, f"{filename_base}_v*_*.png")
            old_files = glob.glob(pattern)

            if old_files:
                # Create temp directory with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_dir = os.path.join(comfy_output, "temp", timestamp)
                os.makedirs(temp_dir, exist_ok=True)

                logger.info(f"Moving {len(old_files)} old file(s) for '{filename_base}' to {temp_dir}")
                for old_file in old_files:
                    try:
                        dest = os.path.join(temp_dir, os.path.basename(old_file))
                        shutil.move(old_file, dest)
                        logger.debug(f"Moved old file: {old_file} → {temp_dir}")
                    except OSError as e:
                        logger.warning(f"Failed to move {old_file}: {e}")

            return len(old_files)

        except Exception as e:
            logger.error(f"Cleanup failed for {filename_base}: {e}")
            return 0

    def _handle_stop(
        self,
        checkpoint: Dict[str, Any],
        all_generated_images: List[str],
        total_shots: int,
        project: Dict[str, Any]
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """Handle stop request during generation."""
        checkpoint["status"] = "stopped"
        self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)

        status = "**⏹️ Gestoppt:** Generation wurde vom Benutzer abgebrochen."
        progress_details = self._format_progress(checkpoint, total_shots)
        self.is_running = False

        yield all_generated_images, status, progress_details, checkpoint, \
              f"Stopped at {checkpoint.get('current_shot', 'unknown')}"

    def stop_generation(self) -> Tuple[str, str]:
        """Request to stop the current generation loop."""
        if self.is_running:
            self.stop_requested = True
            return "**⏹️ Stop angefordert:** Warte auf laufenden Shot.", "Stop wird ausgeführt..."
        self.stop_requested = False
        return "**ℹ️ Kein Lauf aktiv.**", "Kein aktiver Fortschritt."

    def _format_progress(self, checkpoint: Dict, total_shots: int) -> str:
        """Format progress details as markdown."""
        completed = len(checkpoint.get("completed_shots", []))
        total_images = checkpoint.get("total_images_generated", 0)
        current_shot = checkpoint.get("current_shot", "None")
        status = checkpoint.get("status", "unknown")

        progress_md = f"""### Progress

- **Status:** {status}
- **Completed Shots:** {completed}/{total_shots}
- **Total Images Generated:** {total_images}
- **Current Shot:** {current_shot}
- **Started:** {checkpoint.get('started_at', 'N/A')}
"""

        if status == "completed":
            progress_md += f"- **Completed:** {checkpoint.get('completed_at', 'N/A')}\n"

        return progress_md

    def _save_checkpoint(
        self,
        checkpoint: Dict[str, Any],
        storyboard_file: str,
        project: Dict[str, Any]
    ):
        """Save checkpoint to file."""
        try:
            checkpoint_dir = self.project_store.ensure_dir(project, "checkpoints")
            # Use only the filename, not the full path
            storyboard_filename = os.path.basename(storyboard_file)
            checkpoint_file = os.path.join(checkpoint_dir, f"checkpoint_{storyboard_filename}")

            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint, f, indent=2)

            logger.debug(f"Checkpoint saved: {checkpoint_file}")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}", exc_info=True)


__all__ = ["KeyframeService", "KeyframeGenerationService"]
