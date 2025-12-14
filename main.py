"""CINDERGRACE GUI - Main application"""
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradio as gr
from addons import load_addons
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

    with gr.Blocks(title="CINDERGRACE Pipeline Control") as demo:
        # Header
        with gr.Row():
            with gr.Column():
                gr.HTML("""
                <div class="header">
                    <h1>🎬 CINDERGRACE</h1>
                    <p>Automated Video Production Pipeline</p>
                </div>
                """)

        # Separate addons by category
        pipeline_addons = [a for a in addons if a.category == "pipeline"]
        tool_addons = [a for a in addons if a.category == "tools"]

        # Create tabs for each addon
        with gr.Tabs():
            # Pipeline addons as top-level tabs
            for addon in pipeline_addons:
                with gr.Tab(addon.get_tab_name()):
                    addon.render()

            # Tool addons grouped under Tools tab with sub-tabs
            if tool_addons:
                with gr.Tab("🔧 Tools"):
                    gr.Markdown("## ComfyUI Tools & Utilities")
                    with gr.Tabs():
                        for addon in tool_addons:
                            with gr.Tab(addon.get_tab_name()):
                                addon.render()

        # Footer
        gr.Markdown("""
        ---
        **CINDERGRACE Pipeline Control** • Version 0.5.1 • [Documentation](../GUI_FRAMEWORK_README.md)
        """)

    return demo


def main():
    """Main entry point"""

    logger.info("CINDERGRACE GUI starting...")
    config = ConfigManager()
    config.refresh()

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

    # Allow Gradio to serve files from ComfyUI output (project folders)
    comfy_root = config.get_comfy_root()
    allowed_paths = []
    if comfy_root:
        output_path = os.path.join(os.path.expanduser(comfy_root), "output")
        allowed_paths.append(output_path)

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
