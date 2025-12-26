"""Storyboard Preview Component - JSON preview for storyboard data.

This component provides a collapsible accordion with a JSON code viewer
for displaying storyboard data consistently across tabs.
"""

from typing import NamedTuple, Optional
import gradio as gr


class StoryboardPreviewComponents(NamedTuple):
    """Container for storyboard preview UI elements.

    Attributes:
        accordion: The Accordion container (for visibility control)
        code: Code element displaying the JSON
    """

    accordion: gr.Accordion
    code: gr.Code


def create_storyboard_preview(
    initial_value: str = "{}",
    label: str = "📄 Storyboard Details",
    code_label: str = "JSON",
    lines: int = 15,
    open: bool = False,
) -> StoryboardPreviewComponents:
    """Create a storyboard preview accordion with JSON code viewer.

    Args:
        initial_value: Initial JSON string to display
        label: Label for the accordion
        code_label: Label for the code element
        lines: Number of lines for the code viewer
        open: Whether the accordion is open by default

    Returns:
        StoryboardPreviewComponents with accordion and code elements

    Example:
        ```python
        from addons.components import create_storyboard_preview

        # Create preview
        preview = create_storyboard_preview(
            initial_value=self._get_storyboard_json(),
            open=False
        )

        # Update on selection change
        dropdown.change(
            fn=self._get_storyboard_json,
            inputs=[dropdown],
            outputs=[preview.code]
        )
        ```
    """
    with gr.Accordion(label, open=open) as accordion:
        code = gr.Code(
            label=code_label,
            language="json",
            lines=lines,
            interactive=False,
            value=initial_value,
        )

    return StoryboardPreviewComponents(
        accordion=accordion,
        code=code,
    )


__all__ = [
    "StoryboardPreviewComponents",
    "create_storyboard_preview",
]
