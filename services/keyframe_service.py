"""Service layer for keyframe generation (Phase 1)."""
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple, Generator, Optional

from infrastructure.project_store import ProjectStore
from infrastructure.workflow_registry import WorkflowRegistry
from infrastructure.config_manager import ConfigManager
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.logger import get_logger
from domain.models import Storyboard
from services.character_lora_service import CharacterLoraService

# Import from keyframe package
from services.keyframe import (
    KeyframeFileHandler,
    CheckpointHandler,
    LoraParamsResolver,
    create_checkpoint,
    format_progress,
    inject_model_override,
    get_workflow_for_shot,
)

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
        return create_checkpoint(
            storyboard_file=storyboard.raw.get("storyboard_file"),
            workflow_file=workflow_file,
            variants_per_shot=variants_per_shot,
            base_seed=base_seed
        )


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
        """Initialize the keyframe generation service."""
        self.config = config
        self.project_store = project_store
        self.api = comfy_api
        self.is_running = False
        self.stop_requested = False

        # Initialize handlers
        self.character_lora_service = CharacterLoraService(config)
        self._file_handler = KeyframeFileHandler(project_store)
        self._checkpoint_handler = CheckpointHandler(project_store)
        self._lora_resolver = LoraParamsResolver(self.character_lora_service)

    def _format_progress(self, checkpoint: Dict[str, Any], total_shots: int) -> str:
        """Backward-compatible wrapper for progress formatting."""
        return format_progress(checkpoint, total_shots)

    def _save_checkpoint(self, checkpoint: Dict[str, Any], storyboard_file: str, project: Dict[str, Any]) -> None:
        """Backward-compatible wrapper for checkpoint persistence."""
        try:
            self._checkpoint_handler.save(checkpoint, storyboard_file, project)
        except Exception as exc:
            logger.warning(f"Failed to save checkpoint: {exc}")

    def _copy_generated_images(
        self,
        variant_name: str,
        output_dir: str,
        api_result: Dict[str, Any],
    ) -> List[str]:
        """Backward-compatible wrapper for image copying."""
        try:
            return self._file_handler.copy_generated_images(
                variant_name=variant_name,
                output_dir=output_dir,
                api_result=api_result,
            )
        except Exception as exc:
            logger.warning(f"Copy failed for {variant_name}: {exc}")
            return []

    def run_generation(
        self,
        storyboard: Storyboard,
        workflow_file: str,
        checkpoint: Dict[str, Any],
        project: Dict[str, Any],
        comfy_url: str,
        progress_callback=None,
        model_override: Optional[str] = None
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """Run the complete keyframe generation process."""
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

            # Inject model override if specified
            if model_override:
                workflow = inject_model_override(workflow, model_override)
                logger.info(f"Model override applied: {model_override}")

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
                if self.stop_requested:
                    yield from self._handle_stop(checkpoint, all_generated_images, total_shots, project)
                    return

                shot_id = shot.get("shot_id", f"{shot_idx+1:03d}")

                if shot_id in completed_shots:
                    logger.info(f"Skipping shot {shot_id} (already completed)")
                    continue

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
                    progress_callback=progress_callback,
                    base_workflow_file=workflow_file
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
        progress_callback=None,
        base_workflow_file: str = ""
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """Generate all variants for a single shot."""
        checkpoint["current_shot"] = shot_id
        current_shot_display = f"**Current Shot:** {shot_id} - {shot.get('description', 'No description')}"
        progress_details = self._format_progress(checkpoint, total_shots)

        if progress_callback and callable(progress_callback):
            progress_callback(min(0.95, images_done / total_images_est), desc=f"{shot_id}: Start")

        # Determine if this shot needs a different workflow (LoRA vs non-LoRA)
        shot_workflow = workflow
        if base_workflow_file:
            needed_workflow_file = get_workflow_for_shot(
                shot, base_workflow_file, self.config.get_workflow_dir()
            )
            if needed_workflow_file != base_workflow_file:
                workflow_path = os.path.join(self.config.get_workflow_dir(), needed_workflow_file)
                if os.path.exists(workflow_path):
                    shot_workflow = self.api.load_workflow(workflow_path)
                    logger.info(f"Loaded LoRA workflow for shot {shot_id}: {needed_workflow_file}")

        yield [], f"**Status:** ▶️ Shot {shot_id} gestartet", progress_details, \
              checkpoint, current_shot_display

        logger.info(f"Starting shot {shot_id} ({shot_idx + 1}/{total_shots})")

        shot_images = []
        filename_base = shot.get("filename_base", f"shot_{shot_id}")
        res_width, res_height = self.config.get_resolution_tuple()

        # Clean up old files
        self._file_handler.cleanup_old_files(filename_base)

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
                workflow=shot_workflow,
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

        progress_details = format_progress(checkpoint, total_shots)
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

        # Get LoRA params if character is assigned
        lora_params = self._lora_resolver.get_lora_params_for_shot(shot)

        # Update workflow with shot parameters
        updated_workflow = self.api.update_workflow_params(
            workflow,
            prompt=shot.get("prompt", ""),
            seed=variant_seed,
            filename_prefix=variant_name,
            width=res_width,
            height=res_height,
            **lora_params
        )

        try:
            # Queue and monitor
            prompt_id = self.api.queue_prompt(updated_workflow)
            result = self.api.monitor_progress(prompt_id, timeout=300)

            if result["status"] == "success":
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

    # Legacy method for backwards compatibility
    def get_workflow_for_shot(self, shot: Dict[str, Any], base_workflow_file: str) -> str:
        """Determine which workflow to use for a shot."""
        return get_workflow_for_shot(shot, base_workflow_file, self.config.get_workflow_dir())


__all__ = ["KeyframeService", "KeyframeGenerationService"]
