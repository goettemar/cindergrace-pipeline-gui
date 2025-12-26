"""Shared UI components for CINDERGRACE addons.

This module provides reusable Gradio UI patterns that appear across
multiple addons, reducing code duplication and ensuring consistency.
"""

from addons.components.delete_confirm import (
    DeleteConfirmComponents,
    create_delete_confirm,
)
from addons.components.folder_scanner import (
    FolderScannerComponents,
    create_folder_scanner,
    create_refresh_handler,
    create_refresh_handler_with_value,
)
from addons.components.status_log import (
    StatusLogComponents,
    create_status_log,
    append_status,
    clear_status,
)
from addons.components.project_status_bar import (
    ProjectStatusBarComponents,
    create_project_status_bar,
    format_project_status,
    format_project_status_from_dict,
    format_project_status_extended,
    project_status_md,
    storyboard_status_md,
    shorten_storyboard_path,
)
from addons.components.storyboard_preview import (
    StoryboardPreviewComponents,
    create_storyboard_preview,
)
from addons.components.storyboard_section import (
    StoryboardSection,
    create_storyboard_section,
)
from addons.components.log_panel import (
    LogPanelUI,
    create_log_panel,
)
from addons.components.resolution_guide import (
    ResolutionGuideComponents,
    create_resolution_guide,
    get_resolution_guide_content,
)

__all__ = [
    # Delete confirmation
    "DeleteConfirmComponents",
    "create_delete_confirm",
    # Folder scanner
    "FolderScannerComponents",
    "create_folder_scanner",
    "create_refresh_handler",
    "create_refresh_handler_with_value",
    # Status log
    "StatusLogComponents",
    "create_status_log",
    "append_status",
    "clear_status",
    # Project status bar
    "ProjectStatusBarComponents",
    "create_project_status_bar",
    "format_project_status",
    "format_project_status_from_dict",
    "format_project_status_extended",
    "project_status_md",
    "storyboard_status_md",
    "shorten_storyboard_path",
    # Storyboard section
    "StoryboardSection",
    "create_storyboard_section",
    # Storyboard preview
    "StoryboardPreviewComponents",
    "create_storyboard_preview",
    # Log panel
    "LogPanelUI",
    "create_log_panel",
    # Resolution guide
    "ResolutionGuideComponents",
    "create_resolution_guide",
    "get_resolution_guide_content",
]
