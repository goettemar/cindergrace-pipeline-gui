"""Keyframe Selector Addon for CINDERGRACE Pipeline"""
import os
import sys
import json
from typing import Dict, List, Tuple, Any

import gradio as gr

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import (
    format_project_status_extended,
    project_status_md,
    storyboard_status_md,
    create_storyboard_section,
)
from addons.helpers.storyboard_loader import load_storyboard_from_config
from addons.helpers.selection_formatter import format_selection_summary, build_preview_payload
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from infrastructure.error_handler import handle_errors
from domain.storyboard_service import StoryboardService
from services.selection_service import SelectionService

logger = get_logger(__name__)


class KeyframeSelectorAddon(BaseAddon):
    """Select best keyframe variants per shot and export selections"""

    def __init__(self):
        super().__init__(
            name="Keyframe Selector",
            description="Review generated keyframes and pick the best variant per shot",
            category="production"
        )
        self.config = ConfigManager()
        self.project_manager = ProjectStore(self.config)
        self.selection_service = SelectionService(self.project_manager)

    def get_tab_name(self) -> str:
        return "✅ Select"

    def _auto_load_storyboard(self) -> Dict[str, Any]:
        """Auto-load storyboard during render() - returns initial UI data."""
        defaults = {
            "storyboard_json": "{}",
            "status": "**Status:** Storyboard noch nicht loaded",
            "shot_ids": [],
            "storyboard_state": {},
            "summary": "No keyframes selected yet.",
            "preview": {},
            "selections_state": {},
            "variants_state": {},
        }

        try:
            self.config.refresh()
            storyboard, status_md, storyboard_raw = load_storyboard_from_config(self.config, apply_resolution=False)
            if not storyboard:
                defaults["status"] = status_md
                return defaults

            shots = storyboard.shots
            shot_ids = [shot.shot_id or f"{idx+1:03d}" for idx, shot in enumerate(shots)]
            project_name = storyboard.project or "Unknown Project"

            defaults["storyboard_json"] = json.dumps(storyboard_raw, indent=2)
            defaults["status"] = status_md or f"**✅ Storyboard loaded:** {project_name} – {len(shots)} Shots"
            defaults["shot_ids"] = shot_ids
            defaults["storyboard_state"] = storyboard_raw
            defaults["summary"] = format_selection_summary({}, storyboard_raw)
            defaults["preview"] = build_preview_payload(storyboard_raw, {})

            logger.info(f"Keyframe Selector: Auto-loaded storyboard with {len(shots)} shots")
        except Exception as e:
            logger.error(f"Keyframe Selector: Error in auto-load: {e}", exc_info=True)

        return defaults

    def render(self) -> gr.Blocks:
        """Render selector UI"""
        # Auto-load storyboard during render (not via interface.load)
        auto_loaded = self._auto_load_storyboard()

        storyboard_state = gr.State(auto_loaded["storyboard_state"])
        variants_state = gr.State(auto_loaded["variants_state"])
        selections_state = gr.State(auto_loaded["selections_state"])

        with gr.Blocks() as interface:
            # Unified header: Tab name left, project status right
            project_status = gr.HTML(format_project_status_extended(
                self.project_manager, self.config, "✅ Keyframe Selector"
            ))

            gr.Markdown(
                "Load a storyboard, review all generated keyframe variants "
                "and save the best selection per shot."
            )

            storyboard_section = create_storyboard_section(
                accordion_title="📁 Storyboard",
                info_md_value=storyboard_status_md(self.project_manager, self.config.get_current_storyboard(), "✅ Keyframe Selector"),
                reload_label="🔄 Storyboard neu laden",
            )
            storyboard_info_md = storyboard_section.info_md
            load_storyboard_btn = storyboard_section.reload_btn

            status_text = gr.Markdown(auto_loaded["status"])

            # Main content: Left sidebar (20%) + Right content (80%)
            with gr.Row():
                # Left sidebar - Shot selection and actions
                with gr.Column(scale=1, min_width=220):
                    gr.Markdown("### 🎬 Shot Selection")
                    refresh_shot_btn = gr.Button("🗂️ Refresh Keyframes", variant="secondary", size="sm")
                    shot_dropdown = gr.Dropdown(
                        choices=auto_loaded["shot_ids"],
                        value=auto_loaded["shot_ids"][0] if auto_loaded["shot_ids"] else None,
                        label="Shot select",
                        info="Select a shot",
                        interactive=True,
                    )

                    gr.Markdown("---")
                    gr.Markdown("#### Manage Variant")
                    variant_radio = gr.Radio(
                        choices=[],
                        label="Select Best Variant",
                        info="Choose the best variant for this shot",
                    )
                    save_selection_btn = gr.Button("💾 Save Shot Variant", variant="primary")
                    clear_selection_btn = gr.Button("🗑️ Remove Shot Variant", variant="stop")

                    # Delete confirmation dialog (hidden by default)
                    with gr.Group(visible=False) as clear_confirm_group:
                        clear_confirm_text = gr.Markdown(
                            "### ⚠️ Remove variant?\n\n"
                            "The saved selection for this shot will be deleted."
                        )
                        with gr.Row():
                            clear_confirm_btn = gr.Button("✅ Yes, remove", variant="stop", size="sm")
                            clear_cancel_btn = gr.Button("❌ Cancel", variant="secondary", size="sm")

                    gr.Markdown("---")
                    gr.Markdown("#### Export for Video Generator")
                    export_btn = gr.Button("📤 Save Shot Selection", variant="primary")

                    gr.Markdown("---")
                    gr.Markdown("#### 📊 Selection Summary")
                    selection_summary = gr.Markdown(auto_loaded["summary"])
                    selection_warning = gr.Markdown("", visible=False)

                # Right content - Shot overview and variants
                with gr.Column(scale=4):
                    gr.Markdown("### 🖼️ Shot Overview")
                    shot_info = gr.Markdown("No shot selected.")

                    keyframe_gallery = gr.Gallery(
                        label="Varianten",
                        show_label=True,
                        columns=4,
                        height="auto",
                        object_fit="contain",
                        elem_id="keyframe-gallery",
                    )

            # JSON Preview (collapsed by default)
            with gr.Accordion("📄 Export-Vorschau (JSON)", open=False):
                selection_json = gr.JSON(label="Export-Daten", value=auto_loaded["preview"])

            # Event wiring
            load_storyboard_btn.click(
                fn=self._reload_storyboard,
                outputs=[
                    storyboard_info_md,
                    status_text,
                    shot_dropdown,
                    storyboard_state,
                    selection_summary,
                    selection_json,
                    selections_state,
                    variants_state,
                ],
            )

            shot_dropdown.change(
                fn=self.load_shot_preview,
                inputs=[storyboard_state, shot_dropdown, variants_state, selections_state],
                outputs=[shot_info, keyframe_gallery, variant_radio, status_text, variants_state],
            )

            refresh_shot_btn.click(
                fn=self.load_shot_preview,
                inputs=[storyboard_state, shot_dropdown, variants_state, selections_state],
                outputs=[shot_info, keyframe_gallery, variant_radio, status_text, variants_state],
            )

            save_selection_btn.click(
                fn=self.save_selection,
                inputs=[shot_dropdown, variant_radio, storyboard_state, variants_state, selections_state],
                outputs=[status_text, selection_summary, selection_json, selections_state, selection_warning],
            )

            # Clear selection with confirmation dialog
            clear_selection_btn.click(
                fn=self._show_clear_confirm,
                inputs=[shot_dropdown, selections_state],
                outputs=[clear_confirm_text, clear_confirm_group],
            )
            clear_cancel_btn.click(
                fn=lambda: gr.update(visible=False),
                outputs=[clear_confirm_group],
            )
            clear_confirm_btn.click(
                fn=self.clear_selection,
                inputs=[shot_dropdown, storyboard_state, selections_state],
                outputs=[status_text, selection_summary, selection_json, selections_state, selection_warning, clear_confirm_group],
            )

            export_btn.click(
                fn=self.export_selections,
                inputs=[storyboard_state, selections_state],
                outputs=[status_text, selection_json, selection_warning],
            )

            # Auto-refresh storyboard on tab load
            interface.load(
                fn=self._on_tab_load,
                outputs=[
                    storyboard_info_md,
                    status_text,
                    shot_dropdown,
                    storyboard_state,
                    selection_summary,
                    selection_json,
                    selections_state,
                    variants_state,
                    project_status,
                ],
            )

        return interface

    def _on_tab_load(self):
        """Called when tab loads - refresh storyboard from config."""
        # Reload storyboard from config (picks up changes from Storyboard Editor)
        result = self._reload_storyboard()
        # result is: (storyboard_md, status, dropdown_update, storyboard_raw, summary, preview, selections, variants)

        project_status = project_status_md(self.project_manager, "✅ Keyframe Selector")

        # Return all outputs in correct order
        return (
            result[0],           # storyboard_info_md
            result[1],           # status_text
            result[2],           # shot_dropdown
            result[3],           # storyboard_state
            result[4],           # selection_summary
            result[5],           # selection_json
            result[6],           # selections_state
            result[7],           # variants_state
            project_status,      # project_status
        )

    def _reload_storyboard(self):
        """Reload storyboard and return markdown info instead of JSON."""
        result = self.load_storyboard_from_config()
        # Original returns: (storyboard_json, status, dropdown, storyboard_raw, summary, preview, selections, variants)
        # Replace first element (JSON) with markdown info
        storyboard_info_md = storyboard_status_md(self.project_manager, self.config.get_current_storyboard(), "✅ Keyframe Selector")
        return (
            storyboard_info_md,  # storyboard_info_md (instead of JSON)
            result[1],           # status_text
            result[2],           # shot_dropdown
            result[3],           # storyboard_state
            result[4],           # selection_summary
            result[5],           # selection_json
            result[6],           # selections_state
            result[7],           # variants_state
        )

    @handle_errors("Failed to load storyboard", return_tuple=True)
    def _load_storyboard_model(self, storyboard_file: str):
        storyboard = StoryboardService.load_from_config(self.config, storyboard_file)
        StoryboardService.apply_resolution_from_config(storyboard, self.config)
        storyboard.raw["storyboard_file"] = storyboard_file
        return storyboard

    def _format_selection_summary(self, selections: Dict[str, Dict[str, Any]], storyboard: Dict[str, Any]) -> str:
        return format_selection_summary(selections, storyboard)

    def load_storyboard(self, storyboard_file: str) -> Tuple[str, str, Any, Dict[str, Any], str, Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        if not storyboard_file or storyboard_file.startswith("No storyboard"):
            empty_summary = format_selection_summary({}, {})
            empty_preview = build_preview_payload({}, {})
            return (
                "{}",
                "**❌ Error:** No storyboard file selected",
                gr.update(choices=[]),
                {},
                empty_summary,
                empty_preview,
                {},
                {},
            )

        storyboard, error = self._load_storyboard_model(storyboard_file)
        if error:
            empty_summary = format_selection_summary({}, {})
            empty_preview = build_preview_payload({}, {})
            return (
                "{}",
                error,
                gr.update(choices=[]),
                {},
                empty_summary,
                empty_preview,
                {},
                {},
            )

        shots = storyboard.shots
        shot_ids = [shot.shot_id or f"{idx+1:03d}" for idx, shot in enumerate(shots)]
        dropdown_update = gr.update(choices=shot_ids, value=shot_ids[0] if shot_ids else None)
        project_name = storyboard.project or "Unknown Project"
        status = f"**✅ Storyboard loaded:** {project_name} – {len(shots)} Shots"
        storyboard_json = json.dumps(storyboard.raw, indent=2)
        summary = format_selection_summary({}, storyboard.raw)
        preview = build_preview_payload(storyboard.raw, {})

        return (
            storyboard_json,
            status,
            dropdown_update,
            storyboard.raw,
            summary,
            preview,
            {},
            {},
        )

    def load_storyboard_from_config(
        self
    ) -> Tuple[str, str, Any, Dict[str, Any], str, Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        """Wrapper to load storyboard selected in project tab.

        Refactored to use centralized StoryboardService.
        """
        self.config.refresh()
        storyboard_file = self.config.get_current_storyboard()
        if not storyboard_file:
            logger.warning("No storyboard selected in project tab")
            empty_summary = format_selection_summary({}, {})
            empty_preview = build_preview_payload({}, {})
            return (
                "{}",
                "**❌ Error:** No storyboard set. Please select in '📁 Project' tab.",
                gr.update(choices=[]),
                {},
                empty_summary,
                empty_preview,
                {},
                {},
            )
        return self.load_storyboard(storyboard_file)

    def load_shot_preview(
        self,
        storyboard_state: Dict[str, Any],
        shot_id: str,
        variants_state: Dict[str, Dict[str, Dict[str, Any]]],
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, List[Tuple[str, str]], Any, str, Dict[str, Dict[str, Dict[str, Any]]]]:
        """Load gallery + variant list for selected shot"""
        if not storyboard_state:
            return "Please load a storyboard first.", [], gr.update(choices=[]), "**❌ Error:** No storyboard", variants_state

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return (
                "No active project selected.",
                [],
                gr.update(choices=[]),
                "**❌ Error:** Please select a project in '📁 Project' tab first.",
                variants_state,
            )

        shot = self._get_shot_by_id(storyboard_state, shot_id)
        if not shot:
            return f"Shot `{shot_id}` not found.", [], gr.update(choices=[]), "**❌ Error:** Invalid shot", variants_state

        filename_base = shot.get("filename_base", shot_id)
        keyframes = self.selection_service.collect_keyframes(project, filename_base)

        if not keyframes:
            info = self._format_shot_markdown(shot, available=False)
            status = f"**⚠️ Note:** No keyframes found for `{filename_base}`."
            variants_state = variants_state or {}
            variants_state[shot_id] = {}
            return info, [], gr.update(choices=[], value=None), status, variants_state

        # Gradio 4.x format: list of (path, caption) tuples
        gallery_items = [(item["path"], item["label"]) for item in keyframes]

        options_map = {item["label"]: item for item in keyframes}
        variants_state = variants_state or {}
        variants_state[shot_id] = options_map

        existing_selection = selections_state.get(shot_id) if selections_state else None
        default_value = None
        if existing_selection:
            label_match = next(
                (label for label, data in options_map.items() if data["filename"] == existing_selection["selected_file"]),
                None,
            )
            default_value = label_match

        info = self._format_shot_markdown(shot, available=True, total=len(keyframes))
        status = f"**ℹ️ {shot_id}:** {len(keyframes)} Varianten loaded."

        return info, gallery_items, gr.update(choices=list(options_map.keys()), value=default_value), status, variants_state

    def _show_clear_confirm(
        self,
        shot_id: str,
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, Any]:
        """Show confirmation dialog for clearing selection."""
        if not shot_id:
            return "### ⚠️ No shot selected", gr.update(visible=False)

        if not selections_state or shot_id not in selections_state:
            return f"### ℹ️ No selection exists\n\nNo variant saved for shot `{shot_id}`.", gr.update(visible=False)

        entry = selections_state[shot_id]
        confirm_text = f"""### ⚠️ Remove variant?

**Shot:** `{shot_id}`
**Saved Variant:** `{entry.get('selected_file', 'Unknown')}`

The selection for this shot will be deleted."""
        return confirm_text, gr.update(visible=True)

    def save_selection(
        self,
        shot_id: str,
        selected_option: str,
        storyboard_state: Dict[str, Any],
        variants_state: Dict[str, Dict[str, Dict[str, Any]]],
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, str, Dict[str, Any], Dict[str, Dict[str, Any]], Any]:
        """Persist selected variant for a shot"""
        current_summary = format_selection_summary(selections_state, storyboard_state)
        current_preview = build_preview_payload(storyboard_state, selections_state)
        current_warning = self._get_selection_warning(selections_state, storyboard_state)

        if not shot_id:
            return "**❌ Error:** No shot selected.", current_summary, current_preview, selections_state, current_warning

        options = (variants_state or {}).get(shot_id, {})
        if not options:
            return f"**❌ Error:** No variants loaded for `{shot_id}`.", current_summary, current_preview, selections_state, current_warning

        # Check if user selected a variant
        if not selected_option:
            return (
                "**⚠️ Note:** Please select a variant from the list above first, "
                "before saving the selection.",
                current_summary,
                current_preview,
                selections_state,
                current_warning,
            )

        choice = options.get(selected_option)
        if not choice:
            return (
                "**⚠️ Note:** The selected variant is invalid. "
                "Please choose a variant from the 'Best Variant' list.",
                current_summary,
                current_preview,
                selections_state,
                current_warning,
            )

        shot = self._get_shot_by_id(storyboard_state, shot_id) or {}

        selection_record = {
            "shot_id": shot_id,
            "filename_base": shot.get("filename_base", shot_id),
            "selected_variant": choice["variant"],
            "selected_file": choice["filename"],
            "source_path": choice["path"],
        }

        selections_state = selections_state or {}
        selections_state[shot_id] = selection_record

        summary = format_selection_summary(selections_state, storyboard_state)
        preview = build_preview_payload(storyboard_state, selections_state)
        warning = self._get_selection_warning(selections_state, storyboard_state)

        status = f"**✅ Saved:** Shot {shot_id} → {choice['filename']}"
        return status, summary, preview, selections_state, warning

    def clear_selection(
        self,
        shot_id: str,
        storyboard_state: Dict[str, Any],
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, str, Dict[str, Any], Dict[str, Dict[str, Any]], Any, Any]:
        """Remove a saved selection for the active shot"""
        if not shot_id:
            return (
                "**❌ Error:** No shot selected.",
                format_selection_summary(selections_state, storyboard_state),
                build_preview_payload(storyboard_state, selections_state),
                selections_state,
                self._get_selection_warning(selections_state, storyboard_state),
                gr.update(visible=False),
            )

        if selections_state and shot_id in selections_state:
            selections_state.pop(shot_id, None)
            status = f"**🗑️ Removed:** Selection for shot {shot_id} deleted."
        else:
            status = f"**ℹ️ Note:** No saved selection for shot {shot_id}."

        summary = format_selection_summary(selections_state, storyboard_state)
        preview = build_preview_payload(storyboard_state, selections_state)
        warning = self._get_selection_warning(selections_state, storyboard_state)
        return status, summary, preview, selections_state, warning, gr.update(visible=False)

    def export_selections(
        self,
        storyboard_state: Dict[str, Any],
        selections_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[str, Dict[str, Any], Any]:
        """Write JSON export + copy files into the active project/selected folder"""
        no_warning = gr.update(visible=False)

        if not storyboard_state:
            return "**❌ Error:** Please load a storyboard first.", {}, no_warning

        if not selections_state:
            return "**❌ Error:** No selections saved.", {}, self._get_selection_warning(selections_state, storyboard_state)

        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return "**❌ Error:** No active project. Please select one in the '📁 Project' tab.", {}, no_warning

        # Check for incomplete selection before export
        total_shots = len(storyboard_state.get("shots", []))
        selected_shots = len(selections_state)
        if selected_shots < total_shots:
            missing = total_shots - selected_shots
            return (
                f"**⚠️ Warning:** Only {selected_shots} of {total_shots} shots selected. "
                f"Please select all shots or force export.",
                build_preview_payload(storyboard_state, selections_state),
                self._get_selection_warning(selections_state, storyboard_state),
            )

        export_payload = self.selection_service.export_selections(project, storyboard_state, selections_state)
        copied = export_payload.pop("_copied", 0)
        export_path = export_payload.pop("_path", "n/a")
        status = (
            f"**✅ Export complete:** {len(export_payload.get('selections', []))} shots, "
            f"{copied} files copied → `{export_path}`"
        )
        return status, export_payload, gr.update(visible=False, value="")

    def _format_shot_markdown(self, shot: Dict[str, Any], available: bool, total: int = 0) -> str:
        """Readable shot metadata block"""
        lines = [
            f"### Shot {shot.get('shot_id', 'N/A')} – {shot.get('filename_base', 'no filename')}",
            f"- **Description:** {shot.get('description', 'No description')}",
            f"- **Prompt:** {shot.get('prompt', 'No prompt')[:160]}{'…' if len(shot.get('prompt', '')) > 160 else ''}",
            f"- **Resolution:** {shot.get('width', 1024)}×{shot.get('height', 576)}",
            f"- **Camera:** {shot.get('camera_movement', 'n/a')}",
        ]
        if available:
            lines.append(f"- **Variants found:** {total}")
        else:
            lines.append("- **Variants found:** 0")
        return "\n".join(lines)

    def _get_available_storyboards(self) -> List[str]:
        """List storyboard files from config/ and active project folders"""
        directories = self._storyboard_search_dirs()
        storyboards: List[str] = []
        seen = set()

        for directory in directories:
            if not os.path.exists(directory):
                continue
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

    def _get_default_storyboard(self) -> str:
        storyboards = self._get_available_storyboards()
        return storyboards[0] if storyboards else None

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

    def _get_shot_by_id(self, storyboard: Dict[str, Any], shot_id: str) -> Dict[str, Any]:
        for shot in storyboard.get("shots", []):
            if shot.get("shot_id") == shot_id:
                return shot
        return {}

    def _get_selection_warning(
        self, selections: Dict[str, Dict[str, Any]], storyboard: Dict[str, Any]
    ) -> Any:
        """Return warning component if selection is incomplete."""
        if not storyboard:
            return gr.update(visible=False)

        total_shots = len(storyboard.get("shots", []))
        selected_shots = len(selections) if selections else 0

        if selected_shots < total_shots:
            missing = total_shots - selected_shots
            # Find which shots are missing
            all_shot_ids = {s.get("shot_id") for s in storyboard.get("shots", [])}
            selected_ids = set(selections.keys()) if selections else set()
            missing_ids = sorted(all_shot_ids - selected_ids)
            missing_list = ", ".join(missing_ids[:5])
            if len(missing_ids) > 5:
                missing_list += f" (+{len(missing_ids) - 5} more)"

            warning_text = (
                f"**⚠️ Incomplete Selection**\n\n"
                f"{missing} of {total_shots} shots missing:\n"
                f"`{missing_list}`"
            )
            return gr.update(visible=True, value=warning_text)

        return gr.update(visible=False, value="")

    # Removed: _apply_global_resolution() - now using StoryboardService.apply_resolution_from_config()


__all__ = ["KeyframeSelectorAddon"]
