"""Project Status Bar Component - Unified project status display.

This component provides a standardized, compact project status bar
that can be used consistently across all addon tabs. Features:
- Tab name with icon on the left
- Active project status on the right
- Flexbox layout (space-between)
"""

import os
from typing import NamedTuple, Optional, List, Tuple
import gradio as gr


class ProjectStatusBarComponents(NamedTuple):
    """Container for project status bar UI elements.

    Attributes:
        status_bar: Markdown/HTML element displaying the tab header and project status
        refresh_btn: Optional refresh button (None if show_refresh=False)
    """

    status_bar: gr.HTML
    refresh_btn: Optional[gr.Button]


def format_project_status(
    project_name: Optional[str] = None,
    project_slug: Optional[str] = None,
    tab_name: Optional[str] = None,
    extra_info: Optional[List[Tuple[str, str]]] = None,
    show_path: bool = False,
    project_path: Optional[str] = None,
    no_project_relation: bool = False,
    include_remote_warning: bool = False,
) -> str:
    """Format project status as a unified header bar with flexbox layout.

    Creates a header bar with tab name on the left and project status on the right.

    Args:
        project_name: Project display name (e.g., "cindergrace_test")
        project_slug: Project slug/ID (e.g., "cindergrace_test")
        tab_name: Tab name with icon (e.g., "🎥 Video Generator")
        extra_info: List of (label, value) tuples for additional info
                   Example: [("Storyboard", "main.json (5 Shots)")]
        show_path: Whether to show the project path
        project_path: Path to the project directory
        no_project_relation: If True, show "kein Bezug" instead of project status

    Returns:
        HTML string with flexbox layout

    Examples:
        >>> format_project_status("My Project", "my_project", tab_name="🎥 Video Generator")
        '<div style="...">🎥 Video Generator</div><div>✅ Project: My Project</div>'

        >>> format_project_status(None, None, tab_name="📁 Project")
        '<div style="...">📁 Project</div><div>⚠️ No Project</div>'

        >>> format_project_status(tab_name="⚙️ Settings", no_project_relation=True)
        '<div style="...">⚙️ Settings</div><div>Project: no relation</div>'
    """
    # Build project status (right side)
    if no_project_relation:
        project_status = "Project: no relation"
    elif not project_name and not project_slug:
        project_status = "⚠️ No Project"
    else:
        name_display = project_name or project_slug or "Unknown"
        parts = [f"✅ Project: {name_display}"]

        # Add path if requested
        if show_path and project_path:
            parts.append(f"Path: {project_path}")

        # Add extra info
        if extra_info:
            for label, value in extra_info:
                if value:
                    parts.append(f"{label}: {value}")

        project_status = " │ ".join(parts)

    remote_label = _get_remote_backend_label() if include_remote_warning else ""
    if remote_label:
        project_status = f"{project_status} │ {remote_label}"

    # Build tab name (left side)
    tab_display = tab_name or ""

    # Return flexbox HTML with better visibility
    return f'''<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%); border-radius: 8px; margin-bottom: 16px; border: 1px solid #4a5568;">
  <div style="font-size: 1.4em; font-weight: 700; color: #f7fafc;">{tab_display}</div>
  <div style="font-size: 1.0em; font-weight: 500; color: #a0aec0; background: rgba(255,255,255,0.1); padding: 4px 12px; border-radius: 4px;">{project_status}</div>
</div>'''


def format_project_status_from_dict(
    project: Optional[dict],
    tab_name: Optional[str] = None,
    extra_info: Optional[List[Tuple[str, str]]] = None,
    show_path: bool = False,
    include_remote_warning: bool = False,
) -> str:
    """Format project status from a project dictionary.

    Convenience wrapper for format_project_status that extracts
    values from a project dictionary.

    Args:
        project: Project dictionary with 'name', 'slug', 'path' keys
        tab_name: Tab name with icon (e.g., "🎥 Video Generator")
        extra_info: Additional info tuples
        show_path: Whether to show the path

    Returns:
        Formatted HTML string
    """
    if not project:
        return format_project_status(
            None,
            None,
            tab_name=tab_name,
            include_remote_warning=include_remote_warning,
        )

    return format_project_status(
        project_name=project.get("name"),
        project_slug=project.get("slug"),
        tab_name=tab_name,
        extra_info=extra_info,
        show_path=show_path,
        project_path=project.get("path"),
        include_remote_warning=include_remote_warning,
    )


def create_project_status_bar(
    initial_status: str = "",
    tab_name: Optional[str] = None,
    show_refresh: bool = False,
    refresh_label: str = "↻",
    refresh_min_width: int = 42,
) -> ProjectStatusBarComponents:
    """Create a unified project status bar with tab header.

    Creates a header bar with tab name on the left and project status
    on the right, using flexbox layout.

    Args:
        initial_status: Initial HTML status (use format_project_status)
        tab_name: Tab name with icon (e.g., "🎥 Video Generator")
        show_refresh: Whether to show a refresh button
        refresh_label: Label for the refresh button
        refresh_min_width: Minimum width of the refresh button

    Returns:
        ProjectStatusBarComponents with status_bar (gr.HTML) and optional refresh_btn

    Example:
        ```python
        from addons.components import create_project_status_bar, format_project_status

        # Simple status bar with tab name
        project = self.project_store.get_active_project()
        status = create_project_status_bar(
            initial_status=format_project_status(
                project["name"] if project else None,
                project["slug"] if project else None,
                tab_name="🎥 Video Generator"
            ),
            tab_name="🎥 Video Generator"
        )
        ```
    """
    refresh_btn: Optional[gr.Button] = None

    # Default status if none provided
    if not initial_status:
        initial_status = format_project_status(None, None, tab_name=tab_name)

    if show_refresh:
        with gr.Row():
            status_bar = gr.HTML(initial_status)
            refresh_btn = gr.Button(
                refresh_label,
                scale=0,
                min_width=refresh_min_width,
            )
    else:
        status_bar = gr.HTML(initial_status)

    return ProjectStatusBarComponents(
        status_bar=status_bar,
        refresh_btn=refresh_btn,
    )


