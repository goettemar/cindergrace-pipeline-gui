"""CINDERGRACE GUI - Main application"""
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradio as gr
from addons import load_addons
from addons.components import create_log_panel
from infrastructure.logger import get_logger, PipelineLogger
from infrastructure.config_manager import ConfigManager

# Apply log level from config before first log message
_config = ConfigManager()
_log_level_str = _config.get_log_level()
_log_level = getattr(logging, _log_level_str.upper(), logging.INFO)
PipelineLogger.set_level(_log_level)

# Initialize logger
logger = get_logger(__name__)


def create_gui():
    """Create and configure the main GUI application"""

    # Load all addons
    logger.info("=" * 60)
    logger.info("CINDERGRACE Pipeline Control - Loading...")
    logger.info("=" * 60)

    addons = load_addons()

    if not addons:
        logger.warning("No addons loaded!")
        return None

    logger.info(f"✓ Loaded {len(addons)} addon(s)")
    logger.info("=" * 60)

    # Create main interface with tabs
    css = """
    .header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .header h1 {
        margin: 0;
        font-size: 2.5em;
        font-weight: bold;
    }
    .header p {
        margin: 10px 0 0 0;
        font-size: 1.1em;
        opacity: 0.9;
    }
    """

    # Check if first run
    config = ConfigManager()
    is_first_run = config.is_first_run()

    # Get active backend info
    active_backend = config.get_active_backend()
    backend_name = active_backend.get("name", "Lokal")
    backend_type = active_backend.get("type", "local")
    backend_icon = "☁️" if backend_type == "remote" else "🖥️"
    backend_color = "#4CAF50" if backend_type == "local" else "#2196F3"

    with gr.Blocks(title="CINDERGRACE Pipeline Control") as demo:
        # Header with backend indicator
        with gr.Row():
            with gr.Column():
                gr.HTML(f"""
                <div class="header">
                    <h1>🎬 CINDERGRACE</h1>
                    <p>Automated Video Production Pipeline</p>
                    <div style="
                        display: inline-block;
                        margin-top: 10px;
                        padding: 4px 12px;
                        background: {backend_color};
                        border-radius: 16px;
                        font-size: 0.85em;
                        opacity: 0.95;
                    ">
                        {backend_icon} Backend: {backend_name}
                    </div>
                </div>
                """)

        # First-run banner (prominent)
        if is_first_run:
            with gr.Row():
                gr.HTML("""
                <div style="
                    background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
                    color: white;
                    padding: 20px 24px;
                    border-radius: 12px;
                    margin: 10px 0 20px 0;
                    box-shadow: 0 4px 12px rgba(255, 152, 0, 0.3);
                ">
                    <div style="display: flex; align-items: center; gap: 16px;">
                        <span style="font-size: 2.5em;">🚀</span>
                        <div>
                            <h3 style="margin: 0 0 8px 0; font-size: 1.3em;">Willkommen bei CINDERGRACE!</h3>
                            <p style="margin: 0; opacity: 0.95;">
                                Es sieht so aus, als wäre dies Ihr erster Start.<br>
                                Bitte öffnen Sie den <strong>Setup</strong> Tab um Ihr System zu konfigurieren.
                            </p>
                        </div>
                    </div>
                </div>
                """)

        # Flat tabs - all addons in one row
        with gr.Tabs():
            for addon in addons:
                with gr.Tab(addon.get_tab_name()):
                    addon.render()

        # Global log panel (below tabs)
        create_log_panel(lines=20, auto_refresh=True)

        # Footer
        gr.Markdown("""
        ---
        **CINDERGRACE Pipeline Control** • Version 0.6.1 • [Documentation](../GUI_FRAMEWORK_README.md)
        """)

    return demo


def _validate_storyboard_on_startup(config: ConfigManager) -> None:
    """Check if current_storyboard exists, fix if needed."""
    from infrastructure.project_store import ProjectStore

    current_sb = config.get_current_storyboard()

    # If no storyboard set or file exists, nothing to do
    if not current_sb:
        return
    if os.path.exists(current_sb):
        return

    # Storyboard file missing - try to find one in the active project
    logger.warning(f"Storyboard nicht gefunden: {current_sb}")

    try:
        store = ProjectStore(config)
        project = store.get_active_project(refresh=True)

        if project:
            # Trigger storyboard update for current project
            store._update_storyboard_for_project(project)
            config.refresh()
            new_sb = config.get_current_storyboard()
            if new_sb and os.path.exists(new_sb):
                logger.info(f"Storyboard korrigiert: {new_sb}")
            else:
                logger.warning("Kein gültiges Storyboard im Projekt gefunden")
    except Exception as e:
        logger.warning(f"Konnte Storyboard nicht automatisch korrigieren: {e}")


def main():
    """Main entry point"""

    logger.info("CINDERGRACE GUI starting...")
    config = ConfigManager()
    config.refresh()

    # Validate storyboard path on startup
    _validate_storyboard_on_startup(config)

    # Create GUI
    demo = create_gui()

    if demo is None:
        logger.error("Failed to create GUI")
        return

    # Launch
    logger.info("🚀 Launching CINDERGRACE GUI...")
    logger.info("=" * 60)

    css = """
    .header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .header h1 {
        margin: 0;
        font-size: 2.5em;
        font-weight: bold;
    }
    .header p {
        margin: 10px 0 0 0;
        font-size: 1.1em;
        opacity: 0.9;
    }
    """

    # Allow Gradio to serve files from ComfyUI output and project folders
    allowed_paths = []

    # Add ComfyUI output directory
    comfy_root = config.get_comfy_root()
    if comfy_root:
        comfy_root = os.path.expanduser(comfy_root)
        output_path = os.path.join(comfy_root, "output")
        if os.path.isdir(output_path):
            allowed_paths.append(output_path)
            logger.info(f"Allowed path: {output_path}")

    # Also allow all backend output directories
    for backend_id, backend in config.get_backends().items():
        backend_root = backend.get("comfy_root", "")
        if backend_root:
            backend_root = os.path.expanduser(backend_root)
            backend_output = os.path.join(backend_root, "output")
            if os.path.isdir(backend_output) and backend_output not in allowed_paths:
                allowed_paths.append(backend_output)
                logger.info(f"Allowed path (backend {backend_id}): {backend_output}")

    # Enable queue for long-running operations (video generation can take 10+ minutes)
    demo.queue(default_concurrency_limit=1)

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
        quiet=False,
        css=css,
        allowed_paths=allowed_paths
    )


if __name__ == "__main__":
    main()
