"""Folder Scanner Component - Reusable dropdown with refresh functionality.

This component provides a standardized file/folder selection pattern with
dropdown, optional refresh button, and optional action buttons (Load, Save, etc.).
"""

from typing import NamedTuple, Optional, List, Callable, Tuple
import gradio as gr


class FolderScannerComponents(NamedTuple):
    """Container for folder scanner UI elements.

    Attributes:
        dropdown: Dropdown for file/folder selection
        refresh_btn: Button to refresh the dropdown choices (None if show_refresh=False)
        action_btns: List of additional action buttons (Load, Save, etc.)
    """

    dropdown: gr.Dropdown
    refresh_btn: Optional[gr.Button]
    action_btns: List[gr.Button]


def create_folder_scanner(
    label: str,
    choices: List[str],
    value: Optional[str] = None,
    info: str = "",
    refresh_label: str = "↻",
    refresh_min_width: int = 50,
    show_refresh: bool = True,
    action_buttons: Optional[List[Tuple[str, str, str]]] = None,
    dropdown_scale: int = 4,
) -> FolderScannerComponents:
    """Create a folder scanner UI group with dropdown and optional buttons.

    Creates a standardized file/folder selection pattern commonly used
    for selecting storyboards, workflows, selection files, etc.

    Args:
        label: Label for the dropdown
        choices: Initial dropdown choices
        value: Pre-selected value (None for first choice or empty)
        info: Help text shown below the dropdown
        refresh_label: Label for refresh button (default: "↻")
        refresh_min_width: Minimum width of refresh button in pixels
        show_refresh: Whether to show the refresh button (default: True)
        action_buttons: List of (label, variant, size) tuples for extra buttons.
                       Example: [("📂 Load", "secondary", "sm"), ("💾 Save", "primary", "sm")]
        dropdown_scale: Relative width of dropdown in row (default: 4)

    Returns:
        FolderScannerComponents with dropdown, refresh_btn (or None), and action_btns

    Example:
        ```python
        from addons.components import create_folder_scanner, create_refresh_handler

        # Simple scanner with just refresh
        scanner = create_folder_scanner(
            label="Select Storyboard",
            choices=self._get_storyboard_choices(),
            info="JSON files in project"
        )

        scanner.refresh_btn.click(
            fn=create_refresh_handler(self._get_storyboard_choices),
            outputs=[scanner.dropdown]
        )

        # Scanner with action buttons only (no separate refresh)
        scanner = create_folder_scanner(
            label="Workflow Template",
            choices=get_workflows(),
            show_refresh=False,
            action_buttons=[
                ("⭐ Set Default", "secondary", "sm"),
                ("🔄 Rescan", "secondary", "sm")
            ]
        )

        scanner.action_btns[0].click(fn=set_default, inputs=[scanner.dropdown])
        scanner.action_btns[1].click(fn=rescan, outputs=[scanner.dropdown])
        ```
    """
    action_btns: List[gr.Button] = []
    refresh_btn: Optional[gr.Button] = None

    # Dropdown
    dropdown = gr.Dropdown(
        label=label,
        choices=choices,
        value=value,
        info=info if info else None,
    )

    # Button row (only if we have buttons to show)
    if show_refresh or action_buttons:
        with gr.Row():
            # Refresh button (optional)
            if show_refresh:
                refresh_btn = gr.Button(
                    refresh_label,
                    scale=0,
                    min_width=refresh_min_width,
                )

            # Create action buttons if specified
            if action_buttons:
                for btn_label, btn_variant, btn_size in action_buttons:
                    btn = gr.Button(
                        btn_label,
                        variant=btn_variant,
                        size=btn_size,
                        scale=1,
                    )
                    action_btns.append(btn)

    return FolderScannerComponents(
        dropdown=dropdown,
        refresh_btn=refresh_btn,
        action_btns=action_btns,
    )


def create_refresh_handler(scan_fn: Callable[[], List[str]]) -> Callable:
    """Create a standard refresh handler for folder scanners.

    Creates a handler function that rescans and updates dropdown choices.
    This is the standard pattern for refresh button click handlers.

    Args:
        scan_fn: Function that returns new choices list

    Returns:
        Handler function for refresh_btn.click()

    Example:
        ```python
        scanner.refresh_btn.click(
            fn=create_refresh_handler(self._get_storyboard_choices),
            outputs=[scanner.dropdown]
        )
        ```
    """
    def handler():
        new_choices = scan_fn()
        return gr.update(choices=new_choices)
    return handler


def create_refresh_handler_with_value(
    scan_fn: Callable[[], List[str]],
    default_fn: Optional[Callable[[], Optional[str]]] = None,
) -> Callable:
    """Create a refresh handler that also updates the selected value.

    Like create_refresh_handler but also sets the dropdown value,
    useful when the current selection might become invalid after refresh.

    Args:
        scan_fn: Function that returns new choices list
        default_fn: Optional function that returns the default value to select

    Returns:
        Handler function for refresh_btn.click()

    Example:
        ```python
        scanner.refresh_btn.click(
            fn=create_refresh_handler_with_value(
                scan_fn=self._get_workflows,
                default_fn=self._get_default_workflow
            ),
            outputs=[scanner.dropdown]
        )
        ```
    """
    def handler():
        new_choices = scan_fn()
        new_value = default_fn() if default_fn else (new_choices[0] if new_choices else None)
        return gr.update(choices=new_choices, value=new_value)
    return handler


__all__ = [
    "FolderScannerComponents",
    "create_folder_scanner",
    "create_refresh_handler",
    "create_refresh_handler_with_value",
]
