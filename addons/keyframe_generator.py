import os
import sys
import json
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any, Generator
import gradio as gr
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.config_manager import ConfigManager
from infrastructure.workflow_registry import WorkflowRegistry
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from infrastructure.error_handler import handle_errors
from infrastructure.error_handler import handle_errors
from domain import models as domain_models
from domain.storyboard_service import StoryboardService
from domain.validators import KeyframeGeneratorInput, WorkflowFileInput
from services.keyframe_service import KeyframeGenerationService, KeyframeService

logger = get_logger(__name__)
class KeyframeGeneratorAddon(BaseAddon):
    def __init__(self):
        super().__init__(
            name="Keyframe Generator",
            description="Generate multiple keyframe variants for each storyboard shot"
        )
        self.config = ConfigManager()
        self.current_storyboard: Optional[domain_models.Storyboard] = None
        self.workflow_registry = WorkflowRegistry()
        self.project_manager = ProjectStore(self.config)
        self.keyframe_service = KeyframeService(
            project_store=self.project_manager,
            config=self.config,
            workflow_registry=self.workflow_registry
        )
        self.generation_service = KeyframeGenerationService(
            config=self.config,
            project_store=self.project_manager
        )

    def get_tab_name(self) -> str:
        return "🎬 Keyframe Generator"

    def render(self) -> gr.Blocks:
        # Auto-load storyboard on tab open
        initial_storyboard_json, initial_status = self.load_storyboard_from_config()

        with gr.Blocks() as interface:
            gr.Markdown("# 🎬 Keyframe Generator - Phase 1")
            gr.HTML("""<script>
  window.addEventListener('beforeunload', function (e) {
    const confirmationMessage = 'Stop/Start ist nicht refresh-sicher. Wirklich neu laden?';
    (e || window.event).returnValue = confirmationMessage;
    return confirmationMessage;
  });
</script>
<style>
  .inline-row { gap: 6px; }
  .icon-button button { min-width: 38px; max-width: 42px; min-height: 38px; padding: 6px; }
  .primary-full button { width: 100%; }
  .secondary-full button { width: 100%; min-height: 40px; }
  .status-line { font-weight: 600; }
</style>""")

            # Storyboard info (consistent with other tabs)
            with gr.Row():
                storyboard_info = gr.Markdown(self._get_storyboard_info())
                refresh_btn = gr.Button("↻ Refresh", scale=0, min_width=60)

            with gr.Row():
                with gr.Column():
                    with gr.Group():
                        gr.Markdown("### ⚙️ Setup")

                        with gr.Row(elem_classes=["inline-row"]):
                            workflow_dropdown = gr.Dropdown(
                                choices=self._get_available_workflows(),
                                value=self._get_default_workflow(),
                                label="Workflow Template",
                                info="Flux workflow to use for generation",
                                scale=8
                            )
                            refresh_workflow_btn = gr.Button("↻", variant="secondary", elem_classes=["icon-button"], scale=1, min_width=42)

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
                                minimum=0,
                                maximum=2147483647,
                                info="Starting seed (will increment for each variant; 0-2147483647)"
                            )

                        with gr.Accordion("📋 Storyboard Preview (JSON)", open=False):
                            storyboard_preview = gr.Code(
                                label="Loaded Storyboard Details",
                                language="json",
                                value=initial_storyboard_json,
                                lines=20,
                                max_lines=20,
                                interactive=False
                            )

                with gr.Column():
                    with gr.Group():
                        gr.Markdown("### 🚀 Run")
                        gr.Markdown("**Hinweis:** Start funktioniert, Stop ist experimentell, Resume deaktiviert (nicht refresh-sicher). Bitte Seite nicht neu laden. Robuster Job-Manager folgt in V2.")

                        with gr.Row():
                            start_btn = gr.Button("▶️ Start Generation", variant="primary", elem_classes=["primary-full"])
                        with gr.Row(elem_classes=["inline-row"]):
                            stop_btn = gr.Button("⏹️ Stop (experimentell)", variant="stop", elem_classes=["secondary-full"])
                            resume_btn = gr.Button("⏯️ Resume (deaktiviert)", variant="secondary", interactive=False, elem_classes=["secondary-full"])

                        status_text = gr.Markdown("**Status:** Ready - Load a storyboard to begin")

                        with gr.Accordion("Progress Details", open=True):
                            progress_details = gr.Markdown("No generation in progress")

                        with gr.Accordion("💾 Checkpoint Info", open=False):
                            checkpoint_info = gr.JSON(label="Checkpoint Status", value={})

            with gr.Group():
                gr.Markdown("## 🖼️ Generated Keyframes")
                current_shot_display = gr.Markdown("**Current Shot:** None")
                keyframe_gallery = gr.Gallery(
                    label="Keyframes (All Variants)",
                    show_label=True,
                    columns=4,
                    rows=2,
                    height="auto",
                    object_fit="contain"
                )
                with gr.Row(elem_classes=["inline-row"]):
                    clear_gallery_btn = gr.Button("🗑️ Clear Gallery", variant="secondary", elem_classes=["secondary-full"])
                    open_output_btn = gr.Button("📁 Open Output Folder", variant="secondary", elem_classes=["secondary-full"])

            refresh_btn.click(
                fn=self._get_storyboard_info,
                outputs=[storyboard_info]
            )

            start_btn.click(
                fn=self.start_generation,
                inputs=[workflow_dropdown, variants_per_shot, base_seed],
                outputs=[keyframe_gallery, status_text, progress_details, checkpoint_info, current_shot_display]
            )

            resume_btn.click(
                fn=self.resume_generation,
                inputs=[workflow_dropdown],
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

            interface.load(
                fn=self._reset_controls,
                outputs=[start_btn, stop_btn, resume_btn, status_text, progress_details]
            )

        return interface

    @handle_errors("Failed to load storyboard", return_tuple=True)
    def _load_storyboard_model(self, storyboard_file: str) -> domain_models.Storyboard:
        storyboard = StoryboardService.load_from_config(self.config, filename=storyboard_file)
        StoryboardService.apply_resolution_from_config(storyboard, self.config)
        storyboard.raw["storyboard_file"] = storyboard_file
        return storyboard

    @handle_errors("Ungültige Eingabeparameter", return_tuple=True)
    def _validate_generation_inputs(self, variants_per_shot: int, base_seed: int, workflow_file: str) -> KeyframeGeneratorInput:
        validated_inputs = KeyframeGeneratorInput(
            variants_per_shot=int(variants_per_shot),
            base_seed=int(base_seed)
        )
        WorkflowFileInput(workflow_file=workflow_file)
        return validated_inputs

    def load_storyboard(self, storyboard_file: str) -> Tuple[str, str]:
        if not storyboard_file or storyboard_file.startswith("No storyboards"):
            return "{}", "**❌ Error:** No storyboard selected"

        storyboard, error = self._load_storyboard_model(storyboard_file)
        if error:
            return "{}", error

        self.current_storyboard = storyboard
        storyboard_json = json.dumps(storyboard.raw, indent=2)
        total_shots = len(storyboard.shots)
        project_name = storyboard.project or "Unknown"
        status = f"**✅ Loaded:** {project_name} - {total_shots} shots"
        return storyboard_json, status

    def load_storyboard_from_config(self) -> Tuple[str, str]:
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            return "{}", "**❌ Error:** Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen."

        storyboard, error = self._load_storyboard_model(storyboard_file)
        if error:
            return "{}", error

        self.current_storyboard = storyboard
        storyboard_json = json.dumps(storyboard.raw, indent=2)
        total_shots = len(storyboard.shots)
        project_name = storyboard.project or "Unknown"
        status = f"**✅ Loaded:** {project_name} - {total_shots} shots"
        return storyboard_json, status

    def start_generation(
        self,
        workflow_file: str,
        variants_per_shot: int,
        base_seed: int,
        progress=gr.Progress(track_tqdm=True)
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            yield [], "**❌ Error:** Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen.", "No storyboard", {}, "No shot"
            return

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            yield [], "**❌ Error:** Kein aktives Projekt. Bitte zuerst im Tab '📁 Projekt' auswählen.", "No project", {}, "No shot"
            return

        validated_inputs, validation_error = self._validate_generation_inputs(variants_per_shot, base_seed, workflow_file)
        if validation_error:
            yield [], validation_error, "Ungültige Eingabeparameter", {}, "Error"
            return

        if self.current_storyboard is None:
            _, load_status = self.load_storyboard(storyboard_file)
            if "Error" in load_status:
                yield [], load_status, "No progress", {}, "No shot"
                return

        checkpoint = self.keyframe_service.prepare_checkpoint(
            storyboard=self.current_storyboard,
            workflow_file=workflow_file,
            variants_per_shot=validated_inputs.variants_per_shot,
            base_seed=validated_inputs.base_seed
        )

        self._save_checkpoint(checkpoint, storyboard_file, project)

        # Get ComfyUI URL from settings
        comfy_url = self.config.get_comfy_url()

        yield from self.generation_service.run_generation(
            storyboard=self.current_storyboard,
            workflow_file=workflow_file,
            checkpoint=checkpoint,
            project=project,
            comfy_url=comfy_url,
            progress_callback=progress
        )

    def resume_generation(
        self,
        workflow_file: str,
        progress=gr.Progress(track_tqdm=True)
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            yield [], "**❌ Error:** Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen.", "No storyboard", {}, "No shot"
            return

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            yield [], "**❌ Error:** Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen.", "No project", {}, "No shot"
            return

        checkpoint = self._load_checkpoint(storyboard_file, project)
        if not checkpoint:
            yield [], "**❌ Error:** No checkpoint found. Start a new generation first.", "No checkpoint", {}, "None"
            return

        if checkpoint.get("status") == "completed":
            yield [], "**✅ Info:** Generation already completed. Start a new generation or load existing keyframes.", "Already complete", checkpoint, "Complete"
            return

        if self.current_storyboard is None:
            _, load_status = self.load_storyboard(storyboard_file)
            if "Error" in load_status:
                yield [], load_status, "No progress", {}, "No shot"
                return

        checkpoint["status"] = "running"
        checkpoint["resumed_at"] = datetime.now().isoformat()

        # Get ComfyUI URL from settings
        comfy_url = self.config.get_comfy_url()

        yield from self.generation_service.run_generation(
            storyboard=self.current_storyboard,
            workflow_file=workflow_file,
            checkpoint=checkpoint,
            project=project,
            comfy_url=comfy_url,
            progress_callback=progress
        )

    def stop_generation(self) -> Tuple[str, str]:
        return self.generation_service.stop_generation()

    def _reset_controls(self):
        self.generation_service.stop_requested = False
        self.generation_service.is_running = False
        status = "**Status:** Bereit. Start kann erneut gedrückt werden."
        progress_md = "No generation in progress"
        return (
            gr.update(interactive=True),
            gr.update(interactive=False),
            gr.update(interactive=False),
            status,
            progress_md,
        )

    def _status_bar(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        storyboard = self.config.get_current_storyboard()
        width, height = self.config.get_resolution_tuple()
        comfy_url = self.config.get_comfy_url()

        parts = []
        if project:
            badge = "✅" if os.path.isdir(project.get("path", "")) else "⚠️"
            parts.append(f"Projekt: {badge} {project.get('name')} (`{project.get('slug')}`)")
        else:
            parts.append("Projekt: ⚠️ keines gewählt")

        if storyboard:
            sb_badge = "✅" if os.path.exists(storyboard) else "⚠️"
            parts.append(f"Storyboard: {sb_badge} `{self._short_storyboard_path(storyboard)}`")
        else:
            parts.append("Storyboard: ⚠️ keines gesetzt")

        parts.append(f"Auflösung: {width}x{height}")
        parts.append(f"ComfyUI: {comfy_url}")
        return " | ".join(parts)

    def _short_storyboard_path(self, abs_path: str) -> str:
        if not abs_path:
            return abs_path
        marker = "/output/"
        if marker in abs_path:
            return abs_path.split(marker, 1)[-1]
        return os.path.basename(abs_path)

    @handle_errors("Konnte Ausgabeordner nicht öffnen")
    def open_output_folder(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Error:** Kein aktives Projekt. Bitte im Tab 'Projekt' auswählen."
        output_dir = self.project_manager.ensure_dir(project, "keyframes")
        os.makedirs(output_dir, exist_ok=True)
        os.system(f'xdg-open "{output_dir}"')
        return f"**📁 Opened:** `{output_dir}`"

    def _project_status_md(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Kein aktives Projekt:** Bitte im Tab `📁 Projekt` anlegen oder auswählen."
        return (
            f"**Aktives Projekt:** {project.get('name')} (`{project.get('slug')}`)\n"
            f"- Pfad: `{project.get('path')}`"
        )

    def _get_storyboard_info(self) -> str:
        """Get storyboard info for display (consistent with other tabs)."""
        self.config.refresh()
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**Storyboard:** ❌ No active project - create one in Tab 📁 Projekt"

        storyboard_path = self.config.get_current_storyboard()
        if storyboard_path:
            return f"**Storyboard:** {storyboard_path}\n\n*(aus Tab 📁 Projektverwaltung)*"
        else:
            return "**Storyboard:** ❌ No storyboard selected - select one in Tab 📁 Projekt"

    def _get_available_workflows(self) -> List[str]:
        workflows = self.workflow_registry.get_files(category="flux")
        return workflows if workflows else ["No workflows found - update workflow_presets.json"]

    def _get_default_workflow(self) -> Optional[str]:
        return self.workflow_registry.get_default(category="flux")

    def _save_checkpoint(self, checkpoint: Dict[str, Any], storyboard_file: str, project: Dict[str, Any]):
        try:
            self.generation_service._save_checkpoint(checkpoint, storyboard_file, project)  # pylint: disable=protected-access
        except Exception as exc:  # pragma: no cover
            logger.error(f"Failed to save checkpoint: {exc}", exc_info=True)

    def _load_checkpoint(self, storyboard_file: str, project: Dict[str, Any]) -> Optional[Dict]:
        try:
            checkpoint_dir = self.project_manager.ensure_dir(project, "checkpoints")
            base_name = os.path.splitext(os.path.basename(storyboard_file))[0]
            checkpoint_path = os.path.join(checkpoint_dir, f"{base_name}_checkpoint.json")
            if not os.path.exists(checkpoint_path):
                return None
            with open(checkpoint_path, "r") as f:
                return json.load(f)
        except Exception as exc:
            logger.error(f"Failed to load checkpoint: {exc}", exc_info=True)
            return None
