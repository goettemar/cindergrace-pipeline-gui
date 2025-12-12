"""Keyframe Generator Addon - Phase 1 of CINDERGRACE Pipeline"""
import os
import sys
import json
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any, Generator
import gradio as gr

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.config_manager import ConfigManager
from infrastructure.workflow_registry import WorkflowRegistry
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from domain import models as domain_models
from domain.storyboard_service import StoryboardService
from domain.validators import KeyframeGeneratorInput, WorkflowFileInput

logger = get_logger(__name__)


class KeyframeGeneratorAddon(BaseAddon):
    """Generate keyframe variants for storyboard shots"""

    def __init__(self):
        super().__init__(
            name="Keyframe Generator",
            description="Generate multiple keyframe variants for each storyboard shot"
        )
        self.config = ConfigManager()
        self.api = None
        self.current_storyboard: Optional[domain_models.Storyboard] = None
        self.checkpoint_file = None
        self.is_running = False
        self.stop_requested = False
        self.workflow_registry = WorkflowRegistry()
        self.project_manager = ProjectStore(self.config)

    def get_tab_name(self) -> str:
        return "🎬 Keyframe Generator"

    def render(self) -> gr.Blocks:
        """Render the keyframe generator UI"""

        with gr.Blocks() as interface:
            gr.Markdown("# 🎬 Keyframe Generator - Phase 1")
            gr.Markdown("Generate multiple keyframe variants for each shot in your storyboard")

            # Configuration Section
            with gr.Group():
                gr.Markdown("## ⚙️ Configuration")
                project_status = gr.Markdown(self._project_status_md())
                refresh_project_btn = gr.Button("🔄 Projektstatus aktualisieren", size="sm")

                with gr.Row():
                    comfy_url = gr.Textbox(
                        value=self.config.get_comfy_url(),
                        label="ComfyUI URL",
                        placeholder="http://127.0.0.1:8188"
                    )

                storyboard_info_md = gr.Markdown(self._current_storyboard_md())
                gr.Markdown("Storyboard wird im Tab 📁 Projektverwaltung gewählt.")

                with gr.Row(equal_height=True):
                    workflow_dropdown = gr.Dropdown(
                        choices=self._get_available_workflows(),
                        value=self._get_default_workflow(),
                        label="Workflow Template",
                        info="Flux workflow to use for generation",
                        scale=9
                    )
                    refresh_workflow_btn = gr.Button("🔄", size="sm", scale=1, min_width=60)

                with gr.Row():
                    variants_per_shot = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value=4,
                        step=1,
                        label="Variants per Shot",
                        info="Number of keyframe variants to generate for each shot"
                    )
                    base_seed = gr.Number(
                        value=2000,
                        label="Base Seed",
                        precision=0,
                        info="Starting seed (will increment for each variant)"
                    )

                load_storyboard_btn = gr.Button("📖 Load Storyboard", variant="secondary")

            # Storyboard Info Section
            with gr.Accordion("📋 Storyboard Info (Click to expand)", open=False):
                storyboard_info = gr.Code(
                    label="Loaded Storyboard Details",
                    language="json",
                    value="{}",
                    lines=20,
                    max_lines=20,
                    interactive=False
                )

            gr.Markdown("---")

            # Generation Control Section
            with gr.Group():
                gr.Markdown("## 🚀 Generation Control")

                with gr.Row():
                    start_btn = gr.Button("▶️ Start Generation", variant="primary", size="lg")
                    stop_btn = gr.Button("⏹️ Stop", variant="stop", size="lg")
                    resume_btn = gr.Button("⏯️ Resume from Checkpoint", variant="secondary", size="lg")

                status_text = gr.Markdown("**Status:** Ready - Load a storyboard to begin")

                with gr.Accordion("Progress Details", open=True):
                    progress_details = gr.Markdown("No generation in progress")

            gr.Markdown("---")

            # Results Section
            with gr.Group():
                gr.Markdown("## 🖼️ Generated Keyframes")

                with gr.Row():
                    current_shot_display = gr.Markdown("**Current Shot:** None")

                keyframe_gallery = gr.Gallery(
                    label="Keyframes (All Variants)",
                    show_label=True,
                    columns=4,
                    rows=2,
                    height="auto",
                    object_fit="contain"
                )

                with gr.Row():
                    clear_gallery_btn = gr.Button("🗑️ Clear Gallery")
                    open_output_btn = gr.Button("📁 Open Output Folder")

            # Checkpoint Section
            with gr.Accordion("💾 Checkpoint Info", open=False):
                checkpoint_info = gr.JSON(label="Checkpoint Status", value={})

            # Event Handlers
            load_storyboard_btn.click(
                fn=self.load_storyboard_from_config,
                outputs=[storyboard_info, status_text]
            )

            start_btn.click(
                fn=self.start_generation,
                inputs=[
                    comfy_url,
                    workflow_dropdown,
                    variants_per_shot,
                    base_seed
                ],
                outputs=[keyframe_gallery, status_text, progress_details, checkpoint_info, current_shot_display]
            )

            resume_btn.click(
                fn=self.resume_generation,
                inputs=[
                    comfy_url,
                    workflow_dropdown
                ],
                outputs=[keyframe_gallery, status_text, progress_details, checkpoint_info, current_shot_display]
            )

            stop_btn.click(
                fn=self.stop_generation,
                outputs=[status_text, progress_details]
            )

            refresh_workflow_btn.click(
                fn=lambda: gr.update(choices=self._get_available_workflows()),
                outputs=[workflow_dropdown]
            )

            clear_gallery_btn.click(
                fn=lambda: ([], "**Status:** Gallery cleared"),
                outputs=[keyframe_gallery, status_text]
            )

            open_output_btn.click(
                fn=self.open_output_folder,
                outputs=[status_text]
            )

            refresh_project_btn.click(
                fn=lambda: self._project_status_md(),
                outputs=[project_status]
            )

        return interface

    def load_storyboard(self, storyboard_file: str) -> Tuple[str, str]:
        """Load and validate storyboard file.

        Refactored to use centralized StoryboardService.
        """
        try:
            if not storyboard_file or storyboard_file.startswith("No storyboards"):
                return "{}", "**❌ Error:** No storyboard selected"

            # Use centralized service for loading
            storyboard = StoryboardService.load_from_config(
                self.config,
                filename=storyboard_file
            )

            # Apply global resolution override from project settings
            StoryboardService.apply_resolution_from_config(storyboard, self.config)

            # Store metadata and reference
            storyboard.raw["storyboard_file"] = storyboard_file
            self.current_storyboard = storyboard

            # Format storyboard as pretty JSON string for display
            storyboard_json = json.dumps(storyboard.raw, indent=2)

            # Create status message
            total_shots = len(storyboard.shots)
            project_name = storyboard.project or "Unknown"
            status = f"**✅ Loaded:** {project_name} - {total_shots} shots"

            return storyboard_json, status

        except Exception as e:
            logger.error(f"Failed to load storyboard: {e}", exc_info=True)
            return "{}", f"**❌ Error:** Failed to load storyboard: {str(e)}"

    def load_storyboard_from_config(self) -> Tuple[str, str]:
        """Load storyboard using selection from project tab.

        Refactored to use centralized StoryboardService.
        """
        try:
            # Load using centralized service (handles config refresh internally)
            storyboard = StoryboardService.load_from_config(self.config)

            # Apply global resolution override
            StoryboardService.apply_resolution_from_config(storyboard, self.config)

            # Store reference
            storyboard_file = self.config.get_current_storyboard()
            storyboard.raw["storyboard_file"] = storyboard_file
            self.current_storyboard = storyboard

            # Format for display
            storyboard_json = json.dumps(storyboard.raw, indent=2)
            total_shots = len(storyboard.shots)
            project_name = storyboard.project or "Unknown"
            status = f"**✅ Loaded:** {project_name} - {total_shots} shots"

            return storyboard_json, status

        except Exception as e:
            logger.error(f"Failed to load storyboard from config: {e}", exc_info=True)
            return "{}", f"**❌ Error:** {str(e)}"

    def start_generation(
        self,
        comfy_url: str,
        workflow_file: str,
        variants_per_shot: int,
        base_seed: int,
        progress=gr.Progress(track_tqdm=True)
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """Start keyframe generation from beginning (streaming updates)."""
        try:
            self.config.refresh()
            storyboard_file = self.config.get_current_storyboard()
            if not storyboard_file:
                yield [], "**❌ Error:** Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen.", "No storyboard", {}, "No shot"
                return

            # Validate inputs with Pydantic
            validated_inputs = KeyframeGeneratorInput(
                variants_per_shot=int(variants_per_shot),
                base_seed=int(base_seed)
            )
            WorkflowFileInput(workflow_file=workflow_file)

            logger.info(f"Starting keyframe generation: {validated_inputs.variants_per_shot} variants, seed {validated_inputs.base_seed}")

            self.stop_requested = False
            project = self.project_manager.get_active_project(refresh=True)
            if not project:
                yield [], "**❌ Error:** Kein aktives Projekt. Bitte zuerst im Tab '📁 Projekt' auswählen.", "No project", {}, "No shot"
                return

            # Load storyboard if not already loaded
            if self.current_storyboard is None:
                sb_json, load_status = self.load_storyboard(storyboard_file)
                if "Error" in load_status:
                    yield [], load_status, "No progress", {}, "No shot"
                    return

            # Initialize checkpoint
            checkpoint = {
                "storyboard_file": storyboard_file,
                "workflow_file": workflow_file,
                "variants_per_shot": validated_inputs.variants_per_shot,
                "base_seed": validated_inputs.base_seed,
                "started_at": datetime.now().isoformat(),
                "completed_shots": [],
                "current_shot": None,
                "total_images_generated": 0,
                "status": "running"
            }

            # Save checkpoint
            self._save_checkpoint(checkpoint, storyboard_file, project)

            # Stream generation
            yield from self._run_generation(comfy_url, workflow_file, checkpoint, project, progress)

        except Exception as e:
            error_msg = f"**❌ Error:** {str(e)}"
            logger.error(f"Keyframe generation failed: {e}", exc_info=True)
            yield [], error_msg, "Generation failed", {}, "Error"

    def resume_generation(
        self,
        comfy_url: str,
        workflow_file: str,
        progress=gr.Progress(track_tqdm=True)
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """Resume generation from checkpoint (streaming updates)."""
        try:
            self.config.refresh()
            storyboard_file = self.config.get_current_storyboard()
            if not storyboard_file:
                yield [], "**❌ Error:** Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen.", "No storyboard", {}, "No shot"
                return
            self.stop_requested = False
            project = self.project_manager.get_active_project(refresh=True)
            if not project:
                yield [], "**❌ Error:** Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen.", "No project", {}, "No shot"
                return

            # Load checkpoint
            checkpoint = self._load_checkpoint(storyboard_file, project)

            if not checkpoint:
                yield [], "**❌ Error:** No checkpoint found. Start a new generation first.", "No checkpoint", {}, "None"
                return

            if checkpoint.get("status") == "completed":
                yield [], "**✅ Info:** Generation already completed. Start a new generation or load existing keyframes.", "Already complete", checkpoint, "Complete"
                return

            # Load storyboard
            _, load_status = self.load_storyboard(storyboard_file)
            if "Error" in load_status:
                yield [], load_status, "No progress", {}, "No shot"
                return

            # Resume generation
            checkpoint["status"] = "running"
            checkpoint["resumed_at"] = datetime.now().isoformat()

            yield from self._run_generation(comfy_url, workflow_file, checkpoint, project, progress)

        except Exception as e:
            error_msg = f"**❌ Error:** {str(e)}"
            yield [], error_msg, "Resume failed", {}, "Error"

    def _run_generation(
        self,
        comfy_url: str,
        workflow_file: str,
        checkpoint: Dict,
        project: Dict[str, Any],
        progress=None
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        """Run the actual generation process and stream updates."""
        try:
            # Initialize API
            self.api = ComfyUIAPI(comfy_url)
            self.is_running = True

            # Test connection
            conn_result = self.api.test_connection()
            if not conn_result["connected"]:
                self.is_running = False
                yield [], f"**❌ Error:** Connection failed - {conn_result['error']}", "Connection failed", checkpoint, "Error"
                return

            # Load workflow
            workflow_path = os.path.join(
                self.config.get_workflow_dir(),
                workflow_file
            )

            if not os.path.exists(workflow_path):
                yield [], f"**❌ Error:** Workflow not found: `{workflow_path}`", "Workflow missing", checkpoint, "Error"
                return

            workflow = self.api.load_workflow(workflow_path)

            # Get generation settings
            variants_per_shot = checkpoint["variants_per_shot"]
            base_seed = checkpoint["base_seed"]
            completed_shots = set(checkpoint.get("completed_shots", []))

            # Prepare output directory
            output_dir = self.project_manager.ensure_dir(project, "keyframes")
            os.makedirs(output_dir, exist_ok=True)

            all_generated_images = []
            shots = self.current_storyboard.raw.get("shots", [])
            total_shots = len(shots)
            total_images_est = max(1, total_shots * variants_per_shot)
            images_done = len(completed_shots) * variants_per_shot
            res_width, res_height = self.config.get_resolution_tuple()

            print(f"\n{'='*60}")
            print(f"KEYFRAME GENERATION STARTED")
            print(f"Total Shots: {total_shots}")
            print(f"Variants per Shot: {variants_per_shot}")
            print(f"Total Images: {total_shots * variants_per_shot}")
            print(f"{'='*60}\n")

            # Initial update
            yield [], "**Status:** 🚀 Starte Keyframe-Generation...", self._format_progress(checkpoint, total_shots), checkpoint, "**Current Shot:** None"

            # Generate keyframes for each shot
            for shot_idx, shot in enumerate(shots):
                if self.stop_requested:
                    checkpoint["status"] = "stopped"
                    checkpoint["current_shot"] = shot.get("shot_id", f"{shot_idx+1:03d}")
                    self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)
                    status = "**⏹️ Gestoppt:** Generation wurde vom Benutzer abgebrochen."
                    progress_details = self._format_progress(checkpoint, total_shots)
                    self.is_running = False
                    yield all_generated_images, status, progress_details, checkpoint, f"Stopped at {checkpoint['current_shot']}"
                    return

                shot_id = shot.get("shot_id", f"{shot_idx+1:03d}")

                # Skip if already completed
                if self.stop_requested:
                    checkpoint["status"] = "stopped"
                    self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)
                    status = "**⏹️ Gestoppt:** Generation wurde vom Benutzer abgebrochen."
                    progress_details = self._format_progress(checkpoint, total_shots)
                    return all_generated_images, status, progress_details, checkpoint, f"Stopped at {shot_id}"

                if shot_id in completed_shots:
                    print(f"⏭️  Skipping shot {shot_id} (already completed)")
                    continue

                checkpoint["current_shot"] = shot_id
                current_shot_display = f"**Current Shot:** {shot_id} - {shot.get('description', 'No description')}"
                checkpoint_progress = self._format_progress(checkpoint, total_shots)
                progress_details = checkpoint_progress
                if progress and callable(progress):
                    progress(
                        min(0.95, images_done / total_images_est),
                        desc=f"{shot_id}: Start"
                    )
                # Stream update for new shot
                yield all_generated_images, f"**Status:** ▶️ Shot {shot_id} gestartet", progress_details, checkpoint, current_shot_display

                print(f"\n{'='*60}")
                print(f"Shot {shot_id} ({shot_idx + 1}/{total_shots})")
                print(f"Description: {shot.get('description', 'N/A')}")
                print(f"{'='*60}")

                shot_images = []

                # Get filename base (content-based naming)
                filename_base = shot.get("filename_base", f"shot_{shot_id}")
                shot_width = res_width
                shot_height = res_height

                # Generate variants for this shot
                for variant_idx in range(variants_per_shot):
                    variant_seed = base_seed + (shot_idx * variants_per_shot) + variant_idx
                    variant_name = f"{filename_base}_v{variant_idx+1}"

                    print(f"\n  Generating variant {variant_idx + 1}/{variants_per_shot} (seed {variant_seed})...")
                    print(f"  Filename: {variant_name}")
                    logger.info(f"[Keyframe] Shot {shot_id} Variant {variant_idx + 1} Seed {variant_seed}")
                    if self.stop_requested:
                        checkpoint["status"] = "stopped"
                        self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)
                        status = "**⏹️ Gestoppt:** Generation wurde vom Benutzer abgebrochen."
                        progress_details = self._format_progress(checkpoint, total_shots)
                        self.is_running = False
                        yield all_generated_images, status, progress_details, checkpoint, f"Stopped at {shot_id}"
                        return

                    # Update workflow with shot parameters (including resolution)
                    updated_workflow = self.api.update_workflow_params(
                        workflow,
                        prompt=shot.get("prompt", ""),
                        seed=variant_seed,
                        filename_prefix=variant_name,
                        width=shot_width,
                        height=shot_height
                    )

                    try:
                        # Queue and monitor
                        prompt_id = self.api.queue_prompt(updated_workflow)
                        result = self.api.monitor_progress(prompt_id, timeout=300)

                        if result["status"] == "success":
                            # Prefer downloading directly from API result if available
                            copied_images = []
                            api_images = result.get("output_images") or []
                            if api_images:
                                copied_images.extend(self._copy_images_list(api_images, output_dir))
                            # Copy images from ComfyUI output to GUI output
                            copied_images.extend(self._copy_images_from_comfyui(variant_name, output_dir))
                            copied_images = self._dedup_paths(copied_images)

                            if copied_images:
                                shot_images.extend(copied_images)
                                all_generated_images.extend(copied_images)
                                checkpoint["total_images_generated"] += len(copied_images)
                                print(f"  ✓ Generated and copied variant {variant_idx + 1} ({len(copied_images)} images)")
                                images_done += len(copied_images)
                                if progress and callable(progress):
                                    progress(
                                        min(0.99, images_done / total_images_est),
                                        desc=f"{shot_id}: Variant {variant_idx + 1}/{variants_per_shot}"
                                    )
                                # Stream variant-level update
                                variant_progress = self._format_progress(checkpoint, total_shots)
                                yield all_generated_images, f"**Status:** 🖼️ {shot_id} Variant {variant_idx + 1} fertig", variant_progress, checkpoint, current_shot_display
                            else:
                                print(f"  ⚠️  Generated but failed to copy variant {variant_idx + 1}")
                        else:
                            error_msg = result.get("error", "Unknown error")
                            print(f"  ✗ Failed variant {variant_idx + 1}: {error_msg}")

                    except Exception as e:
                        print(f"  ✗ Error generating variant {variant_idx + 1}: {e}")
                        continue

                # Mark shot as completed
                checkpoint["completed_shots"].append(shot_id)
                self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)

                progress_details = self._format_progress(checkpoint, total_shots)
                yield all_generated_images, f"**Status:** ✅ Shot {shot_id} abgeschlossen", progress_details, checkpoint, current_shot_display

                print(f"\n✓ Completed shot {shot_id}: {len(shot_images)} images generated")

            # Mark as completed
            checkpoint["status"] = "completed"
            checkpoint["completed_at"] = datetime.now().isoformat()
            self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)

            status = f"**✅ Generation Complete!** Generated {checkpoint['total_images_generated']} keyframes for {len(checkpoint['completed_shots'])} shots"
            progress_details = self._format_progress(checkpoint, total_shots)

            print(f"\n{'='*60}")
            print(f"GENERATION COMPLETE")
            print(f"Total Images: {checkpoint['total_images_generated']}")
            print(f"Output: {output_dir}")
            print(f"{'='*60}\n")

            self.is_running = False
            self.stop_requested = False
            yield all_generated_images, status, progress_details, checkpoint, "Complete"
            return

        except Exception as e:
            checkpoint["status"] = "error"
            checkpoint["error"] = str(e)
            self._save_checkpoint(checkpoint, checkpoint["storyboard_file"], project)
            self.is_running = False
            self.stop_requested = False

            error_msg = f"**❌ Error:** {str(e)}"
            yield [], error_msg, "Generation failed", checkpoint, "Error"

    def stop_generation(self):
        """Request to stop the current generation loop."""
        if self.is_running:
            self.stop_requested = True
            return "**⏹️ Stop angefordert:** Warte auf laufenden Shot.", "Stop wird ausgeführt..."
        self.stop_requested = False
        return "**ℹ️ Kein Lauf aktiv.**", "Kein aktiver Fortschritt."

    def _format_progress(self, checkpoint: Dict, total_shots: int) -> str:
        """Format progress details as markdown"""
        completed = len(checkpoint.get("completed_shots", []))
        total_images = checkpoint.get("total_images_generated", 0)
        current_shot = checkpoint.get("current_shot", "None")
        status = checkpoint.get("status", "unknown")

        progress_md = f"""
### Progress

- **Status:** {status}
- **Completed Shots:** {completed}/{total_shots}
- **Total Images Generated:** {total_images}
- **Current Shot:** {current_shot}
- **Started:** {checkpoint.get('started_at', 'N/A')}
"""

        if status == "completed":
            progress_md += f"- **Completed:** {checkpoint.get('completed_at', 'N/A')}\n"

        return progress_md

    def _save_checkpoint(self, checkpoint: Dict, storyboard_file: str, project: Dict[str, Any]):
        """Save checkpoint to file"""
        try:
            checkpoint_dir = self.project_manager.ensure_dir(project, "checkpoints")

            # Create checkpoint filename based on storyboard
            base_name = os.path.splitext(os.path.basename(storyboard_file))[0]
            checkpoint_name = f"{base_name}_checkpoint.json"
            checkpoint_path = os.path.join(checkpoint_dir, checkpoint_name)

            with open(checkpoint_path, 'w') as f:
                json.dump(checkpoint, f, indent=2)

            self.checkpoint_file = checkpoint_path
            print(f"💾 Checkpoint saved: {checkpoint_path}")

        except Exception as e:
            print(f"✗ Failed to save checkpoint: {e}")

    def _load_checkpoint(self, storyboard_file: str, project: Dict[str, Any]) -> Optional[Dict]:
        """Load checkpoint from file"""
        try:
            checkpoint_dir = self.project_manager.ensure_dir(project, "checkpoints")

            base_name = os.path.splitext(os.path.basename(storyboard_file))[0]
            checkpoint_name = f"{base_name}_checkpoint.json"
            checkpoint_path = os.path.join(checkpoint_dir, checkpoint_name)

            if not os.path.exists(checkpoint_path):
                return None

            with open(checkpoint_path, 'r') as f:
                checkpoint = json.load(f)

            print(f"📂 Checkpoint loaded: {checkpoint_path}")
            return checkpoint

        except Exception as e:
            print(f"✗ Failed to load checkpoint: {e}")
            return None

    def _copy_images_from_comfyui(self, filename_prefix: str, gui_output_dir: str) -> List[str]:
        """
        Copy generated images from ComfyUI output to the active project keyframe directory

        Args:
            filename_prefix: Prefix used when generating (e.g., "hand-book_v1")
            gui_output_dir: Destination directory path

        Returns:
            List of copied image paths
        """
        import glob
        import shutil

        copied_images = []

        try:
            comfyui_output = self.project_manager.comfy_output_dir()
        except FileNotFoundError as exc:
            print(f"    ✗ Copy error: {exc}")
            return []

        try:
            # ComfyUI default output directory
            # Find images matching the prefix
            pattern = os.path.join(comfyui_output, f"{filename_prefix}*.png")
            matching_files = glob.glob(pattern)

            print(f"    Looking for: {pattern}")
            print(f"    Found {len(matching_files)} file(s)")

            for source_path in matching_files:
                filename = os.path.basename(source_path)
                dest_path = os.path.join(gui_output_dir, filename)

                # Copy file
                shutil.copy2(source_path, dest_path)
                copied_images.append(dest_path)
                print(f"    ✓ Copied: {filename}")

            return copied_images

        except Exception as e:
            print(f"    ✗ Copy error: {e}")
            return []

    def _copy_images_list(self, source_paths: List[str], dest_dir: str) -> List[str]:
        """Copy already-downloaded images into project keyframe directory."""
        import shutil

        copied = []
        for source_path in source_paths:
            try:
                if not os.path.exists(source_path):
                    continue
                filename = os.path.basename(source_path)
                dest_path = os.path.join(dest_dir, filename)
                if os.path.exists(dest_path):
                    copied.append(dest_path)
                    continue
                shutil.copy2(source_path, dest_path)
                copied.append(dest_path)
            except Exception as exc:
                print(f"    ✗ Copy error (api download): {exc}")
        return copied

    @staticmethod
    def _dedup_paths(paths: List[str]) -> List[str]:
        """Remove duplicate paths while preserving order."""
        seen = set()
        unique: List[str] = []
        for p in paths:
            if p in seen:
                continue
            seen.add(p)
            unique.append(p)
        return unique

    def open_output_folder(self) -> str:
        """Open output folder in file manager"""
        try:
            project = self.project_manager.get_active_project(refresh=True)
            if not project:
                return "**❌ Error:** Kein aktives Projekt. Bitte im Tab 'Projekt' auswählen."
            output_dir = self.project_manager.ensure_dir(project, "keyframes")
            os.makedirs(output_dir, exist_ok=True)

            # Open folder (Linux)
            os.system(f'xdg-open "{output_dir}"')

            return f"**📁 Opened:** `{output_dir}`"

        except Exception as e:
            return f"**❌ Error:** {str(e)}"

    def _project_status_md(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Kein aktives Projekt:** Bitte im Tab `📁 Projekt` anlegen oder auswählen."
        return (
            f"**Aktives Projekt:** {project.get('name')} (`{project.get('slug')}`)\n"
            f"- Pfad: `{project.get('path')}`"
        )

    def _current_storyboard_md(self) -> str:
        self.config.refresh()
        storyboard = self.config.get_current_storyboard()
        if not storyboard:
            return "**❌ Kein Storyboard gesetzt:** Bitte im Tab `📁 Projekt` auswählen."
        return f"**Storyboard:** `{storyboard}` (aus Tab 📁 Projektverwaltung)"

    # Removed: _apply_global_resolution() - now using StoryboardService.apply_resolution_from_config()

    def _get_available_storyboards(self) -> List[str]:
        """Get list of available storyboard files"""
        directories = self._storyboard_search_dirs()
        storyboards: List[str] = []
        seen = set()

        for directory in directories:
            for filename in sorted(os.listdir(directory)):
                if not filename.endswith('.json'):
                    continue
                if 'storyboard' not in filename.lower():
                    continue
                full_path = os.path.join(directory, filename)
                if full_path in seen:
                    continue
                storyboards.append(full_path)
                seen.add(full_path)

        return storyboards if storyboards else ["No storyboards found - add JSON files to config/ or project folder"]

    def _get_default_storyboard(self) -> Optional[str]:
        """Get default storyboard (first available)"""
        storyboards = self._get_available_storyboards()
        return storyboards[0] if storyboards else None

    def _get_available_workflows(self) -> List[str]:
        """Get list of available workflow files"""
        workflows = self.workflow_registry.get_files(category="flux")
        return workflows if workflows else ["No workflows found - update workflow_presets.json"]

    def _get_default_workflow(self) -> Optional[str]:
        """Get default workflow"""
        return self.workflow_registry.get_default(category="flux")

    def _storyboard_search_dirs(self) -> List[str]:
        """Return directories that may contain storyboard files."""
        dirs: List[str] = []
        config_dir = self.config.config_dir
        if config_dir and os.path.isdir(config_dir):
            dirs.append(config_dir)

        project = self.project_manager.get_active_project(refresh=True)
        if project:
            project_root = project.get("path")
            for candidate in (project_root, os.path.join(project_root, "storyboards")):
                if candidate and os.path.isdir(candidate):
                    dirs.append(candidate)

        # remove duplicates while preserving order
        unique_dirs: List[str] = []
        for directory in dirs:
            if directory not in unique_dirs:
                unique_dirs.append(directory)
        return unique_dirs
