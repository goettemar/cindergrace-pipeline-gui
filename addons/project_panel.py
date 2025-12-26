"""Project selection/creation addon."""
import os
import sys
from typing import Dict, List, Optional

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import (
    create_delete_confirm,
    create_status_log,
    append_status,
    format_project_status_extended,
    project_status_md,
    create_resolution_guide,
)
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.error_handler import handle_errors
from infrastructure.logger import get_logger
from domain.validators import ProjectCreateInput

logger = get_logger(__name__)


class ProjectAddon(BaseAddon):
    """Tab to create/select active pipeline projects."""

    def __init__(self):
        super().__init__(
            name="Project Manager",
            description="Manage CINDERGRACE project folders under ComfyUI/output",
            category="project"
        )
        self.config = ConfigManager()
        self.project_manager = ProjectStore(self.config)

    def get_tab_name(self) -> str:
        return "📁 Project"

    def render(self) -> gr.Blocks:
        project = self.project_manager.get_active_project(refresh=True)
        valid_path = self._is_comfy_path_valid()
        has_projects = len(self._project_choices()) > 0

        with gr.Blocks() as interface:
            # Unified header: Tab name left, project status right
            project_status = gr.HTML(format_project_status_extended(
                self.project_manager, self.config, "📁 Project Manager"
            ))

            gr.Markdown(
                "Create or load a project. "
                "Each project stores your keyframes and videos in its own folder."
            )

            # Warning if ComfyUI path is missing
            warning_box = gr.Markdown(
                "## ⚠️ ComfyUI path not configured\n\n"
                "Please set the path to ComfyUI in the **Settings tab** first.",
                visible=not valid_path,
                elem_classes=["warning-box"],
            )

            # Hint if no project exists (dynamically show/hide)
            no_project_hint = gr.Markdown(
                "## 📋 No project yet\n\n"
                "Create your first project to get started. "
                "Enter a name on the left and click **Create Project**.",
                visible=not has_projects and valid_path,
                elem_classes=["info-box"],
            )

            # Main area
            with gr.Row():
                # === LEFT COLUMN: Create & load project ===
                with gr.Column(scale=1):
                    # Create project
                    gr.Markdown("### Create Project")
                    new_name = gr.Textbox(
                        label="Project Name",
                        placeholder="e.g. my-music-video",
                        interactive=valid_path,
                    )
                    create_btn = gr.Button(
                        "🚀 Create Project",
                        variant="primary",
                        interactive=valid_path,
                        size="lg",
                    )

                    gr.Markdown("---")

                    # Load project
                    gr.Markdown("### Load Project")
                    with gr.Row():
                        project_dropdown = gr.Dropdown(
                            choices=self._project_choices(),
                            value=project["slug"] if project else None,
                            label="Existing Project",
                            scale=8,
                            interactive=valid_path and has_projects,
                        )
                        refresh_btn = gr.Button(
                            "↻",
                            variant="secondary",
                            interactive=valid_path,
                            scale=1,
                            min_width=42,
                        )
                    load_btn = gr.Button(
                        "📂 Load Project",
                        variant="primary",
                        interactive=valid_path and has_projects,
                    )

                    gr.Markdown("---")

                    # Delete project - with shared Component
                    gr.Markdown("### Delete Active Project")
                    delete_ui = create_delete_confirm(
                        trigger_label="🗑️ Delete Active Project",
                        confirm_warning="All project files will be permanently deleted!",
                    )
                    # Set initial interactive state
                    delete_ui.trigger_btn.interactive = valid_path and project is not None

                # === RIGHT COLUMN: Active Project & Settings ===
                with gr.Column(scale=1):
                    gr.Markdown("### Active Project")
                    with gr.Group():
                        project_summary = gr.Markdown(self._project_summary(project))

                    gr.Markdown("---")

                    # Settings
                    gr.Markdown("### Settings")
                    resolution_dropdown = gr.Dropdown(
                        choices=self._resolution_choices(),
                        value=self.config.get_resolution_preset(),
                        label="Global Resolution",
                        info="16:9 = Landscape (YouTube, TV) · 9:16 = Portrait (TikTok, Reels)",
                        interactive=valid_path,
                    )
                    # Resolution guide - collapsible info panel
                    create_resolution_guide(open_by_default=False)

                    sage_checkbox = gr.Checkbox(
                        value=self.config.use_sage_attention(),
                        label="⚡ Enable SageAttention",
                        info="Faster inference on compatible GPUs (RTX 30xx+, CUDA 12.0+). Workflows with _sage.json suffix are automatically used.",
                        interactive=valid_path,
                    )
                    save_btn = gr.Button(
                        "💾 Save Project",
                        variant="primary",
                        interactive=valid_path and project is not None,
                    )

            # Status / Actions Log - with shared Component
            gr.Markdown("### Status / Actions")
            status = create_status_log(lines=6, max_lines=8)

            # === Event Handlers ===
            refresh_btn.click(
                fn=self._refresh_projects,
                inputs=[status.textbox],
                outputs=[project_dropdown, load_btn, status.textbox],
            )

            load_btn.click(
                fn=self._load_project,
                inputs=[project_dropdown, status.textbox],
                outputs=[
                    project_summary,
                    project_dropdown,
                    save_btn,
                    delete_ui.trigger_btn,
                    status.textbox,
                ],
            )

            create_btn.click(
                fn=self._create_project,
                inputs=[new_name, status.textbox],
                outputs=[
                    project_summary,
                    project_dropdown,
                    new_name,
                    load_btn,
                    save_btn,
                    no_project_hint,
                    status.textbox,
                ],
            )

            save_btn.click(
                fn=self._save_settings,
                inputs=[resolution_dropdown, sage_checkbox, status.textbox],
                outputs=[project_summary, status.textbox],
            )

            # Delete: Show confirmation first
            delete_ui.trigger_btn.click(
                fn=self._show_delete_confirm,
                inputs=[],
                outputs=[delete_ui.confirm_text, delete_ui.confirm_group],
            )

            # Delete: Cancel
            delete_ui.cancel_btn.click(
                fn=lambda: gr.update(visible=False),
                outputs=[delete_ui.confirm_group],
            )

            # Delete: Confirm and delete
            delete_ui.confirm_btn.click(
                fn=self._delete_project,
                inputs=[status.textbox],
                outputs=[
                    project_summary,
                    project_dropdown,
                    load_btn,
                    delete_ui.trigger_btn,
                    save_btn,
                    delete_ui.confirm_group,
                    no_project_hint,
                    status.textbox,
                ],
            )

            # Refresh project status on tab load
            interface.load(
                fn=self._on_tab_load,
                outputs=[project_status]
            )

        return interface

    def _on_tab_load(self):
        """Refresh project status when tab loads."""
        self.config.refresh()
        return project_status_md(self.project_manager, "📁 Project Manager")

    # -----------------------------
    # UI callbacks
    # -----------------------------
    def _refresh_projects(self, current_status: str):
        choices = self._project_choices()
        project = self.project_manager.get_active_project(refresh=True)
        has_projects = len(choices) > 0
        new_status = append_status(
            current_status, f"Project list updated ({len(choices)} projects)"
        )
        return (
            gr.update(choices=choices, value=project["slug"] if project else None),
            gr.update(interactive=has_projects),
            new_status,
        )

    def _load_project(self, slug: Optional[str], current_status: str):
        if not slug:
            project = self.project_manager.get_active_project(refresh=True)
            return (
                self._project_summary(project),
                gr.update(value=project["slug"] if project else None),
                gr.update(interactive=project is not None),  # save_btn
                gr.update(interactive=project is not None),  # delete_btn
                append_status(current_status, "❌ Please select a project."),
            )

        project = self.project_manager.set_active_project(slug)
        if not project:
            return (
                self._project_summary(None),
                gr.update(choices=self._project_choices(), value=None),
                gr.update(interactive=False),  # save_btn
                gr.update(interactive=False),  # delete_btn
                append_status(current_status, f"❌ Project `{slug}` not found."),
            )

        return (
            self._project_summary(project),
            gr.update(value=project["slug"]),
            gr.update(interactive=True),  # save_btn
            gr.update(interactive=True),  # delete_btn
            append_status(current_status, f"✅ Project loaded: {project['name']}"),
        )

    @handle_errors("Could not create project")
    def _create_project(self, name: str, current_status: str):
        logger.info(f"Creating new project: {name}")

        # Validate input with Pydantic
        validated = ProjectCreateInput(name=name)
        validated_name = validated.name

        project = self.project_manager.create_project(validated_name)
        logger.info(f"✓ Project created: {project['name']} ({project['slug']})")

        choices = self._project_choices()
        return (
            self._project_summary(project),
            gr.update(choices=choices, value=project["slug"]),
            "",  # Clear input
            gr.update(interactive=True),  # Enable load button
            gr.update(interactive=True),  # Enable save button
            gr.update(visible=False),  # Hide no_project_hint
            append_status(current_status, f"✅ Project created: {project['name']}"),
        )

    def _save_settings(self, resolution_key: str, use_sage: bool, current_status: str):
        """Save project settings (resolution, SageAttention)."""
        project = self.project_manager.get_active_project(refresh=True)

        # Check if resolution_key is valid (extract values from tuples)
        valid_keys = [value for _, value in self._resolution_choices()]
        if resolution_key not in valid_keys:
            return (
                self._project_summary(project),
                append_status(current_status, "❌ Invalid resolution."),
            )

        self.config.set("global_resolution", resolution_key)
        self.config.set("use_sage_attention", use_sage)
        self.config.save()

        res_label = self._resolution_label(resolution_key)
        sage_label = "activated" if use_sage else "deactivated"
        return (
            self._project_summary(project),
            append_status(current_status, f"✅ Settings saved: {res_label}, SageAttention {sage_label}"),
        )

    def _show_delete_confirm(self):
        """Show delete confirmation dialog for active project."""
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return (
                "### ⚠️ No active project",
                gr.update(visible=False),
            )

        project_name = project.get("name", project.get("slug", "?"))
        slug = project.get("slug", "?")

        confirm_text = f"""### ⚠️ Really delete active project?

**Project:** {project_name} (`{slug}`)

**Warning:** All project files (keyframes, videos, etc.) will be permanently deleted!
"""
        return confirm_text, gr.update(visible=True)

    def _delete_project(self, current_status: str):
        """Delete the active project after confirmation."""
        project = self.project_manager.get_active_project(refresh=True)
        if not project:
            return (
                self._project_summary(None),
                gr.update(choices=self._project_choices(), value=None),
                gr.update(interactive=False),  # load_btn
                gr.update(interactive=False),  # delete_btn
                gr.update(interactive=False),  # save_btn
                gr.update(visible=False),  # delete_confirm_group
                gr.update(visible=True),  # no_project_hint
                append_status(current_status, "❌ No active project."),
            )

        slug = project.get("slug")
        project_name = project.get("name", slug)

        success = self.project_manager.delete_project(slug)

        if success:
            choices = self._project_choices()
            has_projects = len(choices) > 0
            new_project = self.project_manager.get_active_project(refresh=True)

            return (
                self._project_summary(new_project),
                gr.update(choices=choices, value=new_project["slug"] if new_project else None),
                gr.update(interactive=has_projects),  # load_btn
                gr.update(interactive=new_project is not None),  # delete_btn
                gr.update(interactive=new_project is not None),  # save_btn
                gr.update(visible=False),  # delete_confirm_group
                gr.update(visible=not has_projects),  # no_project_hint
                append_status(current_status, f"✅ Project deleted: {project_name}"),
            )
        else:
            return (
                self._project_summary(project),
                gr.update(value=slug),
                gr.update(),  # load_btn
                gr.update(),  # delete_btn
                gr.update(),  # save_btn
                gr.update(visible=False),  # delete_confirm_group
                gr.update(visible=False),  # no_project_hint
                append_status(current_status, f"❌ Could not delete project: {project_name}"),
            )

    # -----------------------------
    # Helper methods
    # -----------------------------
    def _project_choices(self) -> List[str]:
        return [entry["slug"] for entry in self.project_manager.list_projects()]

    def _resolution_choices(self) -> List[tuple]:
        """Return resolution choices as (label, value) tuples for Gradio dropdown.

        Wan 2.2 only supports 480p, 720p and 1080p (16:9 or 9:16).
        LTX-Video supports flexible resolutions (divisible by 32).
        Square resolutions (512, 1024) are for SDXL/LTX use cases.
        """
        return [
            # Wan 2.2 compatible (16:9 / 9:16 only)
            ("1280×720 – Landscape (16:9) [Recommended]", "720p_landscape"),
            ("720×1280 – Portrait (9:16)", "720p_portrait"),
            ("832×480 – Landscape (16:9)", "480p_landscape"),
            ("480×832 – Portrait (9:16)", "480p_portrait"),
            ("1920×1080 – Landscape (16:9) [High VRAM]", "1080p_landscape"),
            ("1080×1920 – Portrait (9:16) [High VRAM]", "1080p_portrait"),
            # LTX-Video / SDXL compatible (flexible)
            ("768×512 – Landscape (3:2) [LTX Low VRAM]", "ltx_768x512"),
            ("512×768 – Portrait (2:3) [LTX Low VRAM]", "ltx_512x768"),
            ("512×512 – Square (1:1) [SDXL/LTX]", "512_square"),
            ("1024×1024 – Square (1:1) [SDXL Native]", "1024_square"),
        ]

    def _resolution_label(self, key: str) -> str:
        """Get display label for resolution key."""
        labels = {
            "720p_landscape": "1280×720 (Landscape)",
            "720p_portrait": "720×1280 (Portrait)",
            "480p_landscape": "832×480 (Landscape)",
            "480p_portrait": "480×832 (Portrait)",
            "1080p_landscape": "1920×1080 (Landscape)",
            "1080p_portrait": "1080×1920 (Portrait)",
            "512_square": "512×512 (Square)",
            "1024_square": "1024×1024 (Square)",
            # LTX-Video presets
            "ltx_768x512": "768×512 (LTX Low VRAM)",
            "ltx_512x768": "512×768 (LTX Portrait)",
            # Legacy support
            "540p_landscape": "960×540 (Landscape) [Not recommended]",
            "540p_portrait": "540×960 (Portrait) [Not recommended]",
            "test_square": "512×512 (Test)",
        }
        return labels.get(key, key)

    def _project_summary(self, project: Optional[Dict[str, str]]) -> str:
        """Formatted project summary for display."""
        if not project:
            return (
                "**No project selected**\n\n"
                "Create a new project or load an existing one."
            )

        name = project.get("name", "-")
        slug = project.get("slug", "-")
        path = project.get("path", "-")
        created = project.get("created_at", "-")
        if created and "T" in created:
            created = created.split("T")[0]
        last_opened = project.get("last_opened", "-")
        if last_opened and "T" in last_opened:
            last_opened = last_opened.split("T")[0]

        # Path status check
        path_exists = path and os.path.isdir(path)
        status_badge = "✅" if path_exists else "⚠️"

        # Resolution from config
        self.config.refresh()
        res_key = self.config.get_resolution_preset()
        res_label = self._resolution_label(res_key)

        return f"""| | |
|---|---|
| **Project** | {status_badge} **{name}** |
| **Resolution** | {res_label} |
| **Path** | `{path}` |
| **Created** | {created} |
| **Last opened** | {last_opened} |
"""

    def _is_comfy_path_valid(self) -> bool:
        path = self.config.get_comfy_root()
        return bool(path) and os.path.exists(path)

__all__ = ["ProjectAddon"]
