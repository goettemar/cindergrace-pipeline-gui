"""Storyboard Manager Addon - Manage storyboard files for the active project."""
import os
from typing import List, Tuple, Optional
import gradio as gr

from addons.base_addon import BaseAddon
from addons.components import (
    create_delete_confirm,
    create_folder_scanner,
    create_storyboard_preview,
    project_status_md,
)
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.logger import get_logger
from infrastructure.error_handler import handle_errors
from domain.storyboard_service import StoryboardService
from services.storyboard_editor_service import StoryboardEditorService

logger = get_logger(__name__)


class StoryboardManagerAddon(BaseAddon):
    """Manage storyboard files: create, load, delete, set active."""

    def __init__(self):
        super().__init__(
            name="Storyboard Manager",
            description="Manage storyboard files in the active project",
            category="project"
        )
        self.config = ConfigManager()
        self.project_store = ProjectStore(self.config)
        self.editor_service = StoryboardEditorService()

    def get_tab_name(self) -> str:
        return "📚 Boards"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Unified header: Tab name left, project status right
            project_status = gr.HTML(project_status_md(self.project_store, "📚 Storyboards"))

            gr.Markdown("Create, load and manage storyboards for the active project.")

            with gr.Row():
                # Left Column: Storyboard Liste (60%)
                with gr.Column(scale=3):
                    with gr.Group():
                        gr.Markdown("### 📁 Storyboards in Project")

                        # Storyboard scanner
                        storyboard_scanner = create_folder_scanner(
                            label="Storyboard select",
                            choices=self._get_storyboard_choices(),
                            value=self._get_current_storyboard_filename(),
                            info="Storyboards in project folder"
                        )
                        storyboard_dropdown = storyboard_scanner.dropdown
                        refresh_btn = storyboard_scanner.refresh_btn

                        # Current storyboard info
                        current_sb_info = gr.Markdown(self._get_current_storyboard_info())

                        with gr.Row():
                            load_btn = gr.Button("📂 Set as Active", variant="primary")
                            open_editor_btn = gr.Button("📝 Open in Editor", variant="secondary")

                    # Storyboard Details
                    preview_ui = create_storyboard_preview(
                        initial_value=self._get_storyboard_preview()
                    )
                    storyboard_preview = preview_ui.code

                # Right Column: Aktionen (40%)
                with gr.Column(scale=2):
                    # Create new storyboard
                    with gr.Group():
                        gr.Markdown("### 🆕 New Storyboard")
                        new_name = gr.Textbox(
                            label="Name",
                            placeholder="storyboard_main",
                            info="Name without .json extension"
                        )
                        create_btn = gr.Button("🆕 Create", variant="primary")

                    # Delete storyboard
                    with gr.Group():
                        gr.Markdown("### 🗑️ Delete")
                        delete_ui = create_delete_confirm(
                            trigger_label="🗑️ Delete Selected Storyboard",
                            confirm_title="### ⚠️ Really delete storyboard?",
                            confirm_warning="This action cannot be undone!",
                        )

            # Status
            status_box = gr.Markdown("")

            # === Event Handlers ===

            # Refresh dropdown
            refresh_btn.click(
                fn=self._refresh_storyboard_list,
                outputs=[storyboard_dropdown, current_sb_info]
            )

            # Load/set active storyboard
            load_btn.click(
                fn=self._set_active_storyboard,
                inputs=[storyboard_dropdown],
                outputs=[status_box, current_sb_info, storyboard_preview, project_status]
            )

            # Preview storyboard on selection change
            storyboard_dropdown.change(
                fn=self._on_storyboard_select,
                inputs=[storyboard_dropdown],
                outputs=[storyboard_preview]
            )

            # Create new storyboard
            create_btn.click(
                fn=self._create_storyboard,
                inputs=[new_name],
                outputs=[status_box, storyboard_dropdown, current_sb_info, storyboard_preview, project_status]
            )

            # Delete storyboard - show confirm
            delete_ui.trigger_btn.click(
                fn=self._show_delete_confirm,
                inputs=[storyboard_dropdown],
                outputs=[delete_ui.confirm_text, delete_ui.confirm_group]
            )

            # Delete storyboard - cancel
            delete_ui.cancel_btn.click(
                fn=lambda: gr.update(visible=False),
                outputs=[delete_ui.confirm_group]
            )

            # Delete storyboard - confirm
            delete_ui.confirm_btn.click(
                fn=self._delete_storyboard,
                inputs=[storyboard_dropdown],
                outputs=[status_box, storyboard_dropdown, current_sb_info, storyboard_preview, delete_ui.confirm_group, project_status]
            )

            # Refresh on tab load
            interface.load(
                fn=self._on_tab_load,
                outputs=[project_status, storyboard_dropdown, current_sb_info, storyboard_preview]
            )

        return interface

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

    def _get_current_storyboard_info(self) -> str:
        """Get info about the currently active storyboard."""
        current_sb = self.config.get_current_storyboard()
        if not current_sb or not os.path.exists(current_sb):
            return "**Active:** *No storyboard selected*"

        filename = os.path.basename(current_sb)
        try:
            storyboard = StoryboardService.load_from_file(current_sb)
            shot_count = len(storyboard.shots)
            total_duration = sum(float(shot.duration) for shot in storyboard.shots)
            return f"**Active:** `{filename}` – {shot_count} shots, {total_duration:.1f}s"
        except Exception:
            return f"**Active:** `{filename}`"

    def _get_storyboard_preview(self, filename: Optional[str] = None) -> str:
        """Get JSON preview of a storyboard."""
        if filename is None:
            filename = self._get_current_storyboard_filename()

        if not filename:
            return "{}"

        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return "{}"

        storyboard_dir = self.project_store.ensure_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, filename)

        if not os.path.exists(file_path):
            return "{}"

        try:
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            return "{}"

    def _on_tab_load(self) -> Tuple:
        """Refresh data when tab loads."""
        self.config.refresh()
        return (
            project_status_md(self.project_store, "📚 Storyboards"),
            gr.Dropdown(
                choices=self._get_storyboard_choices(),
                value=self._get_current_storyboard_filename()
            ),
            self._get_current_storyboard_info(),
            self._get_storyboard_preview()
        )

    def _refresh_storyboard_list(self) -> Tuple:
        """Refresh storyboard dropdown and info."""
        self.config.refresh()
        choices = self._get_storyboard_choices()
        current = self._get_current_storyboard_filename()
        return (
            gr.Dropdown(choices=choices, value=current if current in choices else None),
            self._get_current_storyboard_info()
        )

    def _on_storyboard_select(self, filename: str) -> str:
        """Update preview when storyboard is selected."""
        return self._get_storyboard_preview(filename)

    @handle_errors("Could not activate storyboard")
    def _set_active_storyboard(self, filename: str) -> Tuple:
        """Set a storyboard as active."""
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return (
                "❌ No active project",
                self._get_current_storyboard_info(),
                "{}",
                project_status_md(self.project_store, "📚 Storyboards")
            )

        if not filename:
            return (
                "❌ No storyboard selected",
                self._get_current_storyboard_info(),
                self._get_storyboard_preview(),
                project_status_md(self.project_store, "📚 Storyboards")
            )

        storyboard_dir = self.project_store.ensure_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, filename)

        if not os.path.exists(file_path):
            return (
                f"❌ File not found: {filename}",
                self._get_current_storyboard_info(),
                "{}",
                project_status_md(self.project_store, "📚 Storyboards")
            )

        # Set as active storyboard
        self.project_store.set_project_storyboard(project, file_path, set_as_default=True)
        logger.info(f"Set active storyboard: {filename}")

        return (
            f"✅ Active storyboard: {filename}",
            self._get_current_storyboard_info(),
            self._get_storyboard_preview(filename),
            project_status_md(self.project_store, "📚 Storyboards")
        )

    @handle_errors("Could not create storyboard")
    def _create_storyboard(self, name: str) -> Tuple:
        """Create a new storyboard."""
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return (
                "❌ No active project",
                gr.Dropdown(),
                self._get_current_storyboard_info(),
                "{}",
                project_status_md(self.project_store, "📚 Storyboards")
            )

        if not name:
            name = "storyboard_main"

        if not name.endswith(".json"):
            name += ".json"

        # Create new storyboard
        storyboard = self.editor_service.create_new_storyboard(project["name"])
        storyboard_dir = self.project_store.ensure_storyboard_dir(project)
        file_path = os.path.join(storyboard_dir, name)

        # Check if file already exists
        if os.path.exists(file_path):
            return (
                f"❌ Storyboard already exists: {name}",
                gr.Dropdown(choices=self._get_storyboard_choices(), value=name),
                self._get_current_storyboard_info(),
                self._get_storyboard_preview(name),
                project_status_md(self.project_store, "📚 Storyboards")
            )

        # Save and set as active
        StoryboardService.save_storyboard(storyboard, file_path)
        self.project_store.set_project_storyboard(project, file_path, set_as_default=True)
        logger.info(f"Created storyboard: {name}")

        return (
            f"✅ Storyboard created: {name}",
            gr.Dropdown(choices=self._get_storyboard_choices(), value=name),
            self._get_current_storyboard_info(),
            self._get_storyboard_preview(name),
            project_status_md(self.project_store, "📚 Storyboards")
        )

    def _show_delete_confirm(self, filename: str) -> Tuple:
        """Show delete confirmation dialog."""
        if not filename:
            return "### ⚠️ No storyboard selected", gr.update(visible=False)

        confirm_text = f"""### ⚠️ Really delete storyboard?

**File:** `{filename}`

This action cannot be undone!
"""
        return confirm_text, gr.update(visible=True)

    @handle_errors("Could not delete storyboard")
    def _delete_storyboard(self, filename: str) -> Tuple:
        """Delete a storyboard file."""
        project = self.project_store.get_active_project(refresh=True)
        if not project:
            return (
                "❌ No active project",
                gr.Dropdown(),
                self._get_current_storyboard_info(),
                "{}",
                gr.update(visible=False),
                project_status_md(self.project_store, "📚 Storyboards")
            )

        if not filename:
            return (
                "❌ No storyboard selected",
                gr.Dropdown(choices=self._get_storyboard_choices()),
                self._get_current_storyboard_info(),
                self._get_storyboard_preview(),
                gr.update(visible=False),
                project_status_md(self.project_store, "📚 Storyboards")
            )

        success = self.project_store.delete_storyboard(project, filename)

        if success:
            logger.info(f"Deleted storyboard: {filename}")
            choices = self._get_storyboard_choices()
            current = self._get_current_storyboard_filename()
            return (
                f"✅ Storyboard deleted: {filename}",
                gr.Dropdown(choices=choices, value=current),
                self._get_current_storyboard_info(),
                self._get_storyboard_preview(),
                gr.update(visible=False),
                project_status_md(self.project_store, "📚 Storyboards")
            )
        else:
            return (
                f"❌ Could not delete: {filename}",
                gr.Dropdown(choices=self._get_storyboard_choices()),
                self._get_current_storyboard_info(),
                self._get_storyboard_preview(),
                gr.update(visible=False),
                project_status_md(self.project_store, "📚 Storyboards")
            )


__all__ = ["StoryboardManagerAddon"]
