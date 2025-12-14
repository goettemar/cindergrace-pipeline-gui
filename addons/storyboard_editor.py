import os
import sys
import json
from typing import Optional, List, Dict, Any, Tuple
import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from infrastructure.error_handler import handle_errors
from domain.storyboard_service import StoryboardService
from domain import models as domain_models
from services.storyboard_editor_service import StoryboardEditorService

logger = get_logger(__name__)


class StoryboardEditorAddon(BaseAddon):
    def __init__(self):
        super().__init__(
            name="Storyboard Editor",
            description="Create and edit storyboards for the active project"
        )
        self.config = ConfigManager()
        self.project_store = ProjectStore(self.config)
        self.editor_service = StoryboardEditorService()
        self.current_storyboard: Optional[domain_models.Storyboard] = None

    def get_tab_name(self) -> str:
        return "📝 Storyboard"

    def _auto_load_default_storyboard(self) -> dict:
        """Auto-load current storyboard on tab open and return initial UI data."""
        default_data = {
            "storyboard_info": "**Storyboard:** ❌ No storyboard selected - select one in Tab 📁 Projekt",
            "status": "",
            "shots": [],
            "timeline": "**Timeline:** 0 shots, 0.0s total"
        }

        try:
            project = self.project_store.get_active_project(refresh=True)
            if not project:
                default_data["storyboard_info"] = "**Storyboard:** ❌ No active project - create one in Tab 📁 Projekt"
                return default_data

            # Load the CURRENT storyboard (from settings)
            current_sb_path = self.config.get("current_storyboard")
            if current_sb_path and os.path.exists(current_sb_path):
                self.current_storyboard = StoryboardService.load_from_file(current_sb_path)
                shot_list = self._storyboard_to_dataframe()
                current_sb_name = os.path.basename(current_sb_path)
                default_data["storyboard_info"] = f"**Storyboard:** {current_sb_path}\n\n*(aus Tab 📁 Projektverwaltung)*"
                default_data["status"] = f"✅ Loaded {len(shot_list)} shots"
                default_data["shots"] = shot_list
                default_data["timeline"] = self._get_timeline_info()
                logger.info(f"Auto-loaded current storyboard: {current_sb_name} with {len(shot_list)} shots")
            else:
                default_data["storyboard_info"] = "**Storyboard:** ❌ No storyboard selected - select one in Tab 📁 Projekt"
                default_data["status"] = ""

        except Exception as e:
            logger.error(f"Error auto-loading storyboard: {e}", exc_info=True)
            default_data["storyboard_info"] = "**Storyboard:** ⚠️ Error loading storyboard"
            default_data["status"] = f"Error: {str(e)}"

        return default_data

    def load_shot_from_row_click(self, evt: gr.SelectData) -> Tuple:
        """Handle row click to load shot into editor tabs."""
        default_values = [
            0,  # selected_shot_index
            "", "", "", "", 3.0, "static",  # shot_id, filename_base, description, prompt, duration, camera_movement
            "", "",  # character, negative_prompt
            "none", 0.5, "",  # wan_motion_type, wan_motion_strength, wan_motion_notes
            -1, 7.0, 20,  # seed, cfg_scale, steps
            "❌ No storyboard loaded"
        ]

        if not self.current_storyboard:
            return tuple(default_values)

        # evt.index is the row index clicked (can be list [row, col] or tuple (row, col))
        if isinstance(evt.index, (list, tuple)):
            row_index = evt.index[0]
        else:
            row_index = evt.index

        # Ensure row_index is an integer
        row_index = int(row_index)

        if row_index < 0 or row_index >= len(self.current_storyboard.shots):
            default_values[-1] = f"❌ Invalid index {row_index}"
            return tuple(default_values)

        shot = self.current_storyboard.shots[row_index]

        # Extract wan_motion data
        wan_motion = shot.wan_motion if hasattr(shot, 'wan_motion') and shot.wan_motion else None
        wan_type = wan_motion.type if wan_motion and hasattr(wan_motion, 'type') else shot.raw.get("wan_motion", {}).get("type", "none")
        wan_strength = wan_motion.strength if wan_motion and hasattr(wan_motion, 'strength') else shot.raw.get("wan_motion", {}).get("strength", 0.5)
        wan_notes = wan_motion.notes if wan_motion and hasattr(wan_motion, 'notes') else shot.raw.get("wan_motion", {}).get("notes", "")

        return (
            row_index,  # selected_shot_index
            shot.shot_id,
            shot.filename_base,
            shot.raw.get("description", ""),
            shot.prompt,
            shot.duration,
            shot.raw.get("camera_movement", "static"),
            shot.raw.get("character", ""),
            shot.raw.get("negative_prompt", ""),
            wan_type or "none",
            float(wan_strength) if wan_strength else 0.5,
            wan_notes or "",
            int(shot.raw.get("seed", -1)),
            float(shot.raw.get("cfg_scale", 7.0)),
            int(shot.raw.get("steps", 20)),
            f"✅ Loaded shot {shot.shot_id} from row click"
        )

    def _get_custom_css(self) -> str:
        """Custom CSS for improved UX: 100% width, sticky action bar, scrollable panes."""
        return """
        /* Full width layout */
        .gradio-container {
            max-width: 100% !important;
            width: 100% !important;
        }

        /* Master-Detail Layout */
        #master_detail_container {
            height: calc(100vh - 250px);
            min-height: 650px;
            display: flex;
            overflow: hidden;
        }

        /* Left Pane: Fixed scrollable area (30% width) */
        #left_pane {
            flex: 0 0 30%;
            max-width: 400px;
            height: 100%;
            overflow-y: auto;
            overflow-x: hidden;
            padding-right: 15px;
        }

        /* Right Pane: Fixed scrollable area, no horizontal scroll (70% width) */
        #right_pane {
            flex: 1;
            height: 100%;
            overflow-y: auto;
            overflow-x: hidden;
            padding-left: 20px;
            padding-right: 10px;
            border-left: 2px solid #e0e0e0;
            min-width: 0;
        }

        /* Ensure all child elements respect container width */
        #right_pane * {
            max-width: 100%;
            box-sizing: border-box;
        }

        /* Action Buttons at top of editor */
        #action_buttons_top {
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e0e0e0;
        }

        #action_buttons_top button {
            font-size: 15px !important;
            padding: 10px 20px !important;
            font-weight: 500;
        }

        /* Shot List scrollable */
        #shots_list {
            max-height: 400px;
            overflow-y: auto;
        }

        /* Tab styling - ensure tabs are visible */
        #editor_tabs {
            margin-top: 10px;
            width: 100%;
        }

        /* Ensure tab content is visible and scrollable */
        #right_pane .tabitem {
            padding: 15px 5px;
            max-height: none !important;
        }

        /* Setup accordion */
        #setup_accordion {
            margin-bottom: 15px;
        }

        /* Ensure textareas and inputs don't overflow */
        #right_pane textarea,
        #right_pane input,
        #right_pane .gr-box {
            max-width: 100% !important;
            width: 100% !important;
        }

        /* Ensure form rows wrap properly */
        #right_pane .gr-form {
            width: 100%;
        }

        /* Better spacing for two-column layouts */
        #right_pane .gr-row {
            gap: 10px;
        }
        """

    def render(self) -> gr.Blocks:
        # Auto-load default storyboard if set
        initial_data = self._auto_load_default_storyboard()

        with gr.Blocks() as interface:
            # Inject custom CSS via HTML component (Gradio 6.0 compatible)
            gr.HTML(f"<style>{self._get_custom_css()}</style>")

            gr.Markdown("# 📝 Storyboard Editor")

            with gr.Row():
                storyboard_info = gr.Markdown(initial_data["storyboard_info"])
                refresh_btn = gr.Button("↻ Refresh", scale=0, min_width=60)

            # Master-Detail Layout: Left (Setup + List), Right (Editor)
            with gr.Row(elem_id="master_detail_container"):
                # LEFT PANE: Setup + Shots List (30% width)
                with gr.Column(scale=3, elem_id="left_pane"):
                    # Setup Section (Collapsible)
                    with gr.Accordion("📂 Setup: New / Load / Set Default", open=False, elem_id="setup_accordion"):
                        storyboard_file = gr.Dropdown(
                            label="Storyboard File",
                            choices=[],
                            info="Storyboards in project folder"
                        )
                        with gr.Row():
                            refresh_files_btn = gr.Button("↻", scale=0, min_width=60)
                            load_btn = gr.Button("📂 Load", variant="secondary", scale=1)

                        new_storyboard_name = gr.Textbox(
                            label="New Storyboard Name",
                            placeholder="storyboard_main",
                            info="Name for new storyboard (without .json)"
                        )
                        new_btn = gr.Button("🆕 New Storyboard", variant="primary")

                        gr.Markdown("---")
                        with gr.Row():
                            save_btn = gr.Button("💾 Save", variant="primary", scale=2)
                            set_default_btn = gr.Button("⭐ Set Default", variant="secondary", scale=1)

                    status_box = gr.Markdown(initial_data["status"])

                    # Shots List (Always visible, scrollable)
                    gr.Markdown("### 🎬 Shots")
                    gr.Markdown("*Click on a row to load the shot into the editor*", elem_classes=["info-text"])
                    shot_list = gr.Dataframe(
                        headers=["#", "ID", "Filename", "Description", "Duration (s)"],
                        datatype=["number", "str", "str", "str", "number"],
                        label="Shot List (click row to edit)",
                        interactive=False,
                        row_count=10,
                        elem_id="shots_list",
                        value=initial_data["shots"]
                    )
                    timeline_info = gr.Markdown(initial_data["timeline"])
                    with gr.Row():
                        add_shot_btn = gr.Button("➕ Add Shot", variant="primary")
                        delete_shot_btn = gr.Button("🗑️ Delete Selected", variant="stop")

                # RIGHT PANE: Shot Editor with Tabs (70% width)
                with gr.Column(scale=7, elem_id="right_pane"):
                    # Action Buttons (always visible at top)
                    gr.Markdown("### Shot Editor")
                    with gr.Row(elem_id="action_buttons_top"):
                        load_shot_btn = gr.Button("📋 Load Selected Shot", variant="secondary", scale=1)
                        update_shot_btn = gr.Button("💾 Update & Save Shot", variant="primary", scale=2)

                    # Editor Tabs for Progressive Disclosure
                    with gr.Tabs(elem_id="editor_tabs", selected=0):
                        # TAB 1: Basics
                        with gr.Tab("📌 Basics"):
                            selected_shot_index = gr.Number(
                                label="Shot Index (0 = first shot)",
                                value=0,
                                minimum=0,
                                precision=0,
                                info="Select shot by row number from list above"
                            )
                            with gr.Row():
                                shot_id = gr.Textbox(
                                    label="Shot ID",
                                    placeholder="Auto-generated (001, 002...)",
                                    info="Leave empty for auto-increment"
                                )
                                filename_base = gr.Textbox(
                                    label="Filename Base",
                                    placeholder="cathedral-interior",
                                    info="No spaces or special chars"
                                )
                            description = gr.Textbox(
                                label="Description",
                                placeholder="Opening shot of cathedral interior",
                                info="Human-readable description"
                            )
                            with gr.Row():
                                duration = gr.Number(
                                    label="Duration (seconds)",
                                    value=3.0,
                                    minimum=0.5,
                                    maximum=30.0,
                                    step=0.5,
                                    precision=1,
                                    info="Video clip duration"
                                )
                                character = gr.Textbox(
                                    label="Character",
                                    placeholder="Protagonist",
                                    info="Character name (optional)"
                                )

                        # TAB 2: Prompts
                        with gr.Tab("💬 Prompts"):
                            prompt = gr.TextArea(
                                label="Prompt",
                                placeholder="Gothic cathedral interior, dramatic lighting, stained glass windows...",
                                lines=6,
                                info="AI generation prompt (required)"
                            )
                            negative_prompt = gr.TextArea(
                                label="Negative Prompt",
                                placeholder="blurry, low quality, distorted...",
                                lines=4,
                                info="What to avoid in generation (optional)"
                            )

                        # TAB 3: Camera / Motion
                        with gr.Tab("🎥 Camera / Motion"):
                            camera_movement = gr.Dropdown(
                                label="Camera Movement",
                                choices=["static", "slow_push", "dolly", "pan", "tilt", "zoom", "crane"],
                                value="static",
                                info="Camera animation type"
                            )
                            gr.Markdown("#### Wan Motion Settings")
                            with gr.Row():
                                wan_motion_type = gr.Dropdown(
                                    label="Motion Type",
                                    choices=["none", "macro_dolly", "macro_pan", "macro_tilt", "macro_zoom", "macro_orbit"],
                                    value="none",
                                    info="Wan 2.2 motion type (optional)"
                                )
                                wan_motion_strength = gr.Slider(
                                    label="Motion Strength",
                                    minimum=0.0,
                                    maximum=1.0,
                                    value=0.5,
                                    step=0.1,
                                    info="Motion intensity (0-1)"
                                )
                            wan_motion_notes = gr.Textbox(
                                label="Motion Notes",
                                placeholder="Slow forward dolly movement...",
                                info="Additional notes for motion (optional)"
                            )

                        # TAB 4: Render / Output
                        with gr.Tab("⚙️ Render / Output"):
                            gr.Markdown("*Note: Width/Height are inherited from project settings*")
                            with gr.Row():
                                seed = gr.Number(
                                    label="Seed",
                                    value=-1,
                                    precision=0,
                                    info="Random seed (-1 for random)"
                                )
                                cfg_scale = gr.Number(
                                    label="CFG Scale",
                                    value=7.0,
                                    minimum=1.0,
                                    maximum=30.0,
                                    step=0.5,
                                    precision=1,
                                    info="Classifier-free guidance scale"
                                )
                            steps = gr.Number(
                                label="Steps",
                                value=20,
                                minimum=1,
                                maximum=150,
                                precision=0,
                                info="Sampling steps"
                            )

            # JSON Preview (collapsed by default)
            with gr.Accordion("📄 JSON Preview", open=False):
                json_preview = gr.Code(
                    label="Storyboard JSON",
                    language="json",
                    lines=15,
                    interactive=False
                )

            refresh_btn.click(
                fn=self._refresh_storyboard_info,
                outputs=[storyboard_info]
            )
            refresh_files_btn.click(
                fn=self._refresh_storyboard_files,
                outputs=[storyboard_file]
            )
            new_btn.click(
                fn=self.create_new_storyboard,
                inputs=[new_storyboard_name],
                outputs=[storyboard_info, status_box, shot_list, timeline_info, json_preview, storyboard_file]
            )
            load_btn.click(
                fn=self.load_storyboard,
                inputs=[storyboard_file],
                outputs=[storyboard_info, status_box, shot_list, timeline_info, json_preview]
            )
            save_btn.click(
                fn=self.save_storyboard,
                inputs=[storyboard_file],
                outputs=[status_box, storyboard_file]
            )
            set_default_btn.click(
                fn=self.set_as_default,
                inputs=[storyboard_file],
                outputs=[status_box, storyboard_info]
            )
            add_shot_btn.click(
                fn=self.add_shot,
                inputs=[
                    shot_id, filename_base, description, prompt, duration, camera_movement,
                    character, negative_prompt,
                    wan_motion_type, wan_motion_strength, wan_motion_notes,
                    seed, cfg_scale, steps
                ],
                outputs=[status_box, shot_list, timeline_info, json_preview]
            )
            update_shot_btn.click(
                fn=self.update_shot,
                inputs=[
                    selected_shot_index, shot_id, filename_base, description, prompt, duration, camera_movement,
                    character, negative_prompt,
                    wan_motion_type, wan_motion_strength, wan_motion_notes,
                    seed, cfg_scale, steps
                ],
                outputs=[status_box, shot_list, timeline_info, json_preview]
            )
            delete_shot_btn.click(
                fn=self.delete_shot,
                inputs=[selected_shot_index],
                outputs=[status_box, shot_list, timeline_info, json_preview]
            )
            load_shot_btn.click(
                fn=self.load_shot_to_editor,
                inputs=[selected_shot_index],
                outputs=[
                    shot_id, filename_base, description, prompt, duration, camera_movement,
                    character, negative_prompt,
                    wan_motion_type, wan_motion_strength, wan_motion_notes,
                    seed, cfg_scale, steps,
                    status_box
                ]
            )

            # Auto-load shot when clicking on a row in the dataframe
            shot_list.select(
                fn=self.load_shot_from_row_click,
                inputs=[],
                outputs=[
                    selected_shot_index,
                    shot_id, filename_base, description, prompt, duration, camera_movement,
                    character, negative_prompt,
                    wan_motion_type, wan_motion_strength, wan_motion_notes,
                    seed, cfg_scale, steps,
                    status_box
                ]
            )
        return interface

    @handle_errors("Failed to refresh storyboard info", return_tuple=False)
    def _refresh_storyboard_info(self) -> str:
        """Refresh the storyboard info display at the top."""
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return "**Storyboard:** ❌ No active project - create one in Tab 📁 Projekt"

        current_sb_path = self.config.get("current_storyboard")
        if current_sb_path and os.path.exists(current_sb_path):
            return f"**Storyboard:** {current_sb_path}\n\n*(aus Tab 📁 Projektverwaltung)*"
        else:
            return "**Storyboard:** ❌ No storyboard selected - select one in Tab 📁 Projekt"

    @handle_errors("Failed to refresh files", return_tuple=False)
    def _refresh_storyboard_files(self) -> gr.Dropdown:
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return gr.Dropdown(choices=[], value=None)
        storyboard_dir = self.project_store.get_project_storyboard_dir(project)
        if not os.path.exists(storyboard_dir):
            return gr.Dropdown(choices=[], value=None)
        files = [f for f in os.listdir(storyboard_dir) if f.endswith(".json")]
        default_sb_path = project.get("default_storyboard")
        # Extract filename from path
        default_sb = os.path.basename(default_sb_path) if default_sb_path else None
        return gr.Dropdown(choices=files, value=default_sb if default_sb in files else None)

    @handle_errors("Failed to create storyboard")
    def create_new_storyboard(self, storyboard_name: str) -> Tuple:
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return ("**Storyboard:** ❌ No active project", "Create project in 📁 Projekt tab first",
                    gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}", gr.Dropdown())
        if not storyboard_name:
            storyboard_name = "storyboard_main"
        if not storyboard_name.endswith(".json"):
            storyboard_name += ".json"

        self.current_storyboard = self.editor_service.create_new_storyboard(project["name"])
        storyboard_dir = self.project_store.ensure_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, storyboard_name)
        StoryboardService.save_storyboard(self.current_storyboard, file_path)
        # Save full path to project config (for Tab Projekt compatibility)
        self.project_store.set_project_storyboard(project, file_path, set_as_default=True)

        # Update current_storyboard in settings
        self.config.set("current_storyboard", file_path)

        shot_list = self._storyboard_to_dataframe()
        timeline = self._get_timeline_info()
        json_str = self._storyboard_to_json_str()
        files = self._refresh_storyboard_files()
        storyboard_info = f"**Storyboard:** {file_path}\n\n*(aus Tab 📁 Projektverwaltung)*"
        status = f"✅ Created new storyboard: {storyboard_name}"
        return (storyboard_info, status, gr.update(value=shot_list), timeline, json_str, files)

    @handle_errors("Failed to load storyboard")
    def load_storyboard(self, filename: str) -> Tuple:
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return ("**Storyboard:** ❌ No active project", "Select project in 📁 Projekt tab",
                    gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}")
        if not filename:
            return ("**Storyboard:** ❌ No file selected", "Select a storyboard file above",
                    gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}")
        storyboard_dir = self.project_store.ensure_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, filename)
        self.current_storyboard = StoryboardService.load_from_file(file_path)

        # Update current_storyboard in settings (like other tabs do)
        self.config.set("current_storyboard", file_path)

        shot_list = self._storyboard_to_dataframe()
        timeline = self._get_timeline_info()
        json_str = self._storyboard_to_json_str()
        logger.info(f"Loaded storyboard with {len(shot_list)} shots")
        storyboard_info = f"**Storyboard:** {file_path}\n\n*(aus Tab 📁 Projektverwaltung)*"
        status = f"✅ Loaded {len(shot_list)} shots from {filename}"
        return (storyboard_info, status, gr.update(value=shot_list), timeline, json_str)

    @handle_errors("Failed to save storyboard")
    def save_storyboard(self, storyboard_filename: str) -> Tuple[str, gr.Dropdown]:
        if not self.current_storyboard:
            return "❌ No storyboard loaded", gr.Dropdown()
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return "❌ No active project", gr.Dropdown()

        # Update storyboard project name to match active project
        if self.current_storyboard.project != project["name"]:
            self.current_storyboard.raw["project"] = project["name"]
            self.current_storyboard.project = project["name"]

        if not storyboard_filename:
            storyboard_filename = "storyboard_main.json"
        if not storyboard_filename.endswith(".json"):
            storyboard_filename += ".json"
        storyboard_dir = self.project_store.ensure_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, storyboard_filename)
        StoryboardService.save_storyboard(self.current_storyboard, file_path)
        # Save full path to project config (for Tab Projekt compatibility)
        self.project_store.set_project_storyboard(project, file_path, set_as_default=False)
        files = self._refresh_storyboard_files()
        return f"✅ Saved: {storyboard_filename}", files

    @handle_errors("Failed to set default")
    def set_as_default(self, storyboard_filename: str) -> Tuple[str, str]:
        if not storyboard_filename:
            return "❌ No file selected", self._refresh_storyboard_info()
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return "❌ No active project", "**Storyboard:** ❌ No active project"
        # Construct full path for Tab Projekt compatibility
        storyboard_dir = self.project_store.get_project_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, storyboard_filename)
        self.project_store.set_project_storyboard(project, file_path, set_as_default=True)
        storyboard_info = self._refresh_storyboard_info()
        return f"✅ Set {storyboard_filename} as default", storyboard_info

    @handle_errors("Failed to add shot")
    def add_shot(
        self, shot_id, filename_base, description, prompt, duration, camera_movement,
        character, negative_prompt,
        wan_motion_type, wan_motion_strength, wan_motion_notes,
        seed, cfg_scale, steps
    ):
        if not self.current_storyboard:
            return "❌ Error: No storyboard loaded", gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}"
        if not prompt:
            return "❌ Error: Prompt is required", gr.update(value=self._storyboard_to_dataframe()), self._get_timeline_info(), self._storyboard_to_json_str()
        if not filename_base:
            return "❌ Error: Filename Base is required", gr.update(value=self._storyboard_to_dataframe()), self._get_timeline_info(), self._storyboard_to_json_str()
        if not description:
            return "❌ Error: Description is required", gr.update(value=self._storyboard_to_dataframe()), self._get_timeline_info(), self._storyboard_to_json_str()
        if not shot_id:
            shot_id = self.editor_service.get_next_shot_id(self.current_storyboard)

        # Prepare wan_motion data
        wan_motion_data = None
        if wan_motion_type and wan_motion_type != "none":
            wan_motion_data = {
                "type": wan_motion_type,
                "strength": float(wan_motion_strength) if wan_motion_strength else 0.5,
                "notes": wan_motion_notes or ""
            }

        self.current_storyboard = self.editor_service.add_shot(
            self.current_storyboard,
            shot_id=shot_id,
            filename_base=filename_base or f"shot_{shot_id}",
            description=description,
            prompt=prompt,
            duration=float(duration),
            camera_movement=camera_movement,
            character=character or "",
            negative_prompt=negative_prompt or "",
            wan_motion=wan_motion_data,
            width=1024,  # Default, will be overridden by project settings
            height=576,  # Default, will be overridden by project settings
            seed=int(seed) if seed else -1,
            cfg_scale=float(cfg_scale) if cfg_scale else 7.0,
            steps=int(steps) if steps else 20,
        )
        shot_list = self._storyboard_to_dataframe()
        timeline = self._get_timeline_info()
        json_str = self._storyboard_to_json_str()
        return f"✅ Added shot {shot_id}", gr.update(value=shot_list), timeline, json_str

    @handle_errors("Failed to update shot")
    def update_shot(
        self, index, shot_id, filename_base, description, prompt, duration, camera_movement,
        character, negative_prompt,
        wan_motion_type, wan_motion_strength, wan_motion_notes,
        seed, cfg_scale, steps
    ):
        if not self.current_storyboard:
            return "❌ Error: No storyboard loaded", [], "**Timeline:** 0 shots, 0.0s total", "{}"
        index = int(index)
        if index < 0 or index >= len(self.current_storyboard.shots):
            return f"❌ Error: Invalid index {index}", self._storyboard_to_dataframe(), self._get_timeline_info(), self._storyboard_to_json_str()
        if not filename_base:
            return "❌ Error: Filename Base is required", self._storyboard_to_dataframe(), self._get_timeline_info(), self._storyboard_to_json_str()
        if not description:
            return "❌ Error: Description is required", self._storyboard_to_dataframe(), self._get_timeline_info(), self._storyboard_to_json_str()
        if not prompt:
            return "❌ Error: Prompt is required", self._storyboard_to_dataframe(), self._get_timeline_info(), self._storyboard_to_json_str()

        # Prepare wan_motion data
        wan_motion_data = None
        if wan_motion_type and wan_motion_type != "none":
            wan_motion_data = {
                "type": wan_motion_type,
                "strength": float(wan_motion_strength) if wan_motion_strength else 0.5,
                "notes": wan_motion_notes or ""
            }

        self.current_storyboard = self.editor_service.update_shot(
            self.current_storyboard,
            index,
            shot_id=shot_id,
            filename_base=filename_base,
            description=description,
            prompt=prompt,
            duration=float(duration),
            camera_movement=camera_movement,
            character=character or "",
            negative_prompt=negative_prompt or "",
            wan_motion=wan_motion_data,
            seed=int(seed) if seed else -1,
            cfg_scale=float(cfg_scale) if cfg_scale else 7.0,
            steps=int(steps) if steps else 20,
        )

        # Auto-save after update to the CURRENT storyboard
        save_status = ""
        try:
            current_sb_path = self.config.get("current_storyboard")
            if current_sb_path and os.path.exists(current_sb_path):
                StoryboardService.save_storyboard(self.current_storyboard, current_sb_path)
                save_status = " (auto-saved)"
                logger.info(f"Auto-saved storyboard after updating shot {shot_id}")
            else:
                save_status = " (no storyboard selected)"
        except Exception as e:
            logger.warning(f"Could not auto-save storyboard: {e}")
            save_status = " (save failed)"

        shot_list = self._storyboard_to_dataframe()
        timeline = self._get_timeline_info()
        json_str = self._storyboard_to_json_str()
        return f"✅ Updated shot at index {index}{save_status}", gr.update(value=shot_list), timeline, json_str

    @handle_errors("Failed to delete shot")
    def delete_shot(self, index):
        if not self.current_storyboard:
            return "❌ Error: No storyboard loaded", gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}"
        index = int(index)
        try:
            self.current_storyboard = self.editor_service.delete_shot(self.current_storyboard, index)
        except IndexError:
            return f"❌ Error: Invalid index {index}", gr.update(value=self._storyboard_to_dataframe()), self._get_timeline_info(), self._storyboard_to_json_str()
        shot_list = self._storyboard_to_dataframe()
        timeline = self._get_timeline_info()
        json_str = self._storyboard_to_json_str()
        return f"✅ Deleted shot at index {index}", gr.update(value=shot_list), timeline, json_str

    @handle_errors("Failed to load shot")
    def load_shot_to_editor(self, index):
        default_values = [
            "", "", "", "", 3.0, "static",  # shot_id, filename_base, description, prompt, duration, camera_movement
            "", "",  # character, negative_prompt
            "none", 0.5, "",  # wan_motion_type, wan_motion_strength, wan_motion_notes
            -1, 7.0, 20,  # seed, cfg_scale, steps
            "❌ No storyboard"
        ]
        if not self.current_storyboard:
            return default_values
        index = int(index)
        if index < 0 or index >= len(self.current_storyboard.shots):
            default_values[-1] = f"❌ Invalid index {index}"
            return default_values

        shot = self.current_storyboard.shots[index]

        # Extract wan_motion data
        wan_motion = shot.wan_motion if hasattr(shot, 'wan_motion') and shot.wan_motion else None
        wan_type = wan_motion.type if wan_motion and hasattr(wan_motion, 'type') else shot.raw.get("wan_motion", {}).get("type", "none")
        wan_strength = wan_motion.strength if wan_motion and hasattr(wan_motion, 'strength') else shot.raw.get("wan_motion", {}).get("strength", 0.5)
        wan_notes = wan_motion.notes if wan_motion and hasattr(wan_motion, 'notes') else shot.raw.get("wan_motion", {}).get("notes", "")

        return [
            shot.shot_id,
            shot.filename_base,
            shot.raw.get("description", shot.description if hasattr(shot, 'description') else ""),
            shot.prompt,
            shot.duration,
            shot.raw.get("camera_movement", getattr(shot, "camera_movement", "static") or "static"),
            shot.raw.get("character", ""),
            shot.raw.get("negative_prompt", ""),
            wan_type or "none",
            float(wan_strength) if wan_strength else 0.5,
            wan_notes or "",
            int(shot.raw.get("seed", -1)),
            float(shot.raw.get("cfg_scale", 7.0)),
            int(shot.raw.get("steps", 20)),
            f"✅ Loaded shot {shot.shot_id}",
        ]

    def _storyboard_to_dataframe(self) -> List[List]:
        if not self.current_storyboard:
            return []
        rows = []
        for i, shot in enumerate(self.current_storyboard.shots):
            rows.append([
                i,
                shot.shot_id,
                shot.filename_base,
                shot.raw.get("description", ""),
                shot.duration
            ])
        return rows

    def _get_timeline_info(self) -> str:
        if not self.current_storyboard:
            return "**Timeline:** 0 shots, 0.0s total"
        total_duration = sum(float(shot.duration) for shot in self.current_storyboard.shots)
        shot_count = len(self.current_storyboard.shots)
        return f"**Timeline:** {shot_count} shots, {total_duration:.1f}s total"

    def _storyboard_to_json_str(self) -> str:
        if not self.current_storyboard:
            return "{}"
        data = self.editor_service.storyboard_to_dict(self.current_storyboard)
        return json.dumps(data, indent=2, ensure_ascii=False)


__all__ = ["StoryboardEditorAddon"]
