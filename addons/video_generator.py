import os
import sys
import json
import shutil
from copy import deepcopy
from typing import Dict, Any, List, Tuple, Optional
import gradio as gr
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.config_manager import ConfigManager
from infrastructure.workflow_registry import WorkflowRegistry
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

logger = get_logger(__name__)
NO_PLAN_TEXT = "Noch kein Plan berechnet."
NO_SHOT_TEXT = "Kein Shot ausgewählt."

class VideoGeneratorAddon(BaseAddon):
    def __init__(self):
        super().__init__(name="Video Generator", description="Use selected keyframes to drive Wan 2.2 clip generation")
        self.config = ConfigManager()
        self.workflow_registry = WorkflowRegistry()
        self.project_manager = ProjectStore(self.config)
        self.state_store = VideoGeneratorStateStore()
        self.model_validator = ModelValidator(self.config.get_comfy_root())
        self.plan_builder = VideoPlanBuilder(max_segment_seconds=3.0)
        self.video_service = VideoGenerationService(self.project_manager, self.model_validator, self.state_store, self.plan_builder)
        self.storyboard_model: Optional[domain_models.Storyboard] = None
        self.selection_model: Optional[domain_models.SelectionSet] = None
        self.max_clip_duration = 3.0

    @handle_errors("Storyboard laden fehlgeschlagen", return_tuple=True)
    def _load_storyboard_model(self, storyboard_file: str) -> domain_models.Storyboard:
        storyboard_model = StoryboardService.load_from_config(self.config, filename=storyboard_file)
        StoryboardService.apply_resolution_from_config(storyboard_model, self.config)
        storyboard_model.raw["storyboard_file"] = storyboard_file
        return storyboard_model

    @handle_errors("Auswahl konnte nicht geladen werden", return_tuple=True)
    def _load_selection_model(self, selection_path: str):
        return load_selection(selection_path)

    @handle_errors("Validierungsfehler", return_tuple=True)
    def _validate_video_inputs(self, fps: int, workflow_file: str) -> VideoGeneratorInput:
        validated_inputs = VideoGeneratorInput(fps=int(fps), max_segment_seconds=self.max_clip_duration)
        WorkflowFileInput(workflow_file=workflow_file)
        return validated_inputs

    @handle_errors("Validierungsfehler", return_tuple=True)
    def _validate_selection_file(self, selection_file: str) -> str:
        SelectionFileInput(selection_file=selection_file)
        return selection_file

    @handle_errors("Workflow konnte nicht geladen werden", return_tuple=True)
    def _load_workflow_template(self, comfy_api: ComfyUIAPI, workflow_path: str):
        return comfy_api.load_workflow(workflow_path)

    def get_tab_name(self) -> str:
        return "🎥 Video Generator"

    def _auto_load_storyboard_and_selection(self) -> Dict[str, Any]:
        """Auto-load storyboard and selection during render() - returns initial UI data."""
        defaults = {
            "storyboard_status": "**Storyboard:** Noch nicht geladen",
            "storyboard_info": "{}",
            "storyboard_state": {},
            "selection_status": "**Auswahl:** Noch keine Datei geladen",
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
            storyboard_file = self.config.get_current_storyboard()
            if not storyboard_file:
                logger.debug("Video Generator: No storyboard configured for auto-load")
                return defaults

            storyboard_model, error = self._load_storyboard_model(storyboard_file)
            if error or not storyboard_model:
                logger.warning(f"Video Generator: Could not auto-load storyboard: {error}")
                return defaults

            self.storyboard_model = storyboard_model
            defaults["storyboard_status"] = f"**Storyboard:** ✅ {storyboard_model.project} – {len(storyboard_model.shots)} Shots geladen"
            defaults["storyboard_info"] = json.dumps(storyboard_model.raw, indent=2)
            defaults["storyboard_state"] = storyboard_model.raw

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

                            defaults["selection_status"] = f"**Auswahl:** ✅ {default_selection} – {len(selection_model.selections)} Shots"
                            defaults["selection_state"] = selection_model.raw
                            defaults["plan_summary"] = summary
                            defaults["plan_state"] = plan_entries
                            defaults["shot_choices"] = dropdown_choices
                            defaults["selected_shot"] = first_shot

                            if plan_entries and first_shot:
                                shot_md, preview = self._format_plan_shot(plan_entries, first_shot)
                                defaults["shot_md"] = shot_md
                                defaults["preview_path"] = preview

                            logger.info(f"Video Generator: Auto-loaded storyboard '{storyboard_file}' and selection '{default_selection}'")
                            return defaults

            logger.info(f"Video Generator: Auto-loaded storyboard '{storyboard_file}' (no selection found)")
        except Exception as e:
            logger.error(f"Video Generator: Error in auto-load: {e}", exc_info=True)

        return defaults

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
        default_workflow = saved.get("workflow_file") if saved.get("workflow_file") in workflow_choices else self._get_default_workflow()

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

        storyboard_status_default = auto_loaded["storyboard_status"] if auto_loaded["storyboard_state"] else saved.get("storyboard_status", "**Storyboard:** Noch nicht geladen")
        storyboard_info_default = auto_loaded["storyboard_info"] if auto_loaded["storyboard_state"] else saved.get("storyboard_info", "{}")
        selection_status_default = auto_loaded["selection_status"] if auto_loaded["selection_state"] else saved.get("selection_status", "**Auswahl:** Noch keine Datei geladen")
        status_text_default = saved.get("status_text", "**Status:** Bereit")
        progress_text_default = saved.get("progress_md", "Noch keine Generierung gestartet.\n\n💡 **Tipp:** Während der Generierung siehe `logs/pipeline.log` und ComfyUI Terminal für Echtzeit-Fortschritt.")
        last_video_path = saved.get("last_video") if saved.get("last_video") and os.path.exists(saved.get("last_video")) else None
        preview_path = preview_path if preview_path and os.path.exists(str(preview_path)) else None

        with gr.Blocks() as interface:
            gr.Markdown("# 🎥 Wan 2.2 Video Generator - Phase 3 (Beta)")
            gr.Markdown("Nutze deine ausgewählten Keyframes aus Phase 2. Shots über 3 Sekunden werden segmentiert, LastFrames werden durchgereicht.")

            # Warning if ModelValidator is disabled
            if not self.model_validator.enabled:
                gr.Markdown(
                    "⚠️ **Warnung:** Model-Validierung ist deaktiviert. "
                    "ComfyUI-Pfad nicht konfiguriert oder ungültig. "
                    "Bitte in **⚙️ Settings** den korrekten Pfad setzen, "
                    "sonst können fehlende Modelle erst während der Generierung erkannt werden.",
                    elem_classes=["warning-banner"]
                )

            with gr.Group():
                gr.Markdown("## 🗂️ Projekt")
                project_status = gr.Markdown(self._project_status_md())
                refresh_project_btn = gr.Button("🔄 Projektstatus aktualisieren", size="sm")

            with gr.Accordion("📁 Storyboard & Auswahl", open=False):
                storyboard_md = gr.Markdown(self._current_storyboard_md(default_storyboard))
                load_storyboard_btn = gr.Button("📖 Storyboard neu laden", variant="secondary", size="sm")
                storyboard_status = gr.Markdown(storyboard_status_default)
                selection_status = gr.Markdown(selection_status_default)
                storyboard_info = gr.Code(label="Storyboard-Details", language="json", value=storyboard_info_default, lines=12, max_lines=20, interactive=False)

            with gr.Group():
                gr.Markdown("## ⚙️ Workflow")
                with gr.Row():
                    workflow_dropdown = gr.Dropdown(choices=workflow_choices, value=default_workflow, label="Video-Workflow", info="Wan 2.2 Workflow (konfigurierbar über ⚙️ Settings)")
                    refresh_workflow_btn = gr.Button("🔄", size="sm")
                with gr.Row():
                    fps_slider = gr.Slider(minimum=12, maximum=30, step=1, value=24, label="Frames pro Sekunde", info="Standard 24 fps")
                    clip_duration_box = gr.Number(
                        value=self.max_clip_duration,
                        label="Clip-Länge (Sek.)",
                        precision=1,
                        minimum=0.5,
                        maximum=30.0,
                        interactive=False,
                        info="Segment duration (fixed) 0.5-30s"
                    )
                gr.Markdown("**Hinweis:** Jeder Clip dauert **3 Sekunden**. Segmentierung inkl. LastFrame→StartFrame-Kette.")

            with gr.Group():
                gr.Markdown("## 🗂️ Generation Plan")
                plan_summary = gr.Markdown(summary_text)
                plan_shot_dropdown = gr.Dropdown(choices=shot_choices, value=selected_shot if selected_shot in shot_choices else (shot_choices[0] if shot_choices else None), label="Shot auswählen (Preview/Debug)", interactive=True)
                shot_preview_info = gr.Markdown(shot_md)
                startframe_preview = gr.Image(label="Startframe Vorschau", type="filepath", interactive=False, value=preview_path)

            with gr.Group():
                gr.Markdown("## 🚀 Clip-Generierung")
                with gr.Row():
                    generate_btn = gr.Button("▶️ Clips generieren", variant="primary", size="lg")
                    open_video_btn = gr.Button("📁 Ausgabeordner öffnen", variant="secondary")
                    reset_btn = gr.Button("♻️ Zurücksetzen", variant="secondary")

                # Confirmation dialog (initially hidden)
                with gr.Group(visible=False) as confirm_group:
                    confirm_summary = gr.Markdown("### ⚠️ Generierung bestätigen")
                    with gr.Row():
                        confirm_btn = gr.Button("✅ Bestätigen & Starten", variant="primary")
                        cancel_btn = gr.Button("❌ Abbrechen", variant="secondary")

                status_text = gr.Markdown(status_text_default)
                progress_details = gr.Markdown(progress_text_default)
                last_video = gr.Video(label="Letzter Clip", value=last_video_path, visible=True)

            refresh_project_btn.click(fn=self._refresh_project_status, outputs=[project_status])
            load_storyboard_btn.click(fn=self.load_storyboard_and_selection, outputs=[storyboard_status, storyboard_info, storyboard_state, selection_status, selection_state, plan_summary, plan_shot_dropdown, plan_state, shot_preview_info, startframe_preview])
            refresh_workflow_btn.click(fn=lambda: gr.update(choices=self._get_available_workflows(), value=self._get_default_workflow()), outputs=[workflow_dropdown])
            plan_shot_dropdown.change(fn=self.on_plan_shot_change, inputs=[plan_state, plan_shot_dropdown], outputs=[shot_preview_info, startframe_preview])

            # Two-step generation: first show confirmation, then execute
            generate_btn.click(
                fn=self.prepare_generation,
                inputs=[workflow_dropdown, fps_slider, storyboard_state, plan_state],
                outputs=[status_text, confirm_summary, confirm_group]
            )
            confirm_btn.click(
                fn=self.execute_generation,
                inputs=[workflow_dropdown, fps_slider, storyboard_state, plan_state],
                outputs=[status_text, progress_details, plan_summary, plan_state, last_video, confirm_group]
            )
            cancel_btn.click(
                fn=lambda: (gr.update(visible=False), "**Status:** Generierung abgebrochen"),
                outputs=[confirm_group, status_text]
            )

            reset_btn.click(fn=self.reset_state, outputs=[selection_status, selection_state, plan_summary, plan_shot_dropdown, plan_state, shot_preview_info, startframe_preview, status_text, progress_details, last_video])
            open_video_btn.click(fn=self.open_video_folder, inputs=[storyboard_state], outputs=[status_text])

            # Note: Auto-load is now done synchronously during render() via _auto_load_storyboard_and_selection()
            # The interface.load() event only fires on full page load, not on tab switch
        return interface
    def load_storyboard_and_selection(self) -> Tuple[str, str, Dict[str, Any], str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        """Load storyboard from config and automatically load selection if available."""
        logger.info("Video Generator: Auto-loading storyboard and selection...")
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            logger.warning("Video Generator: No storyboard configured")
            return self._storyboard_error("**Storyboard:** ❌ Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen.")
        storyboard_model, error = self._load_storyboard_model(storyboard_file)
        if error:
            return self._storyboard_error(error)
        self.storyboard_model = storyboard_model
        info = json.dumps(storyboard_model.raw, indent=2)
        storyboard_status = f"**Storyboard:** ✅ {storyboard_model.project} – {len(storyboard_model.shots)} Shots geladen"

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
                        selection_status = f"**Auswahl:** ✅ {default_selection} – {len(selection_model.selections)} Shots"
                        dropdown = gr.update(choices=dropdown_choices, value=first_shot) if plan_entries else gr.update(choices=[], value=None)
                        shot_md, preview = self._format_plan_shot(plan_entries, first_shot) if plan_entries else (NO_SHOT_TEXT, None)
                        self._persist_state(storyboard_file=storyboard_file, storyboard_state=storyboard_model.raw, storyboard_status=storyboard_status, storyboard_info=info, selection_file=default_selection, selection_state=selection_model.raw, selection_status=selection_status, plan_state=plan_entries, plan_summary=summary, selected_shot=first_shot)
                        return storyboard_status, info, storyboard_model.raw, selection_status, selection_model.raw, summary, dropdown, plan_entries, shot_md, preview

        # No selection available
        self._persist_state(storyboard_file=storyboard_file, storyboard_state=storyboard_model.raw, storyboard_status=storyboard_status, storyboard_info=info, plan_state=[], plan_summary=NO_PLAN_TEXT, selected_shot=None)
        return storyboard_status, info, storyboard_model.raw, "**Auswahl:** Keine Auswahl-Datei gefunden", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None

    def load_storyboard_from_config(self) -> Tuple[str, str, Dict[str, Any], str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        """Deprecated: Use load_storyboard_and_selection instead."""
        return self.load_storyboard_and_selection()
    def _storyboard_error(self, message: str):
        return message, "{}", {}, "**Auswahl:** Bitte Datei laden", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
    def load_selection(self, selection_file: str, storyboard_state: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        self.config.refresh()
        selection_file = selection_file or self._get_default_selection_file()
        _, validation_error = self._validate_selection_file(selection_file)
        if validation_error:
            return f"**Auswahl:** ❌ {validation_error}", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        project = self.project_manager.get_active_project(refresh=True)
        if not project: return "**Auswahl:** ❌ Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen.", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        if not storyboard_state: return "**Auswahl:** ❌ Bitte zuerst ein Storyboard laden", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        selection_path = os.path.join(self.project_manager.project_path(project, "selected"), selection_file)
        if not os.path.exists(selection_path): return f"**Auswahl:** ❌ Datei nicht gefunden ({selection_file})", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        selection_model, selection_error = self._load_selection_model(selection_path)
        if selection_error:
            return f"**Auswahl:** ❌ {selection_error}", {}, NO_PLAN_TEXT, gr.update(choices=[], value=None), [], NO_SHOT_TEXT, None
        selection_model.raw["selection_file"] = selection_file
        self.selection_model = selection_model
        if not self.storyboard_model:
            storyboard_model = StoryboardService.load_from_config(self.config, filename=storyboard_state.get("storyboard_file"))
            StoryboardService.apply_resolution_from_config(storyboard_model, self.config)
            self.storyboard_model = storyboard_model
        plan_entries, summary, dropdown_choices, first_shot = self._build_plan_from_models()
        selection_status = f"**Auswahl:** ✅ {selection_file} – {len(selection_model.selections)} Shots"
        dropdown = gr.update(choices=dropdown_choices, value=first_shot) if plan_entries else gr.update(choices=[], value=None)
        shot_md, preview = self._format_plan_shot(plan_entries, first_shot) if plan_entries else (NO_SHOT_TEXT, None)
        self._persist_state(selection_file=selection_file, selection_state=selection_model.raw, selection_status=selection_status, plan_state=plan_entries, plan_summary=summary, selected_shot=first_shot)
        return selection_status, selection_model.raw, summary, dropdown, plan_entries, shot_md, preview

    def _build_plan_from_models(self) -> Tuple[List[Dict[str, Any]], str, List[str], Optional[str]]:
        if not self.storyboard_model or not self.selection_model:
            return [], NO_PLAN_TEXT, [], None
        plan_entries = self.plan_builder.build(self.storyboard_model, self.selection_model).to_dict_list()
        summary = self._format_plan_summary(plan_entries) if plan_entries else NO_PLAN_TEXT
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
        summary = self._format_plan_summary(plan)
        shot_md, preview = self._format_plan_shot(plan, default_shot) if default_shot else (NO_SHOT_TEXT, None)
        return summary, choices, default_shot, shot_md, preview

    def on_plan_shot_change(self, plan_state: List[Dict[str, Any]], shot_id: str) -> Tuple[str, str]:
        info, preview = ("Kein Shot ausgewählt.", None) if (not plan_state or not shot_id) else self._format_plan_shot(plan_state, shot_id)
        if shot_id:
            self._persist_state(selected_shot=shot_id)
        return info, preview

    def prepare_generation(self, workflow_file: str, fps: int, storyboard_state: Dict[str, Any], plan_state: List[Dict[str, Any]]) -> Tuple[str, str, gr.update]:
        """Validate inputs and show confirmation dialog before generation."""
        # Basic validation
        validated_inputs, validation_error = self._validate_video_inputs(fps, workflow_file)
        if validation_error:
            return f"**Status:** ❌ {validation_error}", "", gr.update(visible=False)

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**Status:** ❌ Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen.", "", gr.update(visible=False)

        if not storyboard_state:
            return "**Status:** ❌ Bitte zuerst ein Storyboard laden", "", gr.update(visible=False)

        if not plan_state:
            return "**Status:** ❌ Kein Generierungs-Plan verfügbar", "", gr.update(visible=False)

        if not workflow_file or workflow_file.startswith("No workflows"):
            return "**Status:** ❌ Kein Workflow ausgewählt", "", gr.update(visible=False)

        ready_entries = [e for e in plan_state if e.get("ready")]
        if not ready_entries:
            missing = sorted({e.get("shot_id") for e in plan_state if e.get("start_frame_source") == "missing"})
            missing_hint = ", ".join(missing) if missing else "keine Startframes gefunden"
            return f"**Status:** ❌ Kein Shot mit gültigem Startframe (fehlend: {missing_hint})", "", gr.update(visible=False)

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

        confirm_md = f"""### ⚠️ Generierung bestätigen

Bitte überprüfe die Einstellungen vor dem Start:

| Parameter | Wert |
|-----------|------|
| **Workflow** | `{workflow_file}` |
| **Auflösung** | {width} × {height} px |
| **FPS** | {fps} |
| **Shots** | {unique_shots} |
| **Segmente** | {total_segments} ({ready_count} bereit) |
| **Geschätzte Dauer** | ~{total_duration:.1f}s Video |

⏱️ **Hinweis:** Die Generierung kann je nach Modell mehrere Minuten pro Clip dauern.
"""

        return "**Status:** ⏳ Bestätigung erforderlich...", confirm_md, gr.update(visible=True)

    def execute_generation(self, workflow_file: str, fps: int, storyboard_state: Dict[str, Any], plan_state: List[Dict[str, Any]]) -> Tuple[str, str, str, List[Dict[str, Any]], str, gr.update]:
        """Execute generation after user confirmation."""
        # Run the actual generation
        status, progress, summary, updated_plan, last_video = self.generate_clips(workflow_file, fps, storyboard_state, plan_state)
        # Hide confirmation dialog and return results
        return status, progress, summary, updated_plan, last_video, gr.update(visible=False)

    def generate_clips(self, workflow_file: str, fps: int, storyboard_state: Dict[str, Any], plan_state: List[Dict[str, Any]]) -> Tuple[str, str, str, List[Dict[str, Any]], str]:
        validated_inputs, validation_error = self._validate_video_inputs(fps, workflow_file)
        if validation_error:
            return self._error_response(f"**Status:** ❌ {validation_error}", "Ungültige Eingabeparameter", plan_state)
        project = self.project_manager.get_active_project(refresh=True)
        if not project: return self._error_response("**Status:** ❌ Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen.", "Keine Daten", plan_state)
        self._configure_state_store(project)
        if not storyboard_state: return self._error_response("**Status:** ❌ Bitte zuerst ein Storyboard laden", "Keine Daten", plan_state)
        if not plan_state: return self._error_response("**Status:** ❌ Kein Generierungs-Plan verfügbar", "Keine Daten", plan_state)
        if not workflow_file or workflow_file.startswith("No workflows"): return self._error_response("**Status:** ❌ Kein Workflow ausgewählt", "Keine Daten", plan_state)
        if not any(entry.get("ready") for entry in plan_state):
            missing = sorted({entry.get("shot_id") for entry in plan_state if entry.get("start_frame_source") == "missing"})
            missing_hint = ", ".join(missing) if missing else "keine Startframes gefunden"
            return self._error_response(f"**Status:** ❌ Kein Shot mit gültigem Startframe (fehlend: {missing_hint})", "Bitte im Selector exportieren oder manuell Startframes ablegen.", plan_state)
        workflow_path = os.path.join(self.config.get_workflow_dir(), workflow_file)
        if not os.path.exists(workflow_path): return self._error_response(f"**Status:** ❌ Workflow nicht gefunden ({workflow_file})", "Keine Daten", plan_state)
        comfy_url = self.config.get_comfy_url()
        comfy_api = ComfyUIAPI(comfy_url)
        conn = comfy_api.test_connection()
        if not conn.get("connected"): return self._error_response(f"**Status:** ❌ Verbindung fehlgeschlagen ({conn.get('error')})", "Keine Daten", plan_state)
        workflow_template, workflow_error = self._load_workflow_template(comfy_api, workflow_path)
        if workflow_error:
            return self._error_response(f"**Status:** ❌ {workflow_error}", "Keine Daten", plan_state)
        missing_models = self.model_validator.find_missing(workflow_template) if self.model_validator else []
        if missing_models: return self._error_response(f"**Status:** ❌ Modelle fehlen ({len(missing_models)})", self._format_missing_models(missing_models), plan_state)
        preflight_notice = "⚠️ ffmpeg nicht gefunden – LastFrame-Kette wird übersprungen\n\n" if shutil.which("ffmpeg") is None else ""
        log_hint = "💡 **Tipp:** Für Echtzeit-Fortschritt siehe `logs/pipeline.log` und ComfyUI Terminal.\n\n"
        updated_plan, logs, last_video_path = self.video_service.run_generation(plan_state=plan_state, workflow_template=workflow_template, fps=validated_inputs.fps, project=project, comfy_api=comfy_api)
        progress_md = log_hint + preflight_notice + "### Fortschritt\n" + "\n".join(logs)
        summary = self._format_plan_summary(updated_plan)
        status = "**Status:** ✅ Clips generiert (siehe Log)" if last_video_path else "**Status:** ⚠️ Siehe Log für Details"
        self._persist_state(plan_state=updated_plan, plan_summary=summary, status_text=status, progress_md=progress_md, last_video=last_video_path, workflow_file=workflow_file)
        return status, progress_md, summary, updated_plan, last_video_path

    def _format_plan_summary(self, plan: List[Dict[str, Any]]) -> str:
        total = len(plan)
        unique_shots = len({entry.get("shot_id") for entry in plan})
        ready = len([entry for entry in plan if entry.get("ready")])
        completed = len([entry for entry in plan if entry.get("status") == "completed"])
        missing_list = sorted({entry["shot_id"] for entry in plan if entry.get("start_frame_source") == "missing"})
        clamped_total = len({entry["shot_id"] for entry in plan if entry.get("segment_total", 1) > 1})
        waiting_segments = len([entry for entry in plan if entry.get("start_frame_source") == "chain_wait"])
        md = [
            "### Plan-Übersicht",
            f"- **Storyboard-Shots:** {unique_shots}",
            f"- **Clips (Segmente):** {total}",
            f"- **Bereit:** {ready}",
            f"- **Abgeschlossen:** {completed}",
            f"- **Segmentiert:** {clamped_total}",
            f"- **Wartet auf LastFrame-Start:** {waiting_segments}",
            f"- **Mit Startframe-Problemen:** {len(missing_list)}",
        ]
        return "\n".join(md + ([f"- ❗ Fehlende Shots: {', '.join(missing_list)}"] if missing_list else []))

    def _format_missing_models(self, missing: List[str]) -> str:
        items = "\n".join([f"  - `{name}`" for name in missing])
        return "### Fehlende Modelle\n- Die folgenden Dateien wurden im Workflow referenziert, aber nicht in deinem ComfyUI/models/ Ordner gefunden:\n" + items + "\n\nBitte installiere die Modelle oder passe den Workflow über ⚙️ Settings an."

    def _format_plan_shot(self, plan: List[Dict[str, Any]], plan_entry_id: str) -> Tuple[str, str]:
        entry = next((item for item in plan if (item.get("plan_id") or item.get("shot_id")) == plan_entry_id), None)
        if not entry:
            return "Shot nicht gefunden.", None
        lines = [
            f"### Shot {entry['shot_id']} – {entry['filename_base']}",
            f"- **Prompt:** {entry['prompt'][:160]}{'…' if len(entry['prompt']) > 160 else ''}",
            f"- **Auflösung:** {entry['width']}×{entry['height']}",
            f"- **Storyboard-Dauer:** {entry['duration']}s",
            f"- **Generierte Dauer:** {entry['effective_duration']}s",
            f"- **Segment:** {entry.get('segment_index', 1)}/{entry.get('segment_total', 1)} (Ziel: {entry.get('segment_requested_duration', entry.get('effective_duration'))}s)",
            f"- **Variante:** {entry.get('selected_file', 'n/a')}",
            f"- **Status:** {entry.get('status', 'pending')}",
        ]
        motion = entry.get("wan_motion")
        if motion:
            motion_desc = motion.get("notes") or motion.get("type")
            lines.append(f"- **Wan Motion:** {motion.get('type', 'n/a')} (Strength {motion.get('strength', '-')})")
            if motion_desc and motion_desc != motion.get("type"):
                lines.append(f"  - {motion_desc}")
        if entry.get("segment_total", 1) > 1 and entry.get("segment_index", 1) == 1:
            lines.append("- 🔁 Dieser Shot wird segmentiert.")
        if entry.get("start_frame_source") == "chain_wait":
            lines.append("- ⏳ Wartet auf LastFrame als Startframe.")
        elif not entry.get("ready"):
            lines.append("- ❌ Kein gültiger Startframe gefunden.")
        preview_path = entry.get("start_frame") if entry.get("ready") else None
        return "\n".join(lines), preview_path

    def open_video_folder(self, storyboard_state: Dict[str, Any]) -> str:
        project_data = self.project_manager.get_active_project(refresh=True)
        if not project_data:
            return "**Status:** ❌ Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen."
        dest_dir = self.project_manager.ensure_dir(project_data, "video")
        os.makedirs(dest_dir, exist_ok=True)
        os.system(f'xdg-open "{dest_dir}"')
        return f"**Status:** 📁 Video-Ordner geöffnet ({dest_dir})"

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
        workflows = self.workflow_registry.get_files(category="wan")
        return workflows if workflows else []

    def _get_default_workflow(self) -> str:
        return self.workflow_registry.get_default(category="wan")

    def _persist_state(self, **kwargs):
        if self.state_store:
            self.state_store.update(**kwargs)

    def _configure_state_store(self, project: Optional[Dict[str, Any]]):
        state_path = os.path.join(project["path"], "video", "_state.json") if project else None
        self.state_store.configure(state_path)

    def _project_status_md(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Kein aktives Projekt:** Bitte im Tab `📁 Projekt` anlegen oder auswählen."
        return f"**Aktives Projekt:** {project.get('name')} (`{project.get('slug')}`)\n- Pfad: `{project.get('path')}`"

    def _refresh_project_status(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        self._configure_state_store(project)
        return self._project_status_md()

    def _error_response(self, status_message: str, progress_message: str, plan_state: List[Dict[str, Any]]):
        summary = self._format_plan_summary(plan_state) if plan_state else NO_PLAN_TEXT
        self._persist_state(status_text=status_message, progress_md=progress_message)
        return status_message, progress_message, summary, plan_state, None

    def reset_state(self) -> Tuple[str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str, str, str, None]:
        """Reset generation state but keep storyboard loaded."""
        # Keep storyboard, only reset selection/plan/progress
        self._persist_state(
            selection_file=None,
            selection_state={},
            selection_status="**Auswahl:** Noch keine Datei geladen",
            plan_state=[],
            plan_summary=NO_PLAN_TEXT,
            selected_shot=None,
            status_text="**Status:** Bereit",
            progress_md="Noch keine Generierung gestartet.\n\n💡 **Tipp:** Während der Generierung siehe `logs/pipeline.log` und ComfyUI Terminal für Echtzeit-Fortschritt.",
            last_video=None
        )
        return (
            "**Auswahl:** Noch keine Datei geladen",  # selection_status
            {},  # selection_state
            NO_PLAN_TEXT,  # plan_summary
            gr.update(choices=[], value=None),  # plan_shot_dropdown
            [],  # plan_state
            NO_SHOT_TEXT,  # shot_preview_info
            None,  # startframe_preview
            "**Status:** Bereit",  # status_text
            "Noch keine Generierung gestartet.\n\n💡 **Tipp:** Während der Generierung siehe `logs/pipeline.log` und ComfyUI Terminal für Echtzeit-Fortschritt.",  # progress_details
            None  # last_video
        )

    def _current_storyboard_md(self, storyboard: Optional[str]) -> str:
        return "**❌ Kein Storyboard gesetzt:** Bitte im Tab `📁 Projekt` auswählen." if not storyboard else f"**Storyboard:** `{storyboard}` (aus Tab 📁 Projektverwaltung)"


__all__ = ["VideoGeneratorAddon"]
