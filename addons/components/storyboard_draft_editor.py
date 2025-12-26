"""Shared component for editing storyboard drafts.

Provides a reusable JSON editor with live validation and shot preview.
Used in both Storyboard Editor and LLM Generator addons.
"""
import json
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

import gradio as gr

from domain.validators import StoryboardDraftValidator


class DraftEditorComponents(NamedTuple):
    """Container for draft editor UI components."""
    # Tabs container
    tabs: gr.Tabs
    # Shots tab
    shot_table: gr.Dataframe
    # JSON tab
    json_editor: gr.Code
    # Status
    validation_status: gr.Markdown
    # Actions
    validate_btn: gr.Button
    import_btn: gr.Button


def create_draft_editor(
    initial_json: str = "{}",
    show_import_btn: bool = True,
    import_btn_label: str = "In Projekt importieren",
    json_lines: int = 20,
    interactive: bool = True,
) -> DraftEditorComponents:
    """Create a draft editor component with JSON editor and shot preview.

    Args:
        initial_json: Initial JSON content
        show_import_btn: Whether to show the import button
        import_btn_label: Label for import button
        json_lines: Number of lines for JSON editor
        interactive: Whether JSON is editable

    Returns:
        DraftEditorComponents tuple
    """
    with gr.Tabs() as tabs:
        # Tab 1: Shot Preview
        with gr.Tab("Shots"):
            shot_table = gr.Dataframe(
                headers=["#", "ID", "Filename", "Description", "Duration"],
                datatype=["number", "str", "str", "str", "str"],
                col_count=(5, "fixed"),
                interactive=False,
                wrap=True,
                value=[],
            )

        # Tab 2: JSON Editor
        with gr.Tab("JSON Editor"):
            json_editor = gr.Code(
                value=initial_json,
                language="json",
                lines=json_lines,
                interactive=interactive,
                show_label=False,
            )

    # Validation status
    validation_status = gr.Markdown(
        value="",
        elem_classes=["validation-status"],
    )

    # Action buttons
    with gr.Row():
        validate_btn = gr.Button(
            "Validieren",
            variant="secondary",
            size="sm",
        )
        import_btn = gr.Button(
            import_btn_label,
            variant="primary",
            size="sm",
            visible=show_import_btn,
        )

    return DraftEditorComponents(
        tabs=tabs,
        shot_table=shot_table,
        json_editor=json_editor,
        validation_status=validation_status,
        validate_btn=validate_btn,
        import_btn=import_btn,
    )


def json_to_shot_table(json_str: str) -> List[List[Any]]:
    """Convert JSON string to shot table data.

    Args:
        json_str: Storyboard JSON string

    Returns:
        List of rows for Dataframe
    """
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict) or "shots" not in data:
            return []

        rows = []
        for i, shot in enumerate(data.get("shots", []), start=1):
            rows.append([
                i,
                shot.get("shot_id", ""),
                shot.get("filename_base", ""),
                shot.get("description", "")[:50] + "..." if len(shot.get("description", "")) > 50 else shot.get("description", ""),
                f"{shot.get('duration', 3.0)}s",
            ])
        return rows
    except (json.JSONDecodeError, TypeError):
        return []


def validate_draft_json(json_str: str) -> Tuple[str, List[List[Any]]]:
    """Validate JSON and return status message and shot table.

    Args:
        json_str: JSON string to validate

    Returns:
        Tuple of (status_markdown, shot_table_data)
    """
    if not json_str or json_str.strip() in ("{}", ""):
        return "", []

    is_valid, errors, warnings = StoryboardDraftValidator.validate_json_string(json_str)[0:1] + (
        StoryboardDraftValidator.validate_json_string(json_str)[2],
        [],
    )

    # Re-run to get all values properly
    is_valid, draft, errors = StoryboardDraftValidator.validate_json_string(json_str)

    if is_valid and draft:
        warnings = StoryboardDraftValidator.get_warnings(draft)
        shot_count = len(draft.shots)
        total_duration = sum(s.duration for s in draft.shots)

        status_parts = [f"**Valide** - {shot_count} Shots, {total_duration:.1f}s Gesamtdauer"]

        if warnings:
            status_parts.append("\n**Hinweise:**")
            for w in warnings[:5]:  # Limit to 5 warnings
                status_parts.append(f"- {w}")
            if len(warnings) > 5:
                status_parts.append(f"- ... und {len(warnings) - 5} weitere")

        status = "\n".join(status_parts)
        shot_table = json_to_shot_table(json_str)
        return status, shot_table
    else:
        error_parts = ["**Fehler bei Validierung:**"]
        for e in errors[:5]:
            error_parts.append(f"- {e}")
        if len(errors) > 5:
            error_parts.append(f"- ... und {len(errors) - 5} weitere Fehler")

        status = "\n".join(error_parts)
        return status, []


def format_storyboard_json(json_str: str) -> str:
    """Format/prettify JSON string.

    Args:
        json_str: JSON string to format

    Returns:
        Formatted JSON string
    """
    try:
        data = json.loads(json_str)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return json_str


def setup_draft_editor_events(
    components: DraftEditorComponents,
    on_import: Optional[Callable[[str], Any]] = None,
) -> None:
    """Setup event handlers for draft editor.

    Args:
        components: DraftEditorComponents from create_draft_editor
        on_import: Optional callback for import button
    """
    # Validate button
    components.validate_btn.click(
        fn=validate_draft_json,
        inputs=[components.json_editor],
        outputs=[components.validation_status, components.shot_table],
    )

    # Auto-validate on JSON change (with debounce via Gradio)
    components.json_editor.change(
        fn=validate_draft_json,
        inputs=[components.json_editor],
        outputs=[components.validation_status, components.shot_table],
    )

    # Import button (if callback provided)
    if on_import and components.import_btn:
        components.import_btn.click(
            fn=on_import,
            inputs=[components.json_editor],
            outputs=[],  # Caller should handle outputs
        )


__all__ = [
    "DraftEditorComponents",
    "create_draft_editor",
    "json_to_shot_table",
    "validate_draft_json",
    "format_storyboard_json",
    "setup_draft_editor_events",
]
