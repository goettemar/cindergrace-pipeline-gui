import os
import sys
import json
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any, Generator
import gradio as gr
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import create_folder_scanner, project_status_md, shorten_storyboard_path
from infrastructure.config_manager import ConfigManager
from infrastructure.workflow_registry import WorkflowRegistry, PREFIX_KEYFRAME, PREFIX_KEYFRAME_LORA
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from infrastructure.error_handler import handle_errors
from domain import models as domain_models
from domain.storyboard_service import StoryboardService
from domain.validators import KeyframeGeneratorInput, WorkflowFileInput
from services.keyframe_service import KeyframeGenerationService, KeyframeService
from services.character_lora_service import CharacterLoraService

logger = get_logger(__name__)
class KeyframeGeneratorAddon(BaseAddon):
    def __init__(self):
        super().__init__(
            name="Keyframe Generator",
            description="Generate multiple keyframe variants for each storyboard shot",
            category="production"
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
        self.character_lora_service = CharacterLoraService(self.config)

    def get_tab_name(self) -> str:
        return "🎬 Keyframes"

    def _project_status_md(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "No active project"
        name = project.get("name", "Unknown")
        slug = project.get("slug", "unknown")
        path = project.get("path", "")
        return f"Project: {name} ({slug}) – {path}"

    def render(self) -> gr.Blocks:
        # Auto-load storyboard on tab open
        initial_storyboard_json, initial_status = self.load_storyboard_from_config()

        with gr.Blocks() as interface:
            # Unified header: Tab name left, project status right
            project_status = gr.HTML(project_status_md(self.project_manager, "🎬 Keyframe Generator"))

            # Storyboard info (auto-refresh from config)
            storyboard_info = gr.Markdown(self._get_storyboard_info())

            with gr.Row():
                # Left Column: Setup & Controls (25%)
                with gr.Column(scale=1):
                    with gr.Group():
                        gr.Markdown("### ⚙️ Setup")

                        # Workflow scanner with action buttons
                        workflow_scanner = create_folder_scanner(
                            label="Workflow Template",
                            choices=self._get_available_workflows(),
                            value=self._get_default_workflow(),
                            info="Keyframe-Workflow (gcp_*)",
                            show_refresh=False,
                            action_buttons=[
                                ("⭐ Set as Default", "secondary", "sm"),
                                ("🔄 Scan", "secondary", "sm"),
                            ]
                        )
                        workflow_dropdown = workflow_scanner.dropdown
                        set_default_btn = workflow_scanner.action_btns[0]
                        rescan_btn = workflow_scanner.action_btns[1]
                        workflow_status = gr.Markdown("")

                        # Model selection dropdown (populated based on workflow's .models file)
                        model_dropdown = gr.Dropdown(
                            choices=self._get_available_models(self._get_default_workflow()),
                            value=self._get_default_model(self._get_default_workflow()),
                            label="Diffusion Model",
                            info="Tested models for this workflow",
                            visible=self._has_model_selection(self._get_default_workflow())
                        )

                        # Character-Model compatibility warning
                        compatibility_warning = gr.Markdown(
                            value="",
                            visible=False
                        )

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
                            info="Starting seed (increments per variant)"
                        )

                    # Start Generation Button
                    start_btn = gr.Button("▶️ Start Generation", variant="primary", size="lg")

                    # Status display
                    status_text = gr.Markdown("**Status:** Ready")
                    progress_details = gr.Markdown("")

                    # Hidden components for checkpoint (needed by generation service)
                    checkpoint_info = gr.JSON(visible=False, value={})
                    current_shot_display = gr.Markdown(visible=False, value="")

                    # Open Output & Clear Gallery Buttons
                    open_output_btn = gr.Button("📁 Open Output Folder", variant="secondary")
                    clear_gallery_btn = gr.Button("🗑️ Clear Gallery", variant="secondary")

                # Right Column: Gallery (75%)
                with gr.Column(scale=3):
                    gr.Markdown("### 🖼️ Generated Keyframes")
                    keyframe_gallery = gr.Gallery(
                        label="Keyframes (All Variants)",
                        show_label=False,
                        columns=2,
                        rows=None,
                        height="auto",
                        object_fit="contain",
                        allow_preview=True
                    )

            # Event handlers
            start_btn.click(
                fn=self.start_generation,
                inputs=[workflow_dropdown, variants_per_shot, base_seed, model_dropdown],
                outputs=[keyframe_gallery, status_text, progress_details, checkpoint_info, current_shot_display]
            )

            clear_gallery_btn.click(
                fn=lambda: ([], "**Status:** Gallery cleared", ""),
                outputs=[keyframe_gallery, status_text, progress_details]
            )

            open_output_btn.click(
                fn=self.open_output_folder,
                outputs=[status_text]
            )

            set_default_btn.click(
                fn=self._set_default_workflow,
                inputs=[workflow_dropdown],
                outputs=[workflow_status]
            )

            rescan_btn.click(
                fn=self._rescan_workflows,
                outputs=[workflow_dropdown, workflow_status]
            )

            # Update model dropdown when workflow changes
            workflow_dropdown.change(
                fn=self._on_workflow_change,
                inputs=[workflow_dropdown],
                outputs=[model_dropdown, compatibility_warning]
            )

            # Check character-model compatibility when model changes
            model_dropdown.change(
                fn=self._check_character_model_compatibility,
                inputs=[model_dropdown],
                outputs=[compatibility_warning]
            )

            # Auto-refresh storyboard on tab load
            interface.load(
                fn=self._on_tab_load,
                outputs=[project_status, storyboard_info, status_text, workflow_dropdown, compatibility_warning]
            )

        return interface

    def _on_tab_load(self):
        """Called when tab loads - refresh storyboard from config and reset status."""
        self.generation_service.stop_requested = False
        self.generation_service.is_running = False

        # Refresh config to pick up changes from other tabs (Storyboard Editor, Project tab)
        self.config.refresh()

        # NOTE: Removed auto-rescan to avoid performance issues with Gradio timers
        # Workflows are now cached - use Settings > Rescan Workflows if new files are added

        # Project status
        project_status = project_status_md(self.project_manager, "🎬 Keyframe Generator")

        # Reload storyboard from config (picks up changes from Storyboard Editor)
        _, load_status = self.load_storyboard_from_config()
        storyboard_info = self._get_storyboard_info()

        # Determine status based on load result
        if "Error" in load_status:
            status = load_status
        else:
            status = "**Status:** Ready"

        # Get updated workflow list after rescan
        workflows = self._get_available_workflows()
        default_workflow = self._get_default_workflow()
        workflow_update = gr.update(choices=workflows, value=default_workflow)

        # Check character-model compatibility with default model
        default_model = self._get_default_model(default_workflow)
        compatibility_update = self._check_character_model_compatibility(default_model)

        return project_status, storyboard_info, status, workflow_update, compatibility_update

    @handle_errors("Failed to load storyboard", return_tuple=True)
    def _load_storyboard_model(self, storyboard_file: str) -> domain_models.Storyboard:
        storyboard = StoryboardService.load_from_config(self.config, storyboard_file)
        StoryboardService.apply_resolution_from_config(storyboard, self.config)
        storyboard.raw["storyboard_file"] = storyboard_file
        return storyboard

    @handle_errors("Invalid input parameters", return_tuple=True)
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
            return "{}", "**❌ Error:** No storyboard set. Please select one in the '📁 Project' tab."

        storyboard, error = self._load_storyboard_model(storyboard_file)
        if error:
            return "{}", error

        self.current_storyboard = storyboard
        storyboard_json = json.dumps(storyboard.raw, indent=2)
        total_shots = len(storyboard.shots)
        project_name = storyboard.project or "Unknown"
        status = f"**✅ Loaded:** {project_name} - {total_shots} shots"
        return storyboard_json, status

    def _storyboard_has_lora(self) -> bool:
        """Check if current storyboard has any shots with character_lora set."""
        if not self.current_storyboard:
            return False
        for shot in self.current_storyboard.shots:
            if shot.character_lora:
                return True
        return False

    def _resolve_workflow_for_lora(self, workflow_file: str) -> Tuple[str, Optional[str]]:
        """Resolve workflow file, switching to LoRA variant if needed.

        Args:
            workflow_file: Selected workflow file (gcp_*)

        Returns:
            Tuple of (resolved_workflow_file, warning_message or None)
        """
        has_lora = self._storyboard_has_lora()

        if not has_lora:
            # No LoRA in storyboard, use selected workflow
            return workflow_file, None

        # Storyboard has LoRA - try to find LoRA variant
        lora_variant = self.workflow_registry.get_lora_variant(workflow_file)

        if lora_variant:
            logger.info(f"LoRA detected in storyboard - using {lora_variant} instead of {workflow_file}")
            return lora_variant, None
        else:
            # LoRA in storyboard but no LoRA workflow available
            warning = (
                f"⚠️ **Warning:** Storyboard contains Character LoRA, but no matching "
                f"`gcpl_*` workflow found for `{workflow_file}`. "
                f"LoRA will be ignored."
            )
            logger.warning(warning)
            return workflow_file, warning

    def start_generation(
        self,
        workflow_file: str,
        variants_per_shot: int,
        base_seed: int,
        selected_model: str = "(Standard)",
        progress=gr.Progress(track_tqdm=True)
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            yield [], "**❌ Error:** No storyboard set. Please select one in the '📁 Project' tab.", "No storyboard", {}, "No shot"
            return

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            yield [], "**❌ Error:** No active project. Please select one in the '📁 Project' tab first.", "No project", {}, "No shot"
            return

        validated_inputs, validation_error = self._validate_generation_inputs(variants_per_shot, base_seed, workflow_file)
        if validation_error:
            yield [], validation_error, "Invalid input parameters", {}, "Error"
            return

        if self.current_storyboard is None:
            _, load_status = self.load_storyboard(storyboard_file)
            if "Error" in load_status:
                yield [], load_status, "No progress", {}, "No shot"
                return

        # Resolve workflow (auto-switch to LoRA variant if needed)
        resolved_workflow, lora_warning = self._resolve_workflow_for_lora(workflow_file)
        if lora_warning:
            yield [], lora_warning, "LoRA Warning", {}, "Warning"
            # Continue with generation despite warning

        # Determine model override (None if "(Standard)" selected)
        model_override = None if selected_model == "(Standard)" else selected_model

        checkpoint = self.keyframe_service.prepare_checkpoint(
            storyboard=self.current_storyboard,
            workflow_file=resolved_workflow,
            variants_per_shot=validated_inputs.variants_per_shot,
            base_seed=validated_inputs.base_seed
        )

        self._save_checkpoint(checkpoint, storyboard_file, project)

        # Get ComfyUI URL from settings
        comfy_url = self.config.get_comfy_url()

        yield from self.generation_service.run_generation(
            storyboard=self.current_storyboard,
            workflow_file=resolved_workflow,
            checkpoint=checkpoint,
            project=project,
            comfy_url=comfy_url,
            progress_callback=progress,
            model_override=model_override
        )

    def resume_generation(
        self,
        workflow_file: str,
        progress=gr.Progress(track_tqdm=True)
    ) -> Generator[Tuple[List[str], str, str, Dict, str], None, None]:
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            yield [], "**❌ Error:** No storyboard set. Please select one in the '📁 Project' tab.", "No storyboard", {}, "No shot"
            return

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            yield [], "**❌ Error:** No active project. Please select one in the '📁 Project' tab.", "No project", {}, "No shot"
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
        """Stop generation (kept for future use - see Backlog #001)."""
        return self.generation_service.stop_generation()

    def _status_bar(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        storyboard = self.config.get_current_storyboard()
        width, height = self.config.get_resolution_tuple()
        comfy_url = self.config.get_comfy_url()

        parts = []
        if project:
            badge = "✅" if os.path.isdir(project.get("path", "")) else "⚠️"
            parts.append(f"Project: {badge} {project.get('name')} (`{project.get('slug')}`)")
        else:
            parts.append("Project: ⚠️ none selected")

        if storyboard:
            sb_badge = "✅" if os.path.exists(storyboard) else "⚠️"
            parts.append(f"Storyboard: {sb_badge} `{shorten_storyboard_path(storyboard)}`")
        else:
            parts.append("Storyboard: ⚠️ none set")

        parts.append(f"Resolution: {width}x{height}")
        parts.append(f"ComfyUI: {comfy_url}")
        return " | ".join(parts)

    @handle_errors("Could not open output folder")
    def open_output_folder(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Error:** No active project. Please select one in the 'Project' tab."
        output_dir = self.project_manager.ensure_dir(project, "keyframes")
        os.makedirs(output_dir, exist_ok=True)
        os.system(f'xdg-open "{output_dir}"')
        return f"**📁 Opened:** `{output_dir}`"

    def _get_storyboard_info(self) -> str:
        """Get storyboard info for display."""
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file or not os.path.exists(storyboard_file):
            return "**Storyboard:** Not loaded"
        filename = os.path.basename(storyboard_file)
        return f"**Storyboard:** `{filename}`"

    def _get_available_workflows(self) -> List[str]:
        """Get available keyframe workflows (gcp_* prefix)."""
        workflows = self.workflow_registry.get_files(PREFIX_KEYFRAME)
        return workflows if workflows else ["No gcp_* workflows found"]

    def _get_default_workflow(self) -> Optional[str]:
        """Get default keyframe workflow from SQLite."""
        return self.workflow_registry.get_default(PREFIX_KEYFRAME)

    def _set_default_workflow(self, workflow_file: str) -> str:
        """Set selected workflow as default for keyframe generation."""
        if not workflow_file or workflow_file.startswith("No "):
            return "**⚠️ No workflow selected**"

        success = self.workflow_registry.set_default(PREFIX_KEYFRAME, workflow_file)
        if success:
            display_name = self.workflow_registry.get_display_name(workflow_file)
            logger.info(f"Set default keyframe workflow: {workflow_file}")
            return f"**✅ Default set:** {display_name}"
        else:
            return "**❌ Error setting default**"

    def _rescan_workflows(self):
        """Rescan filesystem for workflows and update cache."""
        count, _ = self.workflow_registry.rescan(PREFIX_KEYFRAME)
        # Also scan LoRA variants
        lora_count, _ = self.workflow_registry.rescan(PREFIX_KEYFRAME_LORA)

        workflows = self._get_available_workflows()
        default = self._get_default_workflow()

        status = f"**✅ Scan complete:** {count} Keyframe + {lora_count} LoRA Workflows"
        return gr.update(choices=workflows, value=default), status

    def _get_comfy_models_dir(self) -> str:
        """Get ComfyUI models directory path."""
        return os.path.join(self.config.get_comfy_root(), "models")

    def _get_available_models(self, workflow_file: Optional[str]) -> List[str]:
        """Get available compatible models for a workflow.

        Args:
            workflow_file: Workflow filename

        Returns:
            List of model paths (relative), or ["(Standard)"] if no .models file
        """
        if not workflow_file:
            return ["(Standard)"]

        comfy_models_dir = self._get_comfy_models_dir()
        models = self.workflow_registry.get_available_compatible_models(workflow_file, comfy_models_dir)

        if not models:
            return ["(Standard)"]

        # Return just the paths (display_name, path) -> path
        return [path for _, path in models]

    def _get_default_model(self, workflow_file: Optional[str]) -> Optional[str]:
        """Get default model for a workflow (first available)."""
        models = self._get_available_models(workflow_file)
        if models and models[0] != "(Standard)":
            return models[0]
        return "(Standard)"

    def _has_model_selection(self, workflow_file: Optional[str]) -> bool:
        """Check if workflow has model selection (.models file with available models)."""
        if not workflow_file:
            return False
        return len(self._get_available_models(workflow_file)) > 0 and \
               self._get_available_models(workflow_file)[0] != "(Standard)"

    def _on_workflow_change(self, workflow_file: str):
        """Update model dropdown when workflow changes."""
        models = self._get_available_models(workflow_file)
        default_model = self._get_default_model(workflow_file)
        has_models = self._has_model_selection(workflow_file)

        # Also check compatibility with new default model
        warning_update = self._check_character_model_compatibility(default_model)

        return (
            gr.update(
                choices=models,
                value=default_model,
                visible=has_models
            ),
            warning_update
        )

    def _check_character_model_compatibility(self, selected_model: str):
        """Check if selected model is compatible with storyboard characters.

        Returns:
            gr.update for compatibility_warning component
        """
        if not selected_model or selected_model == "(Standard)":
            return gr.update(value="", visible=False)

        if not self.current_storyboard:
            return gr.update(value="", visible=False)

        # Collect all unique character_loras from storyboard
        character_loras = set()
        for shot in self.current_storyboard.shots:
            if shot.character_lora:
                character_loras.add(shot.character_lora)

        if not character_loras:
            return gr.update(value="", visible=False)

        # Check compatibility for each character
        warnings = []
        for char_id in character_loras:
            result = self.character_lora_service.get_compatibility_warning(char_id, selected_model)
            if result:
                warning_msg, compatible_models = result
                warnings.append(warning_msg)

        if warnings:
            full_warning = "\n\n".join(warnings)
            full_warning += "\n\n**Generate anyway?** Generation will not be blocked."
            return gr.update(value=full_warning, visible=True)

        return gr.update(value="", visible=False)

    def _get_storyboard_characters(self) -> List[str]:
        """Get all character_lora IDs from current storyboard.

        Returns:
            List of unique character IDs
        """
        if not self.current_storyboard:
            return []

        characters = set()
        for shot in self.current_storyboard.shots:
            if shot.character_lora:
                characters.add(shot.character_lora)

        return list(characters)

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
