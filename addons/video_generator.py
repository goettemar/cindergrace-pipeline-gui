import os
import sys
import subprocess
import json
from copy import deepcopy
from typing import Dict, Any, List, Tuple, Optional
import gradio as gr
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import (
    create_folder_scanner,
    format_project_status_extended,
    project_status_md,
    storyboard_status_md,
    create_storyboard_section,
)
from addons.helpers.storyboard_loader import load_storyboard_from_config
from addons.helpers.plan_formatter import format_plan_summary, format_plan_shot
from infrastructure.config_manager import ConfigManager
from infrastructure.workflow_registry import WorkflowRegistry, PREFIX_VIDEO
from infrastructure.model_validator import ModelValidator
from infrastructure.state_store import VideoGeneratorStateStore
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.error_handler import handle_errors
from domain import models as domain_models
from domain.storyboard_service import StoryboardService, load_selection
from domain.validators import VideoGeneratorInput, WorkflowFileInput, SelectionFileInput
from services.video.video_generation_service import VideoGenerationService
from services.video.video_plan_builder import VideoPlanBuilder
from services.keyframe.workflow_utils import inject_model_override

logger = get_logger(__name__)

NO_PLAN_TEXT = "No plan calculated yet."
NO_SHOT_TEXT = "No shot selected."