__all__ = [
    "ProjectStatusBarComponents",
    "create_project_status_bar",
    "format_project_status",
    "format_project_status_from_dict",
    "project_status_md",
    "storyboard_status_md",
    "shorten_storyboard_path",
]


def project_status_md(project_store, tab_name: str, **kwargs) -> str:
    """Convenience helper to build project status HTML for a tab.

    Args:
        project_store: ProjectStore instance with get_active_project(refresh=True)
        tab_name: Tab label incl. emoji (e.g., "🎥 Video Generator")
        **kwargs: Additional args forwarded to format_project_status (extra_info, show_path, ...)

    Returns:
        HTML string produced by format_project_status
    """
    project = project_store.get_active_project(refresh=True) if project_store else None
    name = project.get("name") if project else None
    slug = project.get("slug") if project else None
    path = project.get("path") if project else None
    return format_project_status(
        project_name=name,
        project_slug=slug,
        tab_name=tab_name,
        project_path=path,
        **kwargs,
    )


def format_project_status_extended(
    project_store,
    config,
    tab_name: str,
    show_storyboard: bool = True,
    show_resolution: bool = True,
    show_path: bool = False,
    include_remote_warning: bool = True,
) -> str:
    """Build extended project status with storyboard, resolution, and path.

    This is the recommended function for tabs that work with projects.
    It automatically collects all relevant project info.

    Args:
        project_store: ProjectStore instance
        config: ConfigManager instance (for resolution)
        tab_name: Tab label incl. emoji (e.g., "🎥 Video Generator")
        show_storyboard: Include current storyboard name
        show_resolution: Include resolution (e.g., "1280x720")
        show_path: Include project path

    Returns:
        HTML string with extended project info

    Example:
        >>> format_project_status_extended(project_store, config, "🎬 Keyframes")
        # Shows: "✅ Project: my_project │ 📖 main.json │ 📐 1280x720"
    """
    project = project_store.get_active_project(refresh=True) if project_store else None

    if not project:
        return format_project_status(
            None,
            None,
            tab_name=tab_name,
            include_remote_warning=include_remote_warning,
        )

    extra_info = []

    # Add storyboard info
    if show_storyboard:
        storyboard_path = project.get("current_storyboard")
        if storyboard_path:
            short_name = shorten_storyboard_path(storyboard_path)
            extra_info.append(("📖", short_name))
        else:
            extra_info.append(("📖", "none"))

    # Add resolution
    if show_resolution and config:
        try:
            width, height = config.get_resolution_tuple()
            extra_info.append(("📐", f"{width}x{height}"))
        except Exception:
            pass

    # Add path (shortened)
    if show_path:
        project_path = project.get("path", "")
        if project_path:
            # Show only last 2 directories
            parts = project_path.rstrip("/").split("/")
            short_path = "/".join(parts[-2:]) if len(parts) > 2 else project_path
            extra_info.append(("📁", short_path))

    return format_project_status(
        project_name=project.get("name"),
        project_slug=project.get("slug"),
        tab_name=tab_name,
        extra_info=extra_info if extra_info else None,
        show_path=False,  # We handle path in extra_info
        project_path=project.get("path"),
        include_remote_warning=include_remote_warning,
    )


def _get_remote_backend_label() -> str:
    """Return a badge label if a remote ComfyUI backend is configured."""
    try:
        from urllib.parse import urlparse
        from infrastructure.config_manager import ConfigManager

        url = ConfigManager().get_comfy_url()
        if not url:
            return ""

        host = urlparse(url).hostname
        local_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
        if host in local_hosts:
            return ""
        return "🌐 Remote backend"
    except Exception:
        return ""


def shorten_storyboard_path(abs_path: Optional[str]) -> str:
    """Shorten storyboard path for UI display."""
    if not abs_path:
        return ""
    marker = "/output/"
    if marker in abs_path:
        return abs_path.split(marker, 1)[-1]
    return os.path.basename(abs_path)


def storyboard_status_md(
    project_store,
    storyboard_path: Optional[str],
    tab_name: str,
    missing_storyboard_text: Optional[str] = None,
) -> str:
    """Build storyboard status markdown with consistent messaging."""
    project = project_store.get_active_project(refresh=True) if project_store else None

    if not project:
        return "**❌ No active project:** Please create one in the `📁 Project` tab."

    if not storyboard_path or not os.path.exists(storyboard_path):
        return missing_storyboard_text or "**❌ No storyboard set:** Please create/save one in the `📖 Storyboard` tab."

    short_path = shorten_storyboard_path(storyboard_path)
    return f"**Project:** {project.get('name')} | **Storyboard:** `{short_path}`"
