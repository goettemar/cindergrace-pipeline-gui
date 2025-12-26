import os
import sys
import json
from typing import Optional, List, Dict, Any, Tuple, NamedTuple
import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import create_storyboard_preview, format_project_status_extended
from addons.shared_styles import inject_styles
from addons.ui_factories import (
    create_universal_presets,
    create_keyframe_presets,
    create_video_presets,
    create_render_settings,
)
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.preset_service import PresetService
from infrastructure.logger import get_logger
from infrastructure.error_handler import handle_errors
from domain.storyboard_service import StoryboardService
from domain import models as domain_models
from services.storyboard_editor_service import StoryboardEditorService
from services.character_lora_service import CharacterLoraService
from addons.handlers.storyboard_handlers import StoryboardHandlers, ShotInputs

logger = get_logger(__name__)


class StoryboardUIComponents(NamedTuple):
    """Container for all Storyboard Editor UI components.

    Groups UI elements by their location/purpose for cleaner event wiring.
    """
    # Header
    storyboard_info: gr.HTML

    # Left pane - Status & List
    status_box: gr.Markdown
    shot_list: gr.Dataframe
    timeline_info: gr.Markdown

    # Left pane - Buttons
    add_shot_btn: gr.Button
    update_shot_btn: gr.Button
    delete_shot_btn: gr.Button
    load_shot_btn: gr.Button
    save_storyboard_btn: gr.Button

    # Left pane - Preview
    json_preview: gr.Code

    # Right pane - Shot Identity
    selected_shot_index: gr.Number
    shot_id: gr.Textbox
    filename_base: gr.Textbox

    # Right pane - Prompts Tab
    description: gr.Textbox
    prompt: gr.TextArea
    negative_prompt: gr.TextArea
    preset_style: gr.Dropdown
    preset_lighting: gr.Dropdown
    preset_mood: gr.Dropdown
    preset_time_of_day: gr.Dropdown

    # Right pane - Keyframe Tab
    character_lora: gr.Dropdown
    refresh_lora_btn: gr.Button
    preset_composition: gr.Dropdown
    preset_color_grade: gr.Dropdown
    flux_seed: gr.Number
    flux_cfg: gr.Number
    flux_steps: gr.Number

    # Right pane - Video Tab
    characters: gr.Dropdown
    refresh_chars_btn: gr.Button
    duration: gr.Number
    preset_camera: gr.Dropdown
    preset_motion: gr.Dropdown
    wan_motion_strength: gr.Slider
    wan_seed: gr.Number
    wan_cfg: gr.Number
    wan_steps: gr.Number


