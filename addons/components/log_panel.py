"""Global log panel component for displaying recent log messages."""
from dataclasses import dataclass
from typing import Callable

import gradio as gr

from infrastructure.logger import UILogHandler


@dataclass
class LogPanelUI:
    """UI elements for the log panel."""
    container: gr.Group
    textbox: gr.Textbox
    refresh_btn: gr.Button


def create_log_panel(lines: int = 20, auto_refresh: bool = True) -> LogPanelUI:
    """Create a log panel that displays recent log messages.

    Args:
        lines: Number of log lines to display
        auto_refresh: If True, auto-refresh every 3 seconds

    Returns:
        LogPanelUI with container, textbox, and refresh button
    """
    handler = UILogHandler.get_instance()

    with gr.Group(elem_classes=["log-panel"]) as container:
        with gr.Row():
            with gr.Column(scale=8):
                gr.Markdown("### 📋 Log")
            with gr.Column(scale=1, min_width=40):
                refresh_btn = gr.Button("↻", size="sm")

        textbox = gr.Textbox(
            value=handler.get_logs_text(lines),
            label=None,
            lines=5,
            max_lines=5,
            interactive=False,
            elem_classes=["log-textbox"],
        )

        # Refresh handler
        def refresh_logs():
            return handler.get_logs_text(lines)

        refresh_btn.click(fn=refresh_logs, outputs=[textbox])

        # Auto-refresh via timer (every 3 seconds)
        # NOTE: Disabled due to Gradio issue where timer ticks can trigger tab load events
        # if auto_refresh:
        #     timer = gr.Timer(value=3, active=True)
        #     timer.tick(fn=refresh_logs, outputs=[textbox])

    return LogPanelUI(container=container, textbox=textbox, refresh_btn=refresh_btn)


__all__ = ["create_log_panel", "LogPanelUI"]
