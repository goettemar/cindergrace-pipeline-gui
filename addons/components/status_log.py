"""Status Log Component - Reusable status/activity log with timestamps.

This component provides a standardized status log pattern commonly used
to display operation progress, errors, and activity history.
"""

from datetime import datetime
from typing import NamedTuple, Optional
import gradio as gr


class StatusLogComponents(NamedTuple):
    """Container for status log UI elements.

    Attributes:
        textbox: Non-interactive textbox displaying log entries
        header: Optional markdown header above the log
    """

    textbox: gr.Textbox
    header: Optional[gr.Markdown]


def create_status_log(
    lines: int = 6,
    max_lines: int = 8,
    initial_message: str = "Ready.",
    show_header: bool = False,
    header_text: str = "### Status",
    placeholder: str = "",
) -> StatusLogComponents:
    """Create a status log textbox with optional header.

    Creates a non-interactive textbox for displaying timestamped status
    messages, commonly used for operation progress and activity logs.

    Args:
        lines: Number of visible lines (default: 6)
        max_lines: Maximum lines before scrolling (default: 8)
        initial_message: Initial status message (default: "Ready.")
        show_header: Whether to show a header above the log (default: False)
        header_text: Markdown text for the header
        placeholder: Placeholder text when empty

    Returns:
        StatusLogComponents with textbox and optional header

    Example:
        ```python
        from addons.components import create_status_log, append_status

        # Create the log
        status = create_status_log(
            lines=8,
            initial_message="System initialized."
        )

        # In event handlers, use append_status:
        def on_save(current_log):
            # ... save logic ...
            return append_status(current_log, "✅ File saved")

        save_btn.click(
            fn=on_save,
            inputs=[status.textbox],
            outputs=[status.textbox]
        )
        ```
    """
    header = None
    if show_header:
        header = gr.Markdown(header_text)

    # Format initial message with placeholder timestamp
    initial_value = f"[--:--:--] {initial_message}" if initial_message else ""

    textbox = gr.Textbox(
        label="",
        lines=lines,
        max_lines=max_lines,
        interactive=False,
        value=initial_value,
        show_label=False,
        placeholder=placeholder,
    )

    return StatusLogComponents(textbox=textbox, header=header)


def append_status(
    current: str,
    message: str,
    max_history: int = 50,
    timestamp_format: str = "%H:%M:%S",
) -> str:
    """Append a timestamped message to the status log.

    Adds a new log entry with current timestamp, automatically
    pruning old entries when max_history is exceeded.

    Args:
        current: Current log content
        message: New message to append
        max_history: Maximum number of lines to keep (oldest removed first)
        timestamp_format: strftime format for timestamp (default: HH:MM:SS)

    Returns:
        Updated log string with new entry appended

    Example:
        ```python
        new_log = append_status(old_log, "✅ Project created")
        new_log = append_status(old_log, "❌ Error: File not found")
        new_log = append_status(old_log, "⏳ Processing...", max_history=100)
        ```
    """
    timestamp = datetime.now().strftime(timestamp_format)
    lines = [line for line in (current or "").splitlines() if line.strip()]
    lines.append(f"[{timestamp}] {message}")

    # Prune old entries if exceeding max_history
    if len(lines) > max_history:
        lines = lines[-max_history:]

    return "\n".join(lines)


def clear_status(initial_message: str = "Ready.") -> str:
    """Clear the status log and reset to initial message.

    Args:
        initial_message: Message to show after clearing

    Returns:
        Fresh log string with initial message

    Example:
        ```python
        clear_btn.click(
            fn=lambda: clear_status("Log cleared."),
            outputs=[status.textbox]
        )
        ```
    """
    return f"[--:--:--] {initial_message}"


__all__ = [
    "StatusLogComponents",
    "create_status_log",
    "append_status",
    "clear_status",
]
