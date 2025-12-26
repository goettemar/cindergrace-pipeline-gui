"""Delete Confirmation Component - Reusable delete confirmation UI pattern.

This component provides a standardized delete confirmation dialog that
can be used across all addons requiring destructive action confirmation.
"""

from typing import NamedTuple
import gradio as gr


class DeleteConfirmComponents(NamedTuple):
    """Container for delete confirmation UI elements.

    Attributes:
        trigger_btn: Button that opens the confirmation dialog
        confirm_group: Hidden group containing the confirmation dialog
        confirm_text: Markdown element for dynamic warning text
        confirm_btn: Button to confirm deletion
        cancel_btn: Button to cancel and hide the dialog
    """

    trigger_btn: gr.Button
    confirm_group: gr.Group
    confirm_text: gr.Markdown
    confirm_btn: gr.Button
    cancel_btn: gr.Button


def create_delete_confirm(
    trigger_label: str = "🗑️ Delete",
    confirm_title: str = "### ⚠️ Really delete?",
    confirm_warning: str = "This action cannot be undone!",
    confirm_btn_label: str = "✅ Yes, delete",
    cancel_btn_label: str = "❌ Cancel",
    trigger_variant: str = "stop",
) -> DeleteConfirmComponents:
    """Create a delete confirmation UI group.

    Creates a trigger button and a hidden confirmation dialog with
    customizable labels. The confirmation group is initially hidden
    and should be shown when the trigger button is clicked.

    Args:
        trigger_label: Text for the trigger button
        confirm_title: Markdown title for confirmation dialog
        confirm_warning: Warning message shown in confirmation dialog
        confirm_btn_label: Text for the confirm button
        cancel_btn_label: Text for the cancel button
        trigger_variant: Gradio button variant for trigger ("stop", "primary", etc.)

    Returns:
        DeleteConfirmComponents with all UI elements for wiring events

    Example:
        ```python
        from addons.components import create_delete_confirm

        # Create the component
        delete_ui = create_delete_confirm(
            trigger_label="🗑️ Delete Project",
            confirm_warning="All project files will be permanently deleted!"
        )

        # Wire up events
        delete_ui.trigger_btn.click(
            fn=lambda: (
                gr.update(value=f"{confirm_title}\\n\\n**Achtung:** {confirm_warning}"),
                gr.update(visible=True)
            ),
            outputs=[delete_ui.confirm_text, delete_ui.confirm_group]
        )

        delete_ui.cancel_btn.click(
            fn=lambda: gr.update(visible=False),
            outputs=[delete_ui.confirm_group]
        )

        delete_ui.confirm_btn.click(
            fn=do_actual_delete,
            outputs=[..., delete_ui.confirm_group]
        )
        ```
    """
    # Trigger button (always visible)
    trigger_btn = gr.Button(trigger_label, variant=trigger_variant)

    # Confirmation dialog (initially hidden)
    with gr.Group(visible=False) as confirm_group:
        confirm_text = gr.Markdown(
            f"{confirm_title}\n\n**Warning:** {confirm_warning}"
        )
        with gr.Row():
            confirm_btn = gr.Button(confirm_btn_label, variant="stop")
            cancel_btn = gr.Button(cancel_btn_label, variant="secondary")

    return DeleteConfirmComponents(
        trigger_btn=trigger_btn,
        confirm_group=confirm_group,
        confirm_text=confirm_text,
        confirm_btn=confirm_btn,
        cancel_btn=cancel_btn,
    )


__all__ = ["DeleteConfirmComponents", "create_delete_confirm"]