class VideoGeneratorAddon(BaseAddon):
    def __init__(self):
        super().__init__(name="Video Generator", description="Use selected keyframes to drive Wan 2.2 clip generation", category="production")
        self.config = ConfigManager()
        self.workflow_registry = WorkflowRegistry()
        self.project_manager = ProjectStore(self.config)
        self.state_store = VideoGeneratorStateStore()
        self.model_validator = ModelValidator(self.config.get_comfy_root())
        if hasattr(self.model_validator, "rebuild_index"):
            self.model_validator.rebuild_index()  # Build index immediately at startup
        model_count = len(getattr(self.model_validator, "_index", {}) or {})
        logger.info(f"Video Generator: ModelValidator initialized with {model_count} models")
        self.plan_builder = VideoPlanBuilder()  # Uses defaults: 73 frames, 24 fps
        self.video_service = VideoGenerationService(self.project_manager, self.model_validator, self.state_store, self.plan_builder)
        self.storyboard_model: Optional[domain_models.Storyboard] = None
        self.selection_model: Optional[domain_models.SelectionSet] = None
        self.max_clip_duration = 3.0

    @handle_errors("Failed to load storyboard", return_tuple=True)
    def _load_storyboard_model(self, storyboard_file: str) -> domain_models.Storyboard:
        storyboard_model = StoryboardService.load_from_config(self.config, filename=storyboard_file)
        StoryboardService.apply_resolution_from_config(storyboard_model, self.config)
        storyboard_model.raw["storyboard_file"] = storyboard_file
        return storyboard_model

    @handle_errors("Failed to load selection", return_tuple=True)
    def _load_selection_model(self, selection_path: str):
        return load_selection(selection_path)

    @handle_errors("Validation error", return_tuple=True)
    def _validate_video_inputs(self, fps: int, workflow_file: str) -> VideoGeneratorInput:
        validated_inputs = VideoGeneratorInput(fps=int(fps), max_segment_seconds=self.max_clip_duration)
        WorkflowFileInput(workflow_file=workflow_file)
        return validated_inputs

    @handle_errors("Validation error", return_tuple=True)
    def _validate_selection_file(self, selection_file: str) -> str:
        SelectionFileInput(selection_file=selection_file)
        return selection_file

    @handle_errors("Failed to load workflow", return_tuple=True)
    def _load_workflow_template(self, comfy_api: ComfyUIAPI, workflow_path: str):
        return comfy_api.load_workflow(workflow_path)

    def get_tab_name(self) -> str:
        return "🎥 Video"

    def _project_status_md(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "No active project"
        name = project.get("name", "Unknown")
        slug = project.get("slug", "unknown")
        path = project.get("path", "")
        return f"Project: {name} ({slug}) – {path}"

    def _auto_load_storyboard_and_selection(self) -> Dict[str, Any]:
        """Auto-load storyboard and selection during render() - returns initial UI data."""
        defaults = {
            "storyboard_status": "**Storyboard:** Not loaded yet",
            "storyboard_info": "{}",
            "storyboard_state": {},
            "selection_status": "**Selection:** No file loaded",
            "selection_state": {},
            "plan_summary": NO_PLAN_TEXT,
            "plan_state": [],
            "shot_choices": [],
            "selected_shot": None,
            "shot_md": NO_SHOT_TEXT,
            "preview_path": None,
        }

        try:
            self.config.refresh()
            storyboard_model, status_md, storyboard_raw = load_storyboard_from_config(self.config, apply_resolution=True)
            if not storyboard_model:
                logger.debug("Video Generator: No storyboard configured for auto-load")
                defaults["storyboard_status"] = status_md
                return defaults

            self.storyboard_model = storyboard_model
            defaults["storyboard_status"] = status_md
            defaults["storyboard_info"] = json.dumps(storyboard_raw, indent=2)
            defaults["storyboard_state"] = storyboard_raw

            # Try to auto-load selection
            project = self.project_manager.get_active_project(refresh=True)
            if project:
                default_selection = self._get_default_selection_file()
                if default_selection:
                    selection_path = os.path.join(self.project_manager.project_path(project, "selected"), default_selection)
                    if os.path.exists(selection_path):
                        selection_model, selection_error = self._load_selection_model(selection_path)
                        if not selection_error and selection_model:
                            selection_model.raw["selection_file"] = default_selection
                            self.selection_model = selection_model
                            plan_entries, summary, dropdown_choices, first_shot = self._build_plan_from_models()

                            defaults["selection_status"] = f"**Selection:** ✅ {default_selection} – {len(selection_model.selections)} Shots"
                            defaults["selection_state"] = selection_model.raw
                            defaults["plan_summary"] = summary
                            defaults["plan_state"] = plan_entries
                            defaults["shot_choices"] = dropdown_choices
                            defaults["selected_shot"] = first_shot

                            if plan_entries and first_shot:
                                shot_md, preview = self._format_plan_shot(plan_entries, first_shot)
                                defaults["shot_md"] = shot_md
                                defaults["preview_path"] = preview

                            logger.info(f"Video Generator: Auto-loaded storyboard and selection '{default_selection}'")
                            return defaults

            logger.info("Video Generator: Auto-loaded storyboard (no selection found)")
        except Exception as e:
            logger.error(f"Video Generator: Error in auto-load: {e}", exc_info=True)

        return defaults

    def _format_plan_shot(self, plan_entries: List[Dict[str, Any]], shot_id: str):
        """Wrapper for plan shot formatting (kept for backward compatibility)."""
        return format_plan_shot(plan_entries, shot_id)

    def render(self) -> gr.Blocks:
        project = self.project_manager.get_active_project(refresh=True)
        self._configure_state_store(project)
        saved = self.state_store.load() or {}
        self.config.refresh()
        default_storyboard = self.config.get_current_storyboard() or saved.get("storyboard_file")

        # Auto-load storyboard and selection during render (not via interface.load)
        auto_loaded = self._auto_load_storyboard_and_selection()

        selection_choices = self._get_available_selection_files()
        default_selection = saved.get("selection_file") if saved.get("selection_file") in selection_choices else self._get_default_selection_file()
        workflow_choices = self._get_available_workflows()
        # Always use registry default - it reflects the user's "Set as Default" choice
        default_workflow = self._get_default_workflow()

        # Merge saved state with auto-loaded data (auto-load takes precedence for fresh data)
        stored_plan = auto_loaded["plan_state"] if auto_loaded["plan_state"] else saved.get("plan_state", [])
        summary_text = auto_loaded["plan_summary"] if auto_loaded["plan_state"] else saved.get("plan_summary", NO_PLAN_TEXT)
        shot_choices = auto_loaded["shot_choices"] if auto_loaded["shot_choices"] else []
        selected_shot = auto_loaded["selected_shot"] if auto_loaded["selected_shot"] else saved.get("selected_shot")
        shot_md = auto_loaded["shot_md"] if auto_loaded["shot_md"] != NO_SHOT_TEXT else NO_SHOT_TEXT
        preview_path = auto_loaded["preview_path"]

        # If no auto-loaded data, fall back to saved state
        if not stored_plan and saved.get("plan_state"):
            stored_plan = saved.get("plan_state", [])
            summary_text, shot_choices, selected_shot, shot_md, preview_path = self._prepare_initial_plan_ui(stored_plan, saved.get("selected_shot"))
            summary_text = saved.get("plan_summary", summary_text)

        storyboard_state_value = auto_loaded["storyboard_state"] if auto_loaded["storyboard_state"] else saved.get("storyboard_state", {})
        selection_state_value = auto_loaded["selection_state"] if auto_loaded["selection_state"] else saved.get("selection_state", {})

        storyboard_state = gr.State(storyboard_state_value)
        selection_state = gr.State(selection_state_value)
        plan_state = gr.State(deepcopy(stored_plan))

        storyboard_status_default = auto_loaded["storyboard_status"] if auto_loaded["storyboard_state"] else saved.get("storyboard_status", "**Storyboard:** Not loaded yet")
        storyboard_info_default = auto_loaded["storyboard_info"] if auto_loaded["storyboard_state"] else saved.get("storyboard_info", "{}")
        selection_status_default = auto_loaded["selection_status"] if auto_loaded["selection_state"] else saved.get("selection_status", "**Selection:** No file loaded")
        status_text_default = saved.get("status_text", "**Status:** Ready")
        progress_text_default = saved.get("progress_md", "No generation started yet.\n\n💡 **Tip:** During generation, check `logs/pipeline.log` and the ComfyUI terminal for real-time progress.")
        last_video_path = saved.get("last_video") if saved.get("last_video") and os.path.exists(saved.get("last_video")) else None
        preview_path = preview_path if preview_path and os.path.exists(str(preview_path)) else None

        with gr.Blocks() as interface:
            # Unified header: Tab name left, project status right
            project_status = gr.HTML(format_project_status_extended(
                self.project_manager, self.config, "🎥 Video Generator"
            ))

            gr.Markdown("Use your selected keyframes to generate videos.")

            # Warning if ModelValidator is disabled
            if not self.model_validator.enabled:
                gr.Markdown(
                    "⚠️ **Warning:** Model validation is disabled. "
                    "ComfyUI path not configured or invalid. "
                    "Please set the correct path in **⚙️ Settings**, "
                    "otherwise missing models can only be detected during generation.",
                    elem_classes=["warning-banner"]
                )

            storyboard_section = create_storyboard_section(
                accordion_title="📁 Storyboard",
                info_md_value=storyboard_status_md(self.project_manager, default_storyboard, "🎥 Video Generator"),
                reload_label="📖 Reload Storyboard",
                reload_variant="secondary",
                reload_size="sm",
            )
            storyboard_md = storyboard_section.info_md
            load_storyboard_btn = storyboard_section.reload_btn
            storyboard_status = gr.Markdown(storyboard_status_default)
            selection_status = gr.Markdown(selection_status_default)

            # === 2-Column Layout ===
            with gr.Row():
                # Left Column (50%): Workflow, Generation Plan, Generate Button
                with gr.Column(scale=1):
                    with gr.Group():
                        gr.Markdown("## ⚙️ Workflow")
                        # Workflow scanner with action buttons
                        workflow_scanner = create_folder_scanner(
                            label="Video-Workflow",
                            choices=workflow_choices,
                            value=default_workflow,
                            info="Video-Workflow (gcv_*)",
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
                            choices=self._get_available_models(default_workflow),
                            value=self._get_default_model(default_workflow),
                            label="Video Model",
                            info="Kompatible Modelle für diesen Workflow",
                            visible=self._has_model_selection(default_workflow)
                        )

                        with gr.Row():
                            fps_slider = gr.Slider(minimum=12, maximum=30, step=1, value=24, label="Frames per Second", info="Standard 24 fps")
                            clip_duration_box = gr.Number(
                                value=self.max_clip_duration,
                                label="Clip Length (sec.)",
                                precision=1,
                                minimum=0.5,
                                maximum=30.0,
                                interactive=False,
                                info="Segment duration (fixed) 0.5-30s"
                            )

                    with gr.Group():
                        gr.Markdown("## 🗂️ Generation Plan")
                        plan_summary = gr.Markdown(summary_text)

                    with gr.Group():
                        generate_btn = gr.Button("▶️ Generate Clips", variant="primary", size="lg")

                        # Confirmation dialog (initially hidden)
                        with gr.Group(visible=False) as confirm_group:
                            confirm_summary = gr.Markdown("### ⚠️ Confirm Generation")
                            with gr.Row():
                                confirm_btn = gr.Button("✅ Confirm & Start", variant="primary")
                                cancel_btn = gr.Button("❌ Cancel", variant="secondary")

                        open_video_btn = gr.Button("📁 Open Output Folder", variant="secondary")
                        reload_storyboard_btn = gr.Button("🔄 Reload Storyboard", variant="secondary")
                        revalidate_models_btn = gr.Button("🔍 Revalidate Models", variant="secondary")
                        model_status = gr.Markdown("")

                # Right Column (50%): Shot Preview
                with gr.Column(scale=1):
                    with gr.Group():
                        gr.Markdown("## 🎬 Shot Preview")
                        plan_shot_dropdown = gr.Dropdown(choices=shot_choices, value=selected_shot if selected_shot in shot_choices else (shot_choices[0] if shot_choices else None), label="Shot select", interactive=True)
                        shot_preview_info = gr.Markdown(shot_md)
                        startframe_preview = gr.Image(label="Start Frame Preview", type="filepath", interactive=False, value=preview_path)

            # === Status Section (below columns) ===
            with gr.Group():
                status_text = gr.Markdown(status_text_default)
                progress_details = gr.Markdown(progress_text_default)
                last_video = gr.Video(label="Latest Clip", value=last_video_path, visible=True)

            load_storyboard_btn.click(fn=self._reload_storyboard_ui, outputs=[storyboard_md, storyboard_status, storyboard_state, selection_status, selection_state, plan_summary, plan_shot_dropdown, plan_state, shot_preview_info, startframe_preview])
            rescan_btn.click(fn=self._rescan_workflows, outputs=[workflow_dropdown, workflow_status])
            set_default_btn.click(fn=self._set_default_workflow, inputs=[workflow_dropdown], outputs=[workflow_status])
            plan_shot_dropdown.change(fn=self.on_plan_shot_change, inputs=[plan_state, plan_shot_dropdown], outputs=[shot_preview_info, startframe_preview])

            # Update model dropdown when workflow changes
            workflow_dropdown.change(fn=self._on_workflow_change, inputs=[workflow_dropdown], outputs=[model_dropdown])

            # Two-step generation: first show confirmation, then execute
            generate_btn.click(
                fn=self.prepare_generation,
                inputs=[workflow_dropdown, fps_slider, storyboard_state, plan_state, model_dropdown],
                outputs=[status_text, confirm_summary, confirm_group]
            )
            confirm_btn.click(
                fn=self.execute_generation,
                inputs=[workflow_dropdown, fps_slider, storyboard_state, plan_state, model_dropdown],
                outputs=[status_text, progress_details, plan_summary, plan_state, last_video, confirm_group]
            )
            cancel_btn.click(
                fn=lambda: (gr.update(visible=False), "**Status:** Generation cancelled"),
                outputs=[confirm_group, status_text]
            )

            open_video_btn.click(fn=self.open_video_folder, inputs=[storyboard_state], outputs=[status_text])
            reload_storyboard_btn.click(fn=self._reload_storyboard_ui, outputs=[storyboard_md, storyboard_status, storyboard_state, selection_status, selection_state, plan_summary, plan_shot_dropdown, plan_state, shot_preview_info, startframe_preview])
            revalidate_models_btn.click(fn=self.revalidate_models, outputs=[model_status])

            # Auto-refresh storyboard and selection on tab load
            interface.load(
                fn=self._on_tab_load,
                outputs=[
                    storyboard_md,
                    storyboard_status,
                    storyboard_state,
                    selection_status,
                    selection_state,
                    plan_summary,
                    plan_shot_dropdown,
                    plan_state,
                    shot_preview_info,
                    startframe_preview,
                    project_status,
                    workflow_dropdown,
                    model_dropdown,
                ],
            )

        return interface

    def _on_tab_load(self):
        """Called when tab loads - refresh storyboard and selection from config."""
        # NOTE: Removed auto-rescan to avoid performance issues with Gradio timers
        # Workflows are now cached - use Settings > Rescan Workflows if new files are added

        # Reload storyboard and selection (picks up changes from Storyboard Editor)
        result = self._reload_storyboard_ui()
        # result is: (storyboard_md, storyboard_status, storyboard_state, selection_status, selection_state, plan_summary, plan_shot_dropdown, plan_state, shot_md, preview)

        project_status = project_status_md(self.project_manager, "🎥 Video Generator")

        # Get updated workflow list after rescan
        workflows = self._get_available_workflows()
        default_workflow = self._get_default_workflow()
        workflow_update = gr.update(choices=workflows, value=default_workflow)

        # Get model dropdown update for the default workflow
        model_update = self._on_workflow_change(default_workflow)

        # Return all outputs in correct order
        return (
            result[0],          # storyboard_md
            result[1],          # storyboard_status
            result[2],          # storyboard_state
            result[3],          # selection_status
            result[4],          # selection_state
            result[5],          # plan_summary
            result[6],          # plan_shot_dropdown
            result[7],          # plan_state
            result[8],          # shot_preview_info
            result[9],          # startframe_preview
            project_status,     # project_status
            workflow_update,    # workflow_dropdown
            model_update,       # model_dropdown
        )

    def _reload_storyboard_ui(self):
        """Reload storyboard and return markdown info instead of JSON."""
        result = self.load_storyboard_and_selection()
        # Original returns: (storyboard_status, storyboard_info, storyboard_state, selection_status, selection_state, plan_summary, plan_shot_dropdown, plan_state, shot_md, preview)
        # Replace storyboard_info (JSON) with storyboard_md
        storyboard_md = storyboard_status_md(self.project_manager, self.config.get_current_storyboard(), "🎥 Video Generator")
        return (
            storyboard_md,      # storyboard_md (instead of position 0)
            result[0],          # storyboard_status
            result[2],          # storyboard_state (skip result[1] which was storyboard_info)
            result[3],          # selection_status
            result[4],          # selection_state
            result[5],          # plan_summary
            result[6],          # plan_shot_dropdown
            result[7],          # plan_state
            result[8],          # shot_preview_info
            result[9],          # startframe_preview
        )

    def revalidate_models(self) -> str:
        """Rebuild model index and return status message."""
        count = self.model_validator.rebuild_index()
        if count > 0:
            return f"✅ **{count} models** found in index."
        elif not self.model_validator.enabled:
            return "⚠️ Model validation disabled. Check ComfyUI path."
        else:
            return "⚠️ No models found. Check ComfyUI path."

    def load_storyboard_and_selection(self) -> Tuple[str, str, Dict[str, Any], str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        """Load storyboard from config and automatically load selection if available."""
        logger.info("Video Generator: Auto-loading storyboard and selection...")
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            logger.warning("Video Generator: No storyboard configured")
            return self._storyboard_error("**Storyboard:** ❌ No storyboard set. Please select one in the '📁 Project' tab.")
        storyboard_model, error = self._load_storyboard_model(storyboard_file)
        if error:
            return self._storyboard_error(error)
        self.storyboard_model = storyboard_model
        info = json.dumps(storyboard_model.raw, indent=2)
        storyboard_status = f"**Storyboard:** ✅ {storyboard_model.project} – {len(storyboard_model.shots)} Shots loaded"

        # Auto-load selection if available
        project = self.project_manager.get_active_project(refresh=True)
        if project:
            default_selection = self._get_default_selection_file()
            if default_selection:
                selection_path = os.path.join(self.project_manager.project_path(project, "selected"), default_selection)
                if os.path.exists(selection_path):
                    selection_model, selection_error = self._load_selection_model(selection_path)
                    if not selection_error and selection_model:
                        selection_model.raw["selection_file"] = default_selection
                        self.selection_model = selection_model
                        plan_entries, summary, dropdown_choices, first_shot = self._build_plan_from_models()
                        selection_status = f"**Selection:** ✅ {default_selection} – {len(selection_model.selections)} Shots"
                        dropdown = gr.update(choices=dropdown_choices, value=first_shot) if plan_entries else gr.update(choices=[], value=None)
                        shot_md, preview = self._format_plan_shot(plan_entries, first_shot) if plan_entries else (NO_SHOT_TEXT, None)
                        self._persist_state(storyboard_file=storyboard_file, storyboard_state=storyboard_model.raw, storyboard_status=storyboard_status, storyboard_info=info, selection_file=default_selection, selection_state=selection_model.raw, selection_status=selection_status, plan_state=plan_entries, plan_summary=summary, selected_shot=first_shot)
                        return storyboard_status, info, storyboard_model.raw, selection_status, selection_model.raw, summary, dropdown, plan_entries, shot_md, preview

        # No selection available
        self._persist_state(storyboard_file=storyboard_file, storyboard_state=storyboard_model.raw, storyboard_status=storyboard_status, storyboard_info=info, plan_state=[], plan_summary=NO_PLAN_TEXT, selected_shot=None)
        return storyboard_status, info, storyboard_model.raw, "**Selection:** No selection file found", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None

    def load_storyboard_from_config(self) -> Tuple[str, str, Dict[str, Any], str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        """Deprecated: Use load_storyboard_and_selection instead."""
        return self.load_storyboard_and_selection()
    def _storyboard_error(self, message: str):
        return message, "{}", {}, "**Selection:** Please load a file", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
    def load_selection(self, selection_file: str, storyboard_state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        self.config.refresh()
        selection_file = selection_file or self._get_default_selection_file()
        _, validation_error = self._validate_selection_file(selection_file)
        if validation_error:
            return f"**Selection:** ❌ {validation_error}", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        project = self.project_manager.get_active_project(refresh=True)
        if not project: return "**Selection:** ❌ No active project. Please select one in the '📁 Project' tab.", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        if not storyboard_state: return "**Selection:** ❌ Please load a storyboard first", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        selection_path = os.path.join(self.project_manager.project_path(project, "selected"), selection_file)
        if not os.path.exists(selection_path): return f"**Selection:** ❌ File not found ({selection_file})", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        selection_model, selection_error = self._load_selection_model(selection_path)
        if selection_error:
            return f"**Selection:** ❌ {selection_error}", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        selection_model.raw["selection_file"] = selection_file
        self.selection_model = selection_model
        if not self.storyboard_model:
            storyboard_model = StoryboardService.load_from_config(self.config, filename=storyboard_state.get("storyboard_file"))
            StoryboardService.apply_resolution_from_config(storyboard_model, self.config)
            self.storyboard_model = storyboard_model
        plan_entries, summary, dropdown_choices, first_shot = self._build_plan_from_models()
        selection_status = f"**Selection:** ✅ {selection_file} – {len(selection_model.selections)} Shots"
        dropdown = gr.update(choices=dropdown_choices, value=first_shot) if plan_entries else gr.update(choices=[], value=None)
        shot_md, preview = format_plan_shot(plan_entries, first_shot) if plan_entries else (NO_SHOT_TEXT, None)
        self._persist_state(selection_file=selection_file, selection_state=selection_model.raw, selection_status=selection_status, plan_state=plan_entries, plan_summary=summary, selected_shot=first_shot)
        return selection_status, selection_model.raw, summary, dropdown, plan_entries, shot_md, preview

    def _build_plan_from_models(self) -> Tuple[List[Dict[str, Any]], str, List[str], Optional[str]]:
        if not self.storyboard_model or not self.selection_model:
            return [], NO_PLAN_TEXT, [], None
        plan_entries = self.plan_builder.build(self.storyboard_model, self.selection_model).to_dict_list()
        summary = format_plan_summary(plan_entries) if plan_entries else NO_PLAN_TEXT
        dropdown_choices = [entry.get("plan_id") or entry.get("shot_id") for entry in plan_entries if entry.get("plan_id") or entry.get("shot_id")]
        dropdown_choices = [choice for choice in dropdown_choices if choice]
        first_choice = dropdown_choices[0] if dropdown_choices else None
        return plan_entries, summary, dropdown_choices, first_choice

    def _prepare_initial_plan_ui(self, plan: List[Dict[str, Any]], selected_shot: Optional[str]) -> Tuple[str, List[str], Optional[str], str, Optional[str]]:
        if not plan:
            return NO_PLAN_TEXT, [], None, NO_SHOT_TEXT, None
        choices = [entry.get("plan_id") or entry.get("shot_id") for entry in plan if entry.get("plan_id") or entry.get("shot_id")]
        choices = [shot for shot in choices if shot]
        default_shot = selected_shot if selected_shot in choices else (choices[0] if choices else None)
        summary = format_plan_summary(plan)
        shot_md, preview = format_plan_shot(plan, default_shot) if default_shot else (NO_SHOT_TEXT, None)
        return summary, choices, default_shot, shot_md, preview

    def on_plan_shot_change(self, plan_state: List[Dict[str, Any]], shot_id: str) -> Tuple[str, str]:
        info, preview = ("No shot selected.", None) if (not plan_state or not shot_id) else format_plan_shot(plan_state, shot_id)
        if shot_id:
            self._persist_state(selected_shot=shot_id)
        return info, preview

    def prepare_generation(self, workflow_file: str, fps: int, storyboard_state: Dict[str, Any], plan_state: List[Dict[str, Any]], selected_model: str = "(Standard)") -> Tuple[str, str, gr.update]:
        """Validate inputs and show confirmation dialog before generation."""
        # Basic validation
        validated_inputs, validation_error = self._validate_video_inputs(fps, workflow_file)
        if validation_error:
            return f"**Status:** ❌ {validation_error}", "", gr.update(visible=False)

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**Status:** ❌ No active project. Please select one in the '📁 Project' tab.", "", gr.update(visible=False)

        if not storyboard_state:
            return "**Status:** ❌ Please load a storyboard first", "", gr.update(visible=False)

        if not plan_state:
            return "**Status:** ❌ No generation plan available", "", gr.update(visible=False)

        if not workflow_file or workflow_file.startswith("No workflows"):
            return "**Status:** ❌ No workflow selected", "", gr.update(visible=False)

        ready_entries = [e for e in plan_state if e.get("ready")]
        if not ready_entries:
            missing = sorted({e.get("shot_id") for e in plan_state if e.get("start_frame_source") == "missing"})
            missing_hint = ", ".join(missing) if missing else "no start frames found"
            return f"**Status:** ❌ No shot with valid start frame (missing: {missing_hint})", "", gr.update(visible=False)

        # Build confirmation summary
        unique_shots = len({e.get("shot_id") for e in plan_state})
        total_segments = len(plan_state)
        ready_count = len(ready_entries)

        # Get resolution from first ready entry
        first_entry = ready_entries[0] if ready_entries else {}
        width = first_entry.get("width", "?")
        height = first_entry.get("height", "?")

        # Calculate total duration
        total_duration = sum(e.get("effective_duration", 0) or e.get("target_duration", 0) for e in ready_entries)

        # Format model display
        model_display = os.path.basename(selected_model) if selected_model and selected_model != "(Standard)" else "(Workflow Default)"

        confirm_md = f"""### ⚠️ Confirm Generation

Please check the settings before starting:

| Parameter | Value |
|-----------|-------|
| **Workflow** | `{workflow_file}` |
| **Model** | `{model_display}` |
| **Resolution** | {width} × {height} px |
| **FPS** | {fps} |
| **Shots** | {unique_shots} |
| **Segments** | {total_segments} ({ready_count} ready) |
| **Estimated Duration** | ~{total_duration:.1f}s video |

⏱️ **Note:** Generation may take several minutes per clip depending on the model.
"""

        return "**Status:** ⏳ Confirmation required...", confirm_md, gr.update(visible=True)

    def execute_generation(self, workflow_file: str, fps: int, storyboard_state: Dict[str, Any], plan_state: List[Dict[str, Any]], selected_model: str = "(Standard)") -> Tuple[str, str, str, List[Dict[str, Any]], str, gr.update]:
        """Execute generation after user confirmation."""
        # Run the actual generation
        status, progress, summary, updated_plan, last_video = self.generate_clips(workflow_file, fps, storyboard_state, plan_state, selected_model)
        # Hide confirmation dialog and return results
        return status, progress, summary, updated_plan, last_video, gr.update(visible=False)

    def generate_clips(self, workflow_file: str, fps: int, storyboard_state: Dict[str, Any], plan_state: List[Dict[str, Any]], selected_model: str = "(Standard)") -> Tuple[str, str, str, List[Dict[str, Any]], str]:
        validated_inputs, validation_error = self._validate_video_inputs(fps, workflow_file)
        if validation_error:
            return self._error_response(f"**Status:** ❌ {validation_error}", "Invalid input parameters", plan_state)
        project = self.project_manager.get_active_project(refresh=True)
        if not project: return self._error_response("**Status:** ❌ No active project. Please select one in the '📁 Project' tab.", "No data", plan_state)
        self._configure_state_store(project)
        if not storyboard_state: return self._error_response("**Status:** ❌ Please load a storyboard first", "No data", plan_state)
        if not plan_state: return self._error_response("**Status:** ❌ No generation plan available", "No data", plan_state)
        if not workflow_file or workflow_file.startswith("No workflows"): return self._error_response("**Status:** ❌ No workflow selected", "No data", plan_state)
        if not any(entry.get("ready") for entry in plan_state):
            missing = sorted({entry.get("shot_id") for entry in plan_state if entry.get("start_frame_source") == "missing"})
            missing_hint = ", ".join(missing) if missing else "no start frames found"
            return self._error_response(f"**Status:** ❌ No shot with valid start frame (missing: {missing_hint})", "Please export from the Selector or manually add start frames.", plan_state)

        # Resolve workflow: use SageAttention variant if enabled and available
        use_sage = self.config.use_sage_attention()
        resolved_workflow = self.workflow_registry.resolve_workflow(workflow_file, use_sage=use_sage)
        if resolved_workflow != workflow_file:
            logger.info(f"SageAttention aktiv: verwende {resolved_workflow} statt {workflow_file}")

        workflow_path = os.path.join(self.config.get_workflow_dir(), resolved_workflow)
        if not os.path.exists(workflow_path): return self._error_response(f"**Status:** ❌ Workflow not found ({resolved_workflow})", "No data", plan_state)
        comfy_url = self.config.get_comfy_url()
        comfy_api = ComfyUIAPI(comfy_url)
        conn = comfy_api.test_connection()
        if not conn.get("connected"): return self._error_response(f"**Status:** ❌ Connection failed ({conn.get('error')})", "No data", plan_state)
        workflow_template, workflow_error = self._load_workflow_template(comfy_api, workflow_path)
        if workflow_error:
            return self._error_response(f"**Status:** ❌ {workflow_error}", "No data", plan_state)

        # Inject model override if specified
        model_override = None if selected_model == "(Standard)" else selected_model
        if model_override:
            workflow_template = inject_model_override(workflow_template, model_override)
            logger.info(f"Model override applied: {model_override}")

        missing_models = self.model_validator.find_missing(workflow_template) if self.model_validator else []
        if missing_models: return self._error_response(f"**Status:** ❌ Models missing ({len(missing_models)})", self._format_missing_models(missing_models), plan_state)
        log_hint = "💡 **Tip:** For real-time progress see `logs/pipeline.log` and ComfyUI terminal.\n\n"
        # Get resolution from project config (central setting)
        resolution = self.config.get_resolution_tuple()
        updated_plan, logs, last_video_path = self.video_service.run_generation(plan_state=plan_state, workflow_template=workflow_template, fps=validated_inputs.fps, project=project, comfy_api=comfy_api, resolution=resolution)
        progress_md = log_hint + "### Progress\n" + "\n".join(logs)
        summary = format_plan_summary(updated_plan)
        status = "**Status:** ✅ Clips generated (see log)" if last_video_path else "**Status:** ⚠️ See log for details"
        self._persist_state(plan_state=updated_plan, plan_summary=summary, status_text=status, progress_md=progress_md, last_video=last_video_path, workflow_file=workflow_file)
        return status, progress_md, summary, updated_plan, last_video_path

    def _format_missing_models(self, missing: List[str]) -> str:
        items = "\n".join([f"  - `{name}`" for name in missing])
        return "### Missing Models\n- The following files are referenced in the workflow but not found in your ComfyUI/models/ folder:\n" + items + "\n\nPlease install the models or adjust the workflow via ⚙️ Settings."

    def open_video_folder(self, storyboard_state: Dict[str, Any]) -> str:
        project_data = self.project_manager.get_active_project(refresh=True)
        if not project_data:
            return "**Status:** ❌ No active project. Please select one in the '📁 Project' tab."
        dest_dir = self.project_manager.ensure_dir(project_data, "video")
        os.makedirs(dest_dir, exist_ok=True)
        subprocess.run(["xdg-open", dest_dir], check=False)
        return f"**Status:** 📁 Video-Folder opened ({dest_dir})"

    def _get_available_selection_files(self) -> List[str]:
        self.config.refresh()
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return []
        selected_dir = self.project_manager.project_path(project, "selected")
        if not os.path.exists(selected_dir):
            return []
        return [f for f in os.listdir(selected_dir) if f.endswith(".json")]
    def _get_default_selection_file(self) -> str:
        files = self._get_available_selection_files()
        return files[0] if files else None

    def _get_available_workflows(self) -> List[str]:
        """Get available video workflows (gcv_* prefix)."""
        workflows = self.workflow_registry.get_files(PREFIX_VIDEO)
        return workflows if workflows else ["No gcv_* workflows found"]

    def _get_default_workflow(self) -> str:
        """Get default video workflow from SQLite."""
        return self.workflow_registry.get_default(PREFIX_VIDEO)

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
        models = self._get_available_models(workflow_file)
        return len(models) > 0 and models[0] != "(Standard)"

    def _on_workflow_change(self, workflow_file: str):
        """Update model dropdown when workflow changes."""
        models = self._get_available_models(workflow_file)
        default_model = self._get_default_model(workflow_file)
        has_models = self._has_model_selection(workflow_file)

        return gr.update(
            choices=models,
            value=default_model,
            visible=has_models
        )

    def _set_default_workflow(self, workflow_file: str) -> str:
        """Set selected workflow as default for video generation."""
        if not workflow_file or workflow_file.startswith("No "):
            return "**⚠️ No workflow selected**"

        success = self.workflow_registry.set_default(PREFIX_VIDEO, workflow_file)
        if success:
            display_name = self.workflow_registry.get_display_name(workflow_file)
            logger.info(f"Set default video workflow: {workflow_file}")
            return f"**✅ Default set:** {display_name}"
        else:
            return "**❌ Error setting default**"

    def _rescan_workflows(self):
        """Rescan filesystem for workflows and update cache."""
        count, _ = self.workflow_registry.rescan(PREFIX_VIDEO)

        workflows = self._get_available_workflows()
        default = self._get_default_workflow()

        status = f"**✅ Scan complete:** {count} video workflows"
        return gr.update(choices=workflows, value=default), status

    def _persist_state(self, **kwargs):
        if self.state_store:
            self.state_store.update(**kwargs)

    def _configure_state_store(self, project: Optional[Dict[str, Any]]):
        state_path = os.path.join(project["path"], "video", "_state.json") if project else None
        self.state_store.configure(state_path)

    def _refresh_project_status(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        self._configure_state_store(project)
        return project_status_md(self.project_manager, "🎥 Video Generator")

    def _error_response(self, status_message: str, progress_message: str, plan_state: List[Dict[str, Any]]):
        summary = format_plan_summary(plan_state) if plan_state else NO_PLAN_TEXT
        # Don't persist error messages - they should not survive page refresh
        return status_message, progress_message, summary, plan_state, None

    def reset_state(self) -> Tuple[str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str, str, str, None]:
        """Reset generation state but keep storyboard loaded."""
        # Keep storyboard, only reset selection/plan/progress
        self._persist_state(
            selection_file=None,
            selection_state={},
            selection_status="**Selection:** No file loaded",
            plan_state=[],
            plan_summary=NO_PLAN_TEXT,
            selected_shot=None,
            status_text="**Status:** Ready",
            progress_md="No generation started yet.\n\n💡 **Tip:** During generation, check `logs/pipeline.log` and the ComfyUI terminal for real-time progress.",
            last_video=None
        )
        return (
            "**Selection:** No file loaded",  # selection_status
            {},  # selection_state
            NO_PLAN_TEXT,  # plan_summary
            gr.update(choices=[], value=None),  # plan_shot_dropdown
            [],  # plan_state
            NO_SHOT_TEXT,  # shot_preview_info
            None,  # startframe_preview
            "**Status:** Ready",  # status_text
            "No generation started yet.\n\n💡 **Tip:** During generation, check `logs/pipeline.log` and the ComfyUI terminal for real-time progress.",  # progress_details
            None  # last_video
        )

__all__ = ["VideoGeneratorAddon"]