class StoryboardEditorAddon(BaseAddon):
    def __init__(self):
        super().__init__(
            name="Storyboard Editor",
            description="Create and edit storyboards for the active project",
            category="project"
        )
        self.config = ConfigManager()
        self.project_store = ProjectStore(self.config)
        self.editor_service = StoryboardEditorService()
        self.preset_service = PresetService()  # Auto-seeds if empty
        self.character_lora_service = CharacterLoraService(self.config)
        self.current_storyboard: Optional[domain_models.Storyboard] = None
        self.shot_handlers = StoryboardHandlers(self)

    def get_tab_name(self) -> str:
        return "📝 Editor"

    def _auto_load_default_storyboard(self) -> dict:
        """Auto-load current storyboard on tab open and return initial UI data."""
        tab_name = "📝 Storyboard Editor"
        default_data = {
            "storyboard_info": format_project_status_extended(self.project_store, self.config, tab_name),
            "status": "",
            "shots": [],
            "timeline": "**Timeline:** 0 shots, 0.0s total"
        }

        try:
            project = self.project_store.get_active_project(refresh=True)
            if not project:
                return default_data

            # Load the CURRENT storyboard (from SQLite via active project)
            current_sb_path = self.config.get_current_storyboard()
            if current_sb_path and os.path.exists(current_sb_path):
                self.current_storyboard = StoryboardService.load_from_file(current_sb_path)
                shot_list = self._storyboard_to_dataframe()
                current_sb_name = os.path.basename(current_sb_path)
                default_data["storyboard_info"] = format_project_status_extended(
                    self.project_store, self.config, tab_name
                )
                default_data["status"] = f"✅ {len(shot_list)} Shots loaded"
                default_data["shots"] = shot_list
                default_data["timeline"] = self._get_timeline_info()
                logger.info(f"Auto-loaded current storyboard: {current_sb_name} with {len(shot_list)} shots")
            else:
                default_data["storyboard_info"] = format_project_status_extended(
                    self.project_store, self.config, tab_name
                )
                default_data["status"] = "⚠️ No storyboard selected – please select one in 📚 Storyboards"

        except Exception as e:
            logger.error(f"Error auto-loading storyboard: {e}", exc_info=True)
            default_data["storyboard_info"] = format_project_status_extended(
                self.project_store, self.config, tab_name
            )
            default_data["status"] = f"❌ Error: {str(e)}"

        return default_data

    def _on_tab_load(self) -> Tuple:
        """Called when tab loads/becomes visible - refresh storyboard from config.

        Returns tuple matching interface.load outputs:
        (storyboard_info, status_box, shot_list, timeline_info, json_preview, character_lora)
        """
        # Refresh config to pick up changes from other tabs (like Project tab or Storyboard Manager)
        self.config.refresh()

        # Load storyboard data
        data = self._auto_load_default_storyboard()

        # Get character LoRA choices (refresh from ComfyUI models folder)
        lora_choices = self._get_character_lora_choices()

        return (
            data["storyboard_info"],                              # storyboard_info
            data["status"],                                       # status_box
            gr.update(value=data["shots"]),                       # shot_list
            data["timeline"],                                     # timeline_info
            self._storyboard_to_json_str(),                       # json_preview
            gr.Dropdown(choices=lora_choices, value="none")       # character_lora (reset to none)
        )

    def load_shot_from_row_click(self, evt: gr.SelectData) -> Tuple:
        """Handle row click to load shot into editor tabs."""
        # Order: selected_shot_index, shot_id, filename_base, description, prompt, negative_prompt,
        #        preset_style, preset_lighting, preset_mood, preset_time_of_day,
        #        preset_composition, preset_color_grade, flux_seed, flux_cfg, flux_steps,
        #        preset_camera, preset_motion, wan_motion_strength, duration, characters,
        #        wan_seed, wan_cfg, wan_steps, character_lora, status
        default_values = [
            0,                      # selected_shot_index
            "", "", "", "", "",     # shot_id, filename_base, description, prompt, negative_prompt
            "none", "none", "none", "none",  # preset_style, preset_lighting, preset_mood, preset_time_of_day
            "none", "none", -1, 7.0, 20,     # preset_composition, preset_color_grade, flux_seed, flux_cfg, flux_steps
            "none", "none", 0.5, 3.0, [],    # preset_camera, preset_motion, wan_motion_strength, duration, characters
            -1, 7.0, 20,            # wan_seed, wan_cfg, wan_steps
            "none",                 # character_lora
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

        # Extract data from raw
        presets = shot.raw.get("presets", {})
        flux_settings = shot.raw.get("flux", {})
        wan_settings = shot.raw.get("wan", {})

        # Get character_lora (new single-select field)
        character_lora_value = shot.character_lora or shot.raw.get("character_lora") or "none"

        return (
            row_index,  # selected_shot_index
            shot.shot_id,
            shot.filename_base,
            shot.raw.get("description", ""),
            shot.prompt,
            shot.raw.get("negative_prompt", ""),
            # Universal presets
            presets.get("style", "none"),
            presets.get("lighting", "none"),
            presets.get("mood", "none"),
            presets.get("time_of_day", "none"),
            # Keyframe (Flux) presets
            presets.get("composition", "none"),
            presets.get("color_grade", "none"),
            int(flux_settings.get("seed", -1)),
            float(flux_settings.get("cfg", 7.0)),
            int(flux_settings.get("steps", 20)),
            # Video (Wan) presets
            presets.get("camera", "none"),
            presets.get("motion", "none"),
            float(wan_settings.get("motion_strength", 0.5)),
            shot.duration,
            shot.characters,  # List of character IDs (legacy)
            int(wan_settings.get("seed", -1)),
            float(wan_settings.get("cfg", 7.0)),
            int(wan_settings.get("steps", 20)),
            character_lora_value,  # Single character LoRA
            f"✅ Loaded shot {shot.shot_id}"
        )

    def _get_character_choices(self) -> List[str]:
        """Get dropdown choices for character LoRAs (legacy multi-select)."""
        loras = self.character_lora_service.scan_loras(force_refresh=True)
        return [lora.id for lora in loras]

    def _get_character_lora_choices(self) -> List[Tuple[str, str]]:
        """Get dropdown choices for single character LoRA selection.

        Returns list of (display_name, id) tuples including "No Character" option.
        Format: [("No Character", "none"), ("Elena", "cg_elena"), ...]
        """
        choices = [("No Character", "none")]
        loras = self.character_lora_service.scan_loras(force_refresh=True)
        for lora in loras:
            choices.append((lora.name, lora.id))
        return choices

    def _refresh_character_choices(self):
        """Refresh character LoRA choices for dropdown."""
        choices = self._get_character_choices()
        return gr.update(choices=choices)

    def _refresh_character_lora_choices(self):
        """Refresh single character LoRA dropdown choices."""
        choices = self._get_character_lora_choices()
        return gr.update(choices=choices)

    def render(self) -> gr.Blocks:
        """Render the Storyboard Editor interface.

        Structured as:
        - Header (project status bar)
        - Left pane (shot list, buttons, preview)
        - Right pane (shot editor with tabs)
        - Event connections
        """
        initial_data = self._auto_load_default_storyboard()

        with gr.Blocks() as interface:
            inject_styles()

            # Build UI components - header outside of Row for full width
            storyboard_info = gr.HTML(initial_data["storyboard_info"])
            with gr.Row():
                refresh_storyboard_btn = gr.Button("🔄 Refresh Storyboard", size="sm", variant="secondary")

            with gr.Row(equal_height=False):
                left_components = self._render_left_pane(initial_data)
                right_components = self._render_right_pane()

            # Combine all components
            ui = StoryboardUIComponents(
                storyboard_info=storyboard_info,
                **left_components,
                **right_components,
            )

            # Wire up events
            self._connect_events(ui, interface)

            # Refresh button event (separate because not in NamedTuple)
            refresh_storyboard_btn.click(
                fn=self._on_tab_load,
                outputs=[
                    ui.storyboard_info, ui.status_box, ui.shot_list,
                    ui.timeline_info, ui.json_preview, ui.character_lora
                ]
            )

        return interface

    def _render_left_pane(self, initial_data: dict) -> dict:
        """Render the left pane: shot list, action buttons, and preview.

        Args:
            initial_data: Initial storyboard data from auto-load

        Returns:
            Dictionary of UI components for this pane
        """
        with gr.Column(scale=1):
            status_box = gr.Markdown(initial_data["status"])

            # Shots List
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

            # Action buttons
            with gr.Row():
                add_shot_btn = gr.Button("➕ Add Shot", variant="primary")
                update_shot_btn = gr.Button("💾 Update Shot", variant="primary")
            with gr.Row():
                delete_shot_btn = gr.Button("🗑️ Delete Selected", variant="stop")
                load_shot_btn = gr.Button("📋 Load Selected", variant="secondary")
            save_storyboard_btn = gr.Button("💾 Save Storyboard", variant="primary", size="lg")

            # Storyboard Details (collapsed)
            preview_ui = create_storyboard_preview(
                initial_value=self._storyboard_to_json_str()
            )
            json_preview = preview_ui.code

        return {
            "status_box": status_box,
            "shot_list": shot_list,
            "timeline_info": timeline_info,
            "add_shot_btn": add_shot_btn,
            "update_shot_btn": update_shot_btn,
            "delete_shot_btn": delete_shot_btn,
            "load_shot_btn": load_shot_btn,
            "save_storyboard_btn": save_storyboard_btn,
            "json_preview": json_preview,
        }

    def _render_right_pane(self) -> dict:
        """Render the right pane: shot editor with tabs.

        Returns:
            Dictionary of UI components for this pane
        """
        with gr.Column(scale=1, elem_id="right_pane"):
            gr.Markdown("### Shot Editor")

            # Shot Identity
            with gr.Group():
                selected_shot_index = gr.Number(
                    label="Shot Index", value=0, minimum=0,
                    precision=0, info="0 = first shot", scale=0
                )
                with gr.Row():
                    shot_id = gr.Textbox(
                        label="Shot ID", placeholder="001",
                        info="Auto-generated if empty"
                    )
                    filename_base = gr.Textbox(
                        label="Filename", placeholder="cathedral-interior",
                        info="No spaces"
                    )

            # Editor Tabs
            with gr.Tabs(elem_id="editor_tabs", selected=0):
                prompts = self._render_prompts_tab()
                keyframe = self._render_keyframe_tab()
                video = self._render_video_tab()

        return {
            "selected_shot_index": selected_shot_index,
            "shot_id": shot_id,
            "filename_base": filename_base,
            **prompts,
            **keyframe,
            **video,
        }

    def _render_prompts_tab(self) -> dict:
        """Render the Prompts tab content."""
        with gr.Tab("📝 Prompts"):
            description = gr.Textbox(
                label="Description",
                placeholder="Opening scene inside the cathedral",
                info="Readable description for storyboard"
            )
            prompt = gr.TextArea(
                label="Prompt",
                placeholder="Gothic cathedral interior, dramatic lighting...",
                lines=4, info="Base prompt for AI generation (required)"
            )
            negative_prompt = gr.TextArea(
                label="Negative Prompt",
                placeholder="blurry, low quality, distorted...",
                lines=2, info="What should be avoided"
            )

            # Universal presets via factory
            universal = create_universal_presets(self.preset_service)

        return {
            "description": description,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "preset_style": universal["style"],
            "preset_lighting": universal["lighting"],
            "preset_mood": universal["mood"],
            "preset_time_of_day": universal["time_of_day"],
        }

    def _render_keyframe_tab(self) -> dict:
        """Render the Keyframe (Flux) tab content."""
        with gr.Tab("🖼️ Keyframe"):
            gr.Markdown("*Settings for Flux image generation*")

            # Character LoRA
            gr.Markdown("#### 🎭 Character LoRA")
            with gr.Row():
                character_lora = gr.Dropdown(
                    label="Character LoRA",
                    choices=self._get_character_lora_choices(),
                    value="none", info="cg_* LoRAs from ComfyUI/models/loras/"
                )
                refresh_lora_btn = gr.Button("↻", scale=0, min_width=50)
            gr.Markdown(
                "💡 *When a Character LoRA is set, the Keyframe Generator will "
                "automatically use the `gcpl_*` workflow variant (if available).*",
                elem_classes=["info-hint"]
            )

            # Keyframe presets via factory
            keyframe_presets = create_keyframe_presets(self.preset_service)

            # Render Settings via factory
            gr.Markdown("#### Render-Settings (Flux)")
            flux_settings = create_render_settings(prefix="flux")

        return {
            "character_lora": character_lora,
            "refresh_lora_btn": refresh_lora_btn,
            "preset_composition": keyframe_presets["composition"],
            "preset_color_grade": keyframe_presets["color_grade"],
            "flux_seed": flux_settings["seed"],
            "flux_cfg": flux_settings["cfg"],
            "flux_steps": flux_settings["steps"],
        }

    def _render_video_tab(self) -> dict:
        """Render the Video (Wan) tab content."""
        with gr.Tab("🎥 Video"):
            gr.Markdown("*Settings for Wan 2.2 video generation*")

            # Character LoRAs (legacy multi-select)
            gr.Markdown("#### 🎭 Character LoRAs")
            with gr.Row():
                characters = gr.Dropdown(
                    label="Characters", choices=self._get_character_choices(),
                    value=[], multiselect=True,
                    info="LoRAs from <ComfyUI>/output/character/"
                )
                refresh_chars_btn = gr.Button("↻", scale=0, min_width=50)

            # Clip Settings
            gr.Markdown("#### Clip Settings")
            with gr.Row():
                duration = gr.Number(
                    label="Duration (sec.)", value=3.0, minimum=0.5, maximum=30.0,
                    step=0.5, precision=1, info="Clip length"
                )

            # Video presets via factory
            gr.Markdown("#### Camera & Motion")
            video_presets = create_video_presets(self.preset_service)
            wan_motion_strength = gr.Slider(
                label="Motion Strength", minimum=0.0, maximum=1.0,
                value=0.5, step=0.1, info="Movement intensity"
            )

            # Render Settings via factory
            gr.Markdown("#### Render-Settings (Wan)")
            wan_settings = create_render_settings(prefix="wan")

        return {
            "characters": characters,
            "refresh_chars_btn": refresh_chars_btn,
            "duration": duration,
            "preset_camera": video_presets["camera"],
            "preset_motion": video_presets["motion"],
            "wan_motion_strength": wan_motion_strength,
            "wan_seed": wan_settings["seed"],
            "wan_cfg": wan_settings["cfg"],
            "wan_steps": wan_settings["steps"],
        }

    def _connect_events(self, ui: StoryboardUIComponents, interface: gr.Blocks) -> None:
        """Connect all UI events to their handlers.

        Args:
            ui: Container with all UI components
            interface: The Gradio Blocks interface
        """
        # Refresh buttons
        ui.refresh_chars_btn.click(
            fn=self._refresh_character_choices,
            outputs=[ui.characters]
        )
        ui.refresh_lora_btn.click(
            fn=self._refresh_character_lora_choices,
            outputs=[ui.character_lora]
        )

        # Shot input components (used in multiple handlers)
        shot_inputs = [
            ui.shot_id, ui.filename_base, ui.description, ui.prompt, ui.negative_prompt,
            ui.preset_style, ui.preset_lighting, ui.preset_mood, ui.preset_time_of_day,
            ui.preset_composition, ui.preset_color_grade, ui.flux_seed, ui.flux_cfg, ui.flux_steps,
            ui.preset_camera, ui.preset_motion, ui.wan_motion_strength, ui.duration, ui.characters,
            ui.wan_seed, ui.wan_cfg, ui.wan_steps, ui.character_lora
        ]
        shot_outputs = [ui.status_box, ui.shot_list, ui.timeline_info, ui.json_preview]

        # Shot CRUD buttons
        ui.add_shot_btn.click(
            fn=self.add_shot,
            inputs=shot_inputs,
            outputs=shot_outputs
        )
        ui.update_shot_btn.click(
            fn=self.update_shot,
            inputs=[ui.selected_shot_index] + shot_inputs,
            outputs=shot_outputs
        )
        ui.delete_shot_btn.click(
            fn=self.delete_shot,
            inputs=[ui.selected_shot_index],
            outputs=shot_outputs
        )

        # Load shot to editor
        editor_outputs = shot_inputs + [ui.status_box]
        ui.load_shot_btn.click(
            fn=self.load_shot_to_editor,
            inputs=[ui.selected_shot_index],
            outputs=editor_outputs
        )

        # Auto-load on row click
        ui.shot_list.select(
            fn=self.load_shot_from_row_click,
            inputs=[],
            outputs=[ui.selected_shot_index] + editor_outputs
        )

        # Save storyboard
        ui.save_storyboard_btn.click(
            fn=self.save_current_storyboard,
            outputs=[ui.status_box, ui.json_preview]
        )

        # Auto-refresh on tab load
        interface.load(
            fn=self._on_tab_load,
            outputs=[
                ui.storyboard_info, ui.status_box, ui.shot_list,
                ui.timeline_info, ui.json_preview, ui.character_lora
            ]
        )

    def _get_current_storyboard_display(self) -> str:
        """Get markdown display for current storyboard."""
        current_sb = self.config.get_current_storyboard()
        if current_sb and os.path.exists(current_sb):
            filename = os.path.basename(current_sb)
            return f"**Active:** `{filename}`"
        return "**Active:** *No storyboard selected*"

    def _get_storyboard_choices(self) -> List[str]:
        """Get list of storyboard files for dropdown."""
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return []
        return self.project_store.list_project_storyboards(project)

    def _get_current_storyboard_filename(self) -> Optional[str]:
        """Get current storyboard filename for dropdown selection."""
        current_sb = self.config.get_current_storyboard()
        if current_sb and os.path.exists(current_sb):
            return os.path.basename(current_sb)
        return None

    @handle_errors("Failed to refresh storyboard info", return_tuple=False)
    def _refresh_storyboard_info(self) -> str:
        """Refresh the storyboard info display at the top."""
        tab_name = "📝 Storyboard Editor"
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return format_project_status(None, None, tab_name=tab_name)
        return format_project_status(project.get("name"), project.get("slug"), tab_name=tab_name)

    @handle_errors("Failed to refresh files")
    def _refresh_storyboard_files(self) -> Tuple[gr.Dropdown, str]:
        """Refresh storyboard file dropdown and current display."""
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return gr.Dropdown(choices=[], value=None), self._get_current_storyboard_display()

        files = self.project_store.list_project_storyboards(project)
        current_filename = self._get_current_storyboard_filename()

        return (
            gr.Dropdown(choices=files, value=current_filename if current_filename in files else None),
            self._get_current_storyboard_display()
        )

    @handle_errors("Failed to create storyboard")
    def create_new_storyboard(self, storyboard_name: str) -> Tuple:
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return ("**Storyboard:** ❌ No active project", "Create a project in 📁 Project tab",
                    gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}", gr.Dropdown(),
                    self._get_current_storyboard_display())
        if not storyboard_name:
            storyboard_name = "storyboard_main"
        if not storyboard_name.endswith(".json"):
            storyboard_name += ".json"

        self.current_storyboard = self.editor_service.create_new_storyboard(project["name"])
        storyboard_dir = self.project_store.ensure_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, storyboard_name)
        StoryboardService.save_storyboard(self.current_storyboard, file_path)

        # Set as active storyboard
        self.project_store.set_project_storyboard(project, file_path, set_as_default=True)

        shot_list = self._storyboard_to_dataframe()
        timeline = self._get_timeline_info()
        json_str = self._storyboard_to_json_str()

        files = self.project_store.list_project_storyboards(project)
        storyboard_info = f"**Storyboard:** `{storyboard_name}`"
        status = f"✅ Storyboard created: {storyboard_name}"
        current_display = self._get_current_storyboard_display()

        return (storyboard_info, status, gr.update(value=shot_list), timeline, json_str,
                gr.Dropdown(choices=files, value=storyboard_name), current_display)

    @handle_errors("Failed to load storyboard")
    def load_storyboard(self, filename: str) -> Tuple:
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return ("**Storyboard:** ❌ No active project", "Select a project in 📁 Project tab",
                    gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}",
                    self._get_current_storyboard_display())
        if not filename:
            return ("**Storyboard:** ❌ No file selected", "Select a storyboard above",
                    gr.update(value=[]), "**Timeline:** 0 shots, 0.0s total", "{}",
                    self._get_current_storyboard_display())

        storyboard_dir = self.project_store.ensure_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, filename)
        self.current_storyboard = StoryboardService.load_from_file(file_path)

        # Set as active storyboard
        self.project_store.set_project_storyboard(project, file_path, set_as_default=True)

        shot_list = self._storyboard_to_dataframe()
        timeline = self._get_timeline_info()
        json_str = self._storyboard_to_json_str()
        logger.info(f"Loaded storyboard with {len(shot_list)} shots")

        storyboard_info = f"**Storyboard:** `{filename}`"
        status = f"✅ {len(shot_list)} Shots loaded aus {filename}"
        current_display = self._get_current_storyboard_display()

        return (storyboard_info, status, gr.update(value=shot_list), timeline, json_str, current_display)

    @handle_errors("Failed to save storyboard")
    def save_storyboard(self, storyboard_filename: str) -> Tuple:
        """Save storyboard and set as active."""
        if not self.current_storyboard:
            return ("❌ No storyboard loaded", gr.Dropdown(),
                    "**Storyboard:** ❌ No storyboard", "{}", self._get_current_storyboard_display())
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return ("❌ No active project", gr.Dropdown(),
                    "**Storyboard:** ❌ No project", "{}", self._get_current_storyboard_display())

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

        # Set as active storyboard (like project tab does)
        self.project_store.set_project_storyboard(project, file_path, set_as_default=True)

        files = self.project_store.list_project_storyboards(project)
        storyboard_info = f"**Storyboard:** `{storyboard_filename}`"
        json_str = self._storyboard_to_json_str()
        current_display = self._get_current_storyboard_display()

        return (f"✅ Saved: {storyboard_filename}",
                gr.Dropdown(choices=files, value=storyboard_filename),
                storyboard_info, json_str, current_display)

    @handle_errors("Failed to save storyboard")
    def save_current_storyboard(self) -> Tuple[str, str]:
        """Save the current storyboard to its file (no filename input needed)."""
        if not self.current_storyboard:
            return "❌ No storyboard loaded", "{}"

        current_sb_path = self.config.get_current_storyboard()
        if not current_sb_path:
            return "❌ No storyboard path set - please select a storyboard first", "{}"

        try:
            StoryboardService.save_storyboard(self.current_storyboard, current_sb_path)
            json_str = self._storyboard_to_json_str()
            filename = os.path.basename(current_sb_path)
            logger.info(f"Saved storyboard to {current_sb_path}")
            return f"✅ Storyboard saved: {filename}", json_str
        except Exception as e:
            logger.error(f"Failed to save storyboard: {e}", exc_info=True)
            return f"❌ Save failed: {e}", self._storyboard_to_json_str()

    def _show_delete_storyboard_confirm(self, filename: str) -> Tuple[str, gr.Group]:
        """Show delete confirmation dialog."""
        if not filename:
            return "### ⚠️ No storyboard selected", gr.update(visible=False)

        confirm_text = f"""### ⚠️ Really delete storyboard?

**File:** `{filename}`

**Warning:** This action cannot be undone!
"""
        return confirm_text, gr.update(visible=True)

    @handle_errors("Failed to delete storyboard")
    def _delete_storyboard(self, filename: str) -> Tuple:
        """Delete storyboard file after confirmation."""
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return ("**Storyboard:** ❌ No active project", "❌ No active project",
                    gr.update(value=[]), "**Timeline:** 0 shots", "{}",
                    gr.Dropdown(choices=[]), self._get_current_storyboard_display(),
                    gr.update(visible=False))

        if not filename:
            return ("**Storyboard:** ❌ No file selected", "❌ No file selected",
                    gr.update(), self._get_timeline_info(), self._storyboard_to_json_str(),
                    gr.update(), self._get_current_storyboard_display(),
                    gr.update(visible=False))

        success = self.project_store.delete_storyboard(project, filename)

        if success:
            # Clear current storyboard if it was the deleted one
            self.current_storyboard = None

            # Get remaining files
            files = self.project_store.list_project_storyboards(project)
            current_sb = self.config.get_current_storyboard()

            # If a new storyboard was auto-selected, load it
            if current_sb and os.path.exists(current_sb):
                try:
                    self.current_storyboard = StoryboardService.load_from_file(current_sb)
                except Exception:
                    pass

            shot_list = self._storyboard_to_dataframe()
            timeline = self._get_timeline_info()
            json_str = self._storyboard_to_json_str()
            current_filename = self._get_current_storyboard_filename()

            storyboard_info = f"**Storyboard:** `{current_filename}`" if current_filename else "**Storyboard:** *None selected*"

            return (storyboard_info, f"✅ Storyboard deleted: {filename}",
                    gr.update(value=shot_list), timeline, json_str,
                    gr.Dropdown(choices=files, value=current_filename),
                    self._get_current_storyboard_display(),
                    gr.update(visible=False))
        else:
            return (self._refresh_storyboard_info(), f"❌ Could not delete {filename}",
                    gr.update(), self._get_timeline_info(), self._storyboard_to_json_str(),
                    gr.update(), self._get_current_storyboard_display(),
                    gr.update(visible=False))

    @handle_errors("Failed to add shot")
    def add_shot(
        self, shot_id, filename_base, description, prompt, negative_prompt,
        preset_style, preset_lighting, preset_mood, preset_time_of_day,
        preset_composition, preset_color_grade, flux_seed, flux_cfg, flux_steps,
        preset_camera, preset_motion, wan_motion_strength, duration, characters,
        wan_seed, wan_cfg, wan_steps, character_lora
    ):
        """Add a new shot to the storyboard. Delegates to StoryboardHandlers."""
        inputs = ShotInputs(
            shot_id, filename_base, description, prompt, negative_prompt,
            preset_style, preset_lighting, preset_mood, preset_time_of_day,
            preset_composition, preset_color_grade, flux_seed, flux_cfg, flux_steps,
            preset_camera, preset_motion, wan_motion_strength, duration, characters,
            wan_seed, wan_cfg, wan_steps, character_lora
        )
        return self.shot_handlers.add_shot(inputs)

    @handle_errors("Failed to update shot")
    def update_shot(
        self, index, shot_id, filename_base, description, prompt, negative_prompt,
        preset_style, preset_lighting, preset_mood, preset_time_of_day,
        preset_composition, preset_color_grade, flux_seed, flux_cfg, flux_steps,
        preset_camera, preset_motion, wan_motion_strength, duration, characters,
        wan_seed, wan_cfg, wan_steps, character_lora
    ):
        """Update an existing shot. Delegates to StoryboardHandlers."""
        inputs = ShotInputs(
            shot_id, filename_base, description, prompt, negative_prompt,
            preset_style, preset_lighting, preset_mood, preset_time_of_day,
            preset_composition, preset_color_grade, flux_seed, flux_cfg, flux_steps,
            preset_camera, preset_motion, wan_motion_strength, duration, characters,
            wan_seed, wan_cfg, wan_steps, character_lora
        )
        return self.shot_handlers.update_shot(index, inputs)

    @handle_errors("Failed to delete shot")
    def delete_shot(self, index):
        """Delete a shot from the storyboard. Delegates to StoryboardHandlers."""
        return self.shot_handlers.delete_shot(index)

    @handle_errors("Failed to load shot")
    def load_shot_to_editor(self, index):
        # Order: shot_id, filename_base, description, prompt, negative_prompt,
        #        preset_style, preset_lighting, preset_mood, preset_time_of_day,
        #        preset_composition, preset_color_grade, flux_seed, flux_cfg, flux_steps,
        #        preset_camera, preset_motion, wan_motion_strength, duration, characters,
        #        wan_seed, wan_cfg, wan_steps, character_lora, status
        default_values = [
            "", "", "", "", "",     # shot_id, filename_base, description, prompt, negative_prompt
            "none", "none", "none", "none",  # preset_style, preset_lighting, preset_mood, preset_time_of_day
            "none", "none", -1, 7.0, 20,     # preset_composition, preset_color_grade, flux_seed, flux_cfg, flux_steps
            "none", "none", 0.5, 3.0, [],    # preset_camera, preset_motion, wan_motion_strength, duration, characters
            -1, 7.0, 20,            # wan_seed, wan_cfg, wan_steps
            "none",                 # character_lora
            "❌ No storyboard"
        ]
        if not self.current_storyboard:
            return default_values
        index = int(index)
        if index < 0 or index >= len(self.current_storyboard.shots):
            default_values[-1] = f"❌ Invalid index {index}"
            return default_values

        shot = self.current_storyboard.shots[index]

        # Extract data from raw
        presets = shot.raw.get("presets", {})
        flux_settings = shot.raw.get("flux", {})
        wan_settings = shot.raw.get("wan", {})

        # Get character_lora (new single-select field)
        character_lora_value = shot.character_lora or shot.raw.get("character_lora") or "none"

        return [
            shot.shot_id,
            shot.filename_base,
            shot.raw.get("description", ""),
            shot.prompt,
            shot.raw.get("negative_prompt", ""),
            # Universal presets
            presets.get("style", "none"),
            presets.get("lighting", "none"),
            presets.get("mood", "none"),
            presets.get("time_of_day", "none"),
            # Keyframe (Flux) presets
            presets.get("composition", "none"),
            presets.get("color_grade", "none"),
            int(flux_settings.get("seed", -1)),
            float(flux_settings.get("cfg", 7.0)),
            int(flux_settings.get("steps", 20)),
            # Video (Wan) presets
            presets.get("camera", "none"),
            presets.get("motion", "none"),
            float(wan_settings.get("motion_strength", 0.5)),
            shot.duration,
            shot.characters,  # List of character IDs (legacy)
            int(wan_settings.get("seed", -1)),
            float(wan_settings.get("cfg", 7.0)),
            int(wan_settings.get("steps", 20)),
            character_lora_value,  # Single character LoRA
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
