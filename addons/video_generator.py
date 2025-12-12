"""Video Generator Addon - Phase 3 of CINDERGRACE Pipeline"""
import os
import sys
import json
import shutil
from copy import deepcopy
from typing import Dict, Any, List, Tuple, Optional

import gradio as gr

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.config_manager import ConfigManager
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.workflow_registry import WorkflowRegistry
from infrastructure.model_validator import ModelValidator
from infrastructure.state_store import VideoGeneratorStateStore
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from domain.storyboard_service import StoryboardService
from domain import models as domain_models
from domain.validators import VideoGeneratorInput, StoryboardFileInput, WorkflowFileInput, SelectionFileInput
from services.selection_service import SelectionService
from services.video_service import VideoPlanBuilder, VideoGenerationService

logger = get_logger(__name__)

NO_PLAN_TEXT = "Noch kein Plan berechnet."
NO_SHOT_TEXT = "Kein Shot ausgewählt."


class VideoGeneratorAddon(BaseAddon):
    """Generate Wan 2.2 clips from selected keyframes"""

    def __init__(self):
        super().__init__(
            name="Video Generator",
            description="Use selected keyframes to drive Wan 2.2 clip generation"
        )
        self.config = ConfigManager()
        self.api = None
        self.storyboard = {}
        self.selection = {}
        self.storyboard_model: Optional[domain_models.Storyboard] = None
        self.selection_model: Optional[domain_models.SelectionSet] = None
        self.max_clip_duration = 3.0  # seconds
        self.workflow_registry = WorkflowRegistry()
        self.model_validator = ModelValidator(self.config.get_comfy_root())
        self.project_manager = ProjectStore(self.config)
        self.state_store = VideoGeneratorStateStore()
        self.selection_service = SelectionService(self.project_manager)
        self.plan_builder = VideoPlanBuilder(self.max_clip_duration)
        self.video_service = VideoGenerationService(
            project_store=self.project_manager,
            model_validator=self.model_validator,
            state_store=self.state_store,
            plan_builder=self.plan_builder,
        )

    def get_tab_name(self) -> str:
        return "🎥 Video Generator"

    def render(self) -> gr.Blocks:
        """Render the video generator UI"""
        project = self.project_manager.get_active_project(refresh=True)
        self._configure_state_store(project)
        saved_state = self.state_store.load()
        self.config.refresh()
        default_storyboard = self.config.get_current_storyboard() or saved_state.get("storyboard_file")

        selection_choices = self._get_available_selection_files()
        default_selection = saved_state.get("selection_file")
        if default_selection not in selection_choices:
            default_selection = self._get_default_selection_file()

        workflow_choices = self._get_available_workflows()
        default_workflow = saved_state.get("workflow_file")
        if default_workflow not in workflow_choices:
            default_workflow = self._get_default_workflow()

        stored_plan = saved_state.get("plan_state", [])
        summary_text, shot_choices, selected_shot, shot_md, preview_path = self._prepare_initial_plan_ui(
            stored_plan,
            saved_state.get("selected_shot")
        )
        if saved_state.get("plan_summary"):
            summary_text = saved_state["plan_summary"]

        storyboard_state = gr.State(saved_state.get("storyboard_state", {}))
        selection_state = gr.State(saved_state.get("selection_state", {}))
        plan_state = gr.State(deepcopy(stored_plan))

        storyboard_status_default = saved_state.get("storyboard_status", "**Storyboard:** Noch nicht geladen")
        storyboard_info_default = saved_state.get("storyboard_info", "{}")
        selection_status_default = saved_state.get("selection_status", "**Auswahl:** Noch keine Datei geladen")
        status_text_default = saved_state.get("status_text", "**Status:** Bereit")
        progress_text_default = saved_state.get("progress_md", "Noch keine Generierung gestartet.")
        last_video_path = saved_state.get("last_video")
        if last_video_path and not os.path.exists(last_video_path):
            last_video_path = None
        if preview_path and not os.path.exists(preview_path):
            preview_path = None

        with gr.Blocks() as interface:
            gr.Markdown("# 🎥 Wan 2.2 Video Generator - Phase 3 (Beta)")
            gr.Markdown(
                "Nutze deine ausgewählten Keyframes aus Phase 2 als Startframes für die Wan 2.2 Video-Generierung. "
                "Shots, die länger als 3 Sekunden dauern, werden automatisch in 3s-Segmente aufgeteilt. "
                "Jedes Segment übernimmt den letzten Frame des Vorgängers als neuen Startframe (`Last Frame = Start Frame`)."
            )

            with gr.Group():
                gr.Markdown("## ⚙️ Setup")
                project_status = gr.Markdown(self._project_status_md())
                refresh_project_btn = gr.Button("🔄 Projektstatus aktualisieren", size="sm")

                comfy_url = gr.Textbox(
                    value=self.config.get_comfy_url(),
                    label="ComfyUI URL",
                    placeholder="http://127.0.0.1:8188"
                )

                storyboard_md = gr.Markdown(self._current_storyboard_md(default_storyboard))
                load_storyboard_btn = gr.Button("📖 Storyboard laden (aus Projekt-Tab)", variant="secondary")

                storyboard_status = gr.Markdown(storyboard_status_default)
                storyboard_info = gr.Code(
                    label="Storyboard-Details",
                    language="json",
                    value=storyboard_info_default,
                    lines=12,
                    max_lines=20,
                    interactive=False
                )

                with gr.Row():
                    selection_dropdown = gr.Dropdown(
                        choices=selection_choices,
                        value=default_selection,
                        label="Auswahl-Datei (`selected_keyframes.json`)",
                        info="Erstellt vom Keyframe Selector",
                    )
                    refresh_selection_btn = gr.Button("🔄", size="sm")
                    load_selection_btn = gr.Button("📥 Auswahl laden", variant="secondary")

                selection_status = gr.Markdown(selection_status_default)

                with gr.Row():
                    workflow_dropdown = gr.Dropdown(
                        choices=workflow_choices,
                        value=default_workflow,
                        label="Video-Workflow",
                        info="Wan 2.2 Workflow (konfigurierbar über ⚙️ Settings)"
                    )
                    refresh_workflow_btn = gr.Button("🔄", size="sm")

                with gr.Row():
                    fps_slider = gr.Slider(
                        minimum=12,
                        maximum=30,
                        step=1,
                        value=24,
                        label="Frames pro Sekunde",
                        info="Standard 24 fps"
                    )
                    clip_duration_box = gr.Number(
                        value=self.max_clip_duration,
                        label="Clip-Länge (Sek.)",
                        precision=1,
                        interactive=False
                    )

                clip_notice = gr.Markdown(
                    f"**Hinweis:** Jeder Clip dauert **{self.max_clip_duration:.0f} Sekunden**. "
                    "Längere Shots werden automatisch in 3s-Segmente zerlegt – inklusive LastFrame→StartFrame-Kette. "
                    "Zur Sicherheit kannst du überlange Segmente später im Schnittprogramm einkürzen."
                )

            with gr.Group():
                gr.Markdown("## 🗂️ Generation Plan")
                plan_summary = gr.Markdown(summary_text)
                plan_shot_dropdown = gr.Dropdown(
                    choices=shot_choices,
                    value=selected_shot,
                    label="Shot auswählen (für Preview & manuelles Debugging)",
                    interactive=True
                )
                shot_preview_info = gr.Markdown(shot_md)
                startframe_preview = gr.Image(
                    label="Startframe Vorschau",
                    type="filepath",
                    interactive=False,
                    value=preview_path
                )

            with gr.Group():
                gr.Markdown("## 🚀 Clip-Generierung")
                with gr.Row():
                    generate_btn = gr.Button("▶️ Clips generieren", variant="primary", size="lg")
                    open_video_btn = gr.Button("📁 Ausgabeordner öffnen", variant="secondary")
                    reset_btn = gr.Button("♻️ Zurücksetzen", variant="secondary")

                status_text = gr.Markdown(status_text_default)
                progress_details = gr.Markdown(progress_text_default)
                last_video = gr.Video(label="Letzter Clip", value=last_video_path, visible=True)

            refresh_project_btn.click(
                fn=self._refresh_project_status,
                outputs=[project_status]
            )

            # Event wiring
            load_storyboard_btn.click(
                fn=self.load_storyboard_from_config,
                outputs=[
                    storyboard_status,
                    storyboard_info,
                    storyboard_state,
                    selection_status,
                    selection_state,
                    plan_summary,
                    plan_shot_dropdown,
                    plan_state,
                    shot_preview_info,
                    startframe_preview
                ]
            )

            refresh_selection_btn.click(
                fn=lambda: gr.update(choices=self._get_available_selection_files(), value=self._get_default_selection_file()),
                outputs=[selection_dropdown]
            )

            load_selection_btn.click(
                fn=self.load_selection,
                inputs=[selection_dropdown, storyboard_state],
                outputs=[
                    selection_status,
                    selection_state,
                    plan_summary,
                    plan_shot_dropdown,
                    plan_state,
                    shot_preview_info,
                    startframe_preview
                ]
            )

            refresh_workflow_btn.click(
                fn=lambda: gr.update(choices=self._get_available_workflows(), value=self._get_default_workflow()),
                outputs=[workflow_dropdown]
            )

            plan_shot_dropdown.change(
                fn=self.on_plan_shot_change,
                inputs=[plan_state, plan_shot_dropdown],
                outputs=[shot_preview_info, startframe_preview]
            )

            generate_btn.click(
                fn=self.generate_clips,
                inputs=[
                    comfy_url,
                    workflow_dropdown,
                    fps_slider,
                    storyboard_state,
                    plan_state
                ],
                outputs=[
                    status_text,
                    progress_details,
                    plan_summary,
                    plan_state,
                    last_video
                ]
            )

            reset_btn.click(
                fn=self.reset_state,
                outputs=[
                    storyboard_status,
                    storyboard_info,
                    selection_status,
                    selection_state,
                    plan_summary,
                    plan_shot_dropdown,
                    plan_state,
                    shot_preview_info,
                    startframe_preview,
                    status_text,
                    progress_details,
                    last_video
                ]
            )

            open_video_btn.click(
                fn=self.open_video_folder,
                inputs=[storyboard_state],
                outputs=[status_text]
            )

        return interface

    # -----------------------------
    # Data loading helpers
    # -----------------------------
    def load_storyboard(
        self,
        storyboard_file: Optional[str] = None
    ) -> Tuple[str, str, Dict[str, Any], str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        """Load storyboard JSON and reset dependent state.

        Refactored to use centralized StoryboardService.
        """
        try:
            # Use centralized service for loading
            storyboard_model = StoryboardService.load_from_config(
                self.config,
                filename=storyboard_file
            )

            # Apply global resolution override
            StoryboardService.apply_resolution_from_config(storyboard_model, self.config)

            # Store metadata and reference
            storyboard_file = storyboard_file or self.config.get_current_storyboard()
            storyboard_model.raw["storyboard_file"] = storyboard_file
            self.storyboard_model = storyboard_model
            self.storyboard = storyboard_model.raw

            # Prepare UI updates
            total_shots = len(storyboard_model.shots)
            status = f"**Storyboard:** ✅ {storyboard_model.project} – {total_shots} Shots geladen"
            info = json.dumps(self.storyboard, indent=2)

            # Persist state
            self._persist_state(
                storyboard_file=storyboard_file,
                storyboard_state=self.storyboard,
                storyboard_status=status,
                storyboard_info=info,
                plan_state=[],
                plan_summary=NO_PLAN_TEXT,
                selected_shot=None
            )

            return (
                status,
                info,
                self.storyboard,
                "**Auswahl:** Bitte Datei laden",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )
        except Exception as exc:
            logger.error(f"Failed to load storyboard: {exc}", exc_info=True)
            empty = "{}"
            return (
                f"**Storyboard:** ❌ Fehler beim Laden ({exc})",
                empty,
                {},
                "**Auswahl:** Bitte Datei laden",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )

    def load_storyboard_from_config(
        self
    ) -> Tuple[str, str, Dict[str, Any], str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        """Wrapper for UI button using project-tab selection.

        Refactored to use centralized StoryboardService.
        """
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            logger.warning("No storyboard selected in project tab")
            return (
                "**Storyboard:** ❌ Kein Storyboard gesetzt. Bitte im Tab '📁 Projekt' auswählen.",
                "{}",
                {},
                "**Auswahl:** Bitte Datei laden",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )
        return self.load_storyboard(storyboard_file)

    def load_selection(
        self,
        selection_file: str,
        storyboard_state: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str, gr.Dropdown, List[Dict[str, Any]], str, str]:
        """Load selected_keyframes JSON and build plan"""
        self.config.refresh()
        if not selection_file:
            selection_file = self._get_default_selection_file()
        try:
            # Validate selection file input
            SelectionFileInput(selection_file=selection_file)
        except Exception as e:
            logger.warning(f"Selection file validation failed: {e}")
            return (
                f"**Auswahl:** ❌ {str(e)}",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return (
                "**Auswahl:** ❌ Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen.",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )

        if not storyboard_state:
            return (
                "**Auswahl:** ❌ Bitte zuerst ein Storyboard laden",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )

        if not selection_file:
            return (
                "**Auswahl:** ❌ Keine Datei ausgewählt",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )

        selected_dir = self.project_manager.project_path(project, "selected")
        selection_path = os.path.join(selected_dir, selection_file)
        if not os.path.exists(selection_path):
            return (
                f"**Auswahl:** ❌ Datei nicht gefunden ({selection_file})",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )

        try:
            selection_model = storyboard_service.load_selection(selection_path)
            selection_model.raw["selection_file"] = selection_file
            self.selection_model = selection_model
            self.selection = selection_model.raw

            if not self.storyboard_model:
                return (
                    "**Auswahl:** ❌ Bitte zuerst ein Storyboard laden",
                    {},
                    NO_PLAN_TEXT,
                    gr.update(choices=[], value=None),
                    [],
                    NO_SHOT_TEXT,
                    None
                )
            # Ensure storyboard dimensions follow global resolution
            self._apply_global_resolution(self.storyboard_model)

            plan, summary, dropdown_choices, first_shot = self._build_plan_from_models()
            selection_status = f"**Auswahl:** ✅ {selection_file} – {len(selection_model.selections)} Shots"

            if not plan:
                dropdown = gr.update(choices=[], value=None)
                shot_md = NO_SHOT_TEXT
                preview = None
            else:
                dropdown = gr.update(choices=dropdown_choices, value=first_shot)
                shot_md, preview = self._format_plan_shot(plan, first_shot)

            self._persist_state(
                selection_file=selection_file,
                selection_state=self.selection,
                selection_status=selection_status,
                plan_state=plan,
                plan_summary=summary,
                selected_shot=first_shot
            )

            return (
                selection_status,
                self.selection,
                summary,
                dropdown,
                plan,
                shot_md,
                preview
            )
        except Exception as exc:
            return (
                f"**Auswahl:** ❌ Fehler beim Laden ({exc})",
                {},
                NO_PLAN_TEXT,
                gr.update(choices=[], value=None),
                [],
                NO_SHOT_TEXT,
                None
            )

    # -----------------------------
    # Plan helpers
    # -----------------------------
    def _build_plan_from_models(self) -> Tuple[List[Dict[str, Any]], str, List[str], Optional[str]]:
        """Create plan data from loaded Storyboard/Selection domain models."""
        if not self.storyboard_model or not self.selection_model:
            return [], NO_PLAN_TEXT, [], None

        generation_plan = self.plan_builder.build(self.storyboard_model, self.selection_model)
        plan_entries = generation_plan.to_dict_list()
        summary = self._format_plan_summary(plan_entries) if plan_entries else NO_PLAN_TEXT
        dropdown_choices = [
            entry.get("plan_id") or entry.get("shot_id")
            for entry in plan_entries
            if entry.get("plan_id") or entry.get("shot_id")
        ]
        dropdown_choices = [choice for choice in dropdown_choices if choice]
        first_choice = dropdown_choices[0] if dropdown_choices else None
        return plan_entries, summary, dropdown_choices, first_choice

    # -----------------------------
    # Preview helpers
    # -----------------------------
    def preview_plan_shot(
        self,
        plan_state: List[Dict[str, Any]],
        shot_id: str
    ) -> Tuple[str, str]:
        """Show info + startframe preview for a shot"""
        if not plan_state or not shot_id:
            return "Kein Shot ausgewählt.", None

        info, preview = self._format_plan_shot(plan_state, shot_id)
        return info, preview

    def on_plan_shot_change(
        self,
        plan_state: List[Dict[str, Any]],
        shot_id: str
    ) -> Tuple[str, str]:
        info, preview = self.preview_plan_shot(plan_state, shot_id)
        if shot_id:
            self._persist_state(selected_shot=shot_id)
        return info, preview

    # -----------------------------
    # Generation
    # -----------------------------
    def generate_clips(
        self,
        comfy_url: str,
        workflow_file: str,
        fps: int,
        storyboard_state: Dict[str, Any],
        plan_state: List[Dict[str, Any]]
    ) -> Tuple[str, str, str, List[Dict[str, Any]], str]:
        """Generate Wan video clips for all ready shots"""
        try:
            # Validate inputs with Pydantic
            validated_inputs = VideoGeneratorInput(
                fps=int(fps),
                max_segment_seconds=self.max_clip_duration
            )
            WorkflowFileInput(workflow_file=workflow_file)

            logger.info(f"Starting video generation: {validated_inputs.fps} fps, {validated_inputs.max_segment_seconds}s segments")

        except Exception as e:
            logger.error(f"Video generation validation failed: {e}")
            return self._error_response(
                f"**Status:** ❌ Validierungsfehler: {str(e)}",
                "Ungültige Eingabeparameter",
                plan_state
            )

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return self._error_response(
                "**Status:** ❌ Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen.",
                "Keine Daten",
                plan_state
            )

        self._configure_state_store(project)
        # Apply global resolution override before plan/generation
        if self.storyboard_model:
            self._apply_global_resolution(self.storyboard_model)
            if self.storyboard_model.raw:
                # keep raw in sync for state persistence
                self.storyboard = self.storyboard_model.raw

        if not storyboard_state:
            return self._error_response("**Status:** ❌ Bitte zuerst ein Storyboard laden", "Keine Daten", plan_state)

        if not plan_state:
            return self._error_response("**Status:** ❌ Kein Generierungs-Plan verfügbar", "Keine Daten", plan_state)

        if not workflow_file or workflow_file.startswith("No workflows"):
            return self._error_response("**Status:** ❌ Kein Workflow ausgewählt", "Keine Daten", plan_state)

        ready_entries = [entry for entry in plan_state if entry.get("ready")]
        if not ready_entries:
            missing = sorted({entry.get("shot_id") for entry in plan_state if entry.get("start_frame_source") == "missing"})
            missing_hint = ", ".join(missing) if missing else "keine Startframes gefunden"
            return self._error_response(
                f"**Status:** ❌ Kein Shot mit gültigem Startframe (fehlend: {missing_hint})",
                "Bitte im Selector exportieren oder manuell Startframes ablegen.",
                plan_state
            )

        workflow_path = os.path.join(self.config.get_workflow_dir(), workflow_file)
        if not os.path.exists(workflow_path):
            return self._error_response(f"**Status:** ❌ Workflow nicht gefunden ({workflow_file})", "Keine Daten", plan_state)

        self.api = ComfyUIAPI(comfy_url)
        conn = self.api.test_connection()
        if not conn.get("connected"):
            return self._error_response(
                f"**Status:** ❌ Verbindung fehlgeschlagen ({conn.get('error')})",
                "Keine Daten",
                plan_state
            )

        # Load workflow template once
        try:
            workflow_template = self.api.load_workflow(workflow_path)
        except Exception as exc:
            return self._error_response(
                f"**Status:** ❌ Workflow konnte nicht geladen werden ({exc})",
                "Keine Daten",
                plan_state
            )

        missing_models = self.model_validator.find_missing(workflow_template) if self.model_validator else []
        if missing_models:
            missing_md = self._format_missing_models(missing_models)
            return self._error_response(
                f"**Status:** ❌ Modelle fehlen ({len(missing_models)})",
                missing_md,
                plan_state
            )

        ffmpeg_missing = shutil.which("ffmpeg") is None
        preflight_notice = ""
        if ffmpeg_missing:
            preflight_notice = "\n⚠️ ffmpeg nicht gefunden – LastFrame-Kette wird übersprungen, Segment-Verlängerung startet ohne Cache."

        updated_plan, logs, last_video_path = self.video_service.run_generation(
            plan_state=plan_state,
            workflow_template=workflow_template,
            fps=validated_inputs.fps,
            project=project,
            comfy_api=self.api
        )

        progress_md = "### Fortschritt\n" + "\n".join(logs)
        if preflight_notice:
            progress_md = preflight_notice + "\n\n" + progress_md
        summary = self._format_plan_summary(updated_plan)

        status = "**Status:** ✅ Clips generiert (siehe Log)" if last_video_path else "**Status:** ⚠️ Siehe Log für Details"
        self._persist_state(
            plan_state=updated_plan,
            plan_summary=summary,
            status_text=status,
            progress_md=progress_md,
            last_video=last_video_path,
            workflow_file=workflow_file
        )
        return status, progress_md, summary, updated_plan, last_video_path

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _prepare_initial_plan_ui(
        self,
        plan: List[Dict[str, Any]],
        selected_shot: Optional[str]
    ) -> Tuple[str, List[str], Optional[str], str, Optional[str]]:
        if not plan:
            return NO_PLAN_TEXT, [], None, NO_SHOT_TEXT, None

        choices = [
            entry.get("plan_id") or entry.get("shot_id")
            for entry in plan
            if entry.get("plan_id") or entry.get("shot_id")
        ]
        choices = [shot for shot in choices if shot]
        default_shot = selected_shot if selected_shot in choices else (choices[0] if choices else None)
        summary = self._format_plan_summary(plan)
        if default_shot:
            shot_md, preview = self._format_plan_shot(plan, default_shot)
        else:
            shot_md, preview = NO_SHOT_TEXT, None
        return summary, choices, default_shot, shot_md, preview

    def _format_plan_summary(
        self,
        plan: List[Dict[str, Any]],
        clamped: int = None,
        missing: List[str] = None,
        needs_extension: int = None
    ) -> str:
        """Generate plan overview markdown"""
        total = len(plan)
        unique_shots = len({entry.get("shot_id") for entry in plan})
        ready = len([entry for entry in plan if entry.get("ready")])
        completed = len([entry for entry in plan if entry.get("status") == "completed"])
        missing_list = missing if missing is not None else sorted({
            entry["shot_id"] for entry in plan if entry.get("start_frame_source") == "missing"
        })
        clamped_total = clamped if clamped is not None else len({
            entry["shot_id"] for entry in plan if entry.get("segment_total", 1) > 1
        })
        waiting_segments = needs_extension if needs_extension is not None else len([
            entry for entry in plan if entry.get("start_frame_source") == "chain_wait"
        ])

        md = [
            "### Plan-Übersicht",
            f"- **Storyboard-Shots:** {unique_shots}",
            f"- **Clips (3s-Segmente):** {total}",
            f"- **Bereit:** {ready}",
            f"- **Abgeschlossen:** {completed}",
            f"- **Shots >3s (segmentiert):** {clamped_total}",
            f"- **Wartet auf LastFrame-Start:** {waiting_segments}",
            f"- **Mit Startframe-Problemen:** {len(missing_list)}"
        ]

        if missing_list:
            md.append(f"- ❗ Fehlende Shots: {', '.join(missing_list)}")

        return "\n".join(md)

    def _format_missing_models(self, missing: List[str]) -> str:
        lines = ["### Fehlende Modelle",
                 "- Die folgenden Dateien wurden im Workflow referenziert, aber nicht in deinem ComfyUI/models/ Ordner gefunden:"]
        for name in missing:
            lines.append(f"  - `{name}`")
        lines.append("")
        lines.append("Bitte installiere die Modelle oder passe den Workflow über ⚙️ Settings an.")
        return "\n".join(lines)

    def _format_plan_shot(
        self,
        plan: List[Dict[str, Any]],
        plan_entry_id: str
    ) -> Tuple[str, str]:
        """Return markdown + preview path for a plan entry"""
        entry = next(
            (
                item for item in plan
                if (item.get("plan_id") or item.get("shot_id")) == plan_entry_id
            ),
            None
        )
        if not entry:
            return "Shot nicht gefunden.", None

        lines = [
            f"### Shot {entry['shot_id']} – {entry['filename_base']}",
            f"- **Prompt:** {entry['prompt'][:160]}{'…' if len(entry['prompt']) > 160 else ''}",
            f"- **Auflösung:** {entry['width']}×{entry['height']}",
            f"- **Storyboard-Dauer:** {entry['duration']}s",
            f"- **Generierte Dauer:** {entry['effective_duration']}s",
            f"- **Segment:** {entry.get('segment_index', 1)}/{entry.get('segment_total', 1)} "
              f"(Ziel: {entry.get('segment_requested_duration', entry.get('effective_duration'))}s)",
            f"- **Variante:** {entry.get('selected_file', 'n/a')}",
            f"- **Status:** {entry.get('status', 'pending')}"
        ]

        motion = entry.get("wan_motion")
        if motion:
            motion_desc = motion.get("notes") or motion.get("type")
            lines.append(f"- **Wan Motion:** {motion.get('type', 'n/a')} (Strength {motion.get('strength', '-')})")
            if motion_desc and motion_desc != motion.get("type"):
                lines.append(f"  - {motion_desc}")

        if entry.get("segment_total", 1) > 1 and entry.get("segment_index", 1) == 1:
            lines.append("- 🔁 Dieser Shot wird in 3s-Segmente verlängert.")
        if entry.get("start_frame_source") == "chain_wait":
            lines.append("- ⏳ Wartet auf LastFrame als Startframe.")
        elif not entry.get("ready"):
            lines.append("- ❌ Kein gültiger Startframe gefunden.")

        preview_path = entry.get("start_frame") if entry.get("ready") else None
        return "\n".join(lines), preview_path


    def open_video_folder(self, storyboard_state: Dict[str, Any]) -> str:
        """Open the video output folder"""
        project_data = self.project_manager.get_active_project(refresh=True)
        if not project_data:
            return "**Status:** ❌ Kein aktives Projekt. Bitte im Tab '📁 Projekt' auswählen."
        dest_dir = self.project_manager.ensure_dir(project_data, "video")
        os.makedirs(dest_dir, exist_ok=True)
        os.system(f'xdg-open "{dest_dir}"')
        return f"**Status:** 📁 Video-Ordner geöffnet ({dest_dir})"

    # -----------------------------
    # Dropdown helpers
    # -----------------------------
    def _get_available_storyboards(self) -> List[str]:
        config_dir = self.config.config_dir
        if not os.path.exists(config_dir):
            return []
        return [
            f for f in os.listdir(config_dir)
            if f.endswith(".json") and "storyboard" in f.lower()
        ]

    def _get_default_storyboard(self) -> str:
        storyboards = self._get_available_storyboards()
        return storyboards[0] if storyboards else None

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
        if not self.state_store:
            return
        self.state_store.update(**kwargs)

    def _configure_state_store(self, project: Optional[Dict[str, Any]]):
        """Update persistence path depending on selected project."""
        if not self.state_store:
            return
        state_path = None
        if project:
            state_path = os.path.join(project["path"], "video", "_state.json")
        self.state_store.configure(state_path)

    def _project_status_md(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Kein aktives Projekt:** Bitte im Tab `📁 Projekt` anlegen oder auswählen."
        return (
            f"**Aktives Projekt:** {project.get('name')} (`{project.get('slug')}`)\n"
            f"- Pfad: `{project.get('path')}`"
        )

    def _refresh_project_status(self) -> str:
        project = self.project_manager.get_active_project(refresh=True)
        self._configure_state_store(project)
        return self._project_status_md()

    def _error_response(
        self,
        status_message: str,
        progress_message: str,
        plan_state: List[Dict[str, Any]]
    ):
        summary = self._format_plan_summary(plan_state) if plan_state else NO_PLAN_TEXT
        self._persist_state(status_text=status_message, progress_md=progress_message)
        return status_message, progress_message, summary, plan_state, None

    def reset_state(
        self
    ) -> Tuple[
        str,  # storyboard_status
        str,  # storyboard_info
        str,  # selection_status
        Dict[str, Any],  # selection_state
        str,  # plan_summary
        gr.Dropdown,  # plan_shot_dropdown update
        List[Dict[str, Any]],  # plan_state
        str,  # shot_preview_info
        str,  # startframe_preview (as filepath)
        str,  # status_text
        str,  # progress_details
        None  # last_video
    ]:
        """Reset video generator UI/state to initial values."""
        self._persist_state(
            storyboard_file=None,
            storyboard_state={},
            storyboard_status="**Storyboard:** Noch nicht geladen",
            storyboard_info="{}",
            selection_file=None,
            selection_state={},
            selection_status="**Auswahl:** Noch keine Datei geladen",
            plan_state=[],
            plan_summary=NO_PLAN_TEXT,
            selected_shot=None,
            status_text="**Status:** Bereit",
            progress_md="Noch keine Generierung gestartet.",
            last_video=None,
        )
        return (
            "**Storyboard:** Noch nicht geladen",
            "{}",
            "**Auswahl:** Noch keine Datei geladen",
            {},
            NO_PLAN_TEXT,
            gr.update(choices=[], value=None),
            [],
            NO_SHOT_TEXT,
            None,
            "**Status:** Bereit",
            "Noch keine Generierung gestartet.",
            None
        )

    # Removed: _apply_global_resolution() - now using StoryboardService.apply_resolution_from_config()

    def _current_storyboard_md(self, storyboard: Optional[str]) -> str:
        if not storyboard:
            return "**❌ Kein Storyboard gesetzt:** Bitte im Tab `📁 Projekt` auswählen."
        return f"**Storyboard:** `{storyboard}` (aus Tab 📁 Projektverwaltung)"


__all__ = ["VideoGeneratorAddon"]
