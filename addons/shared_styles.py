"""Shared CSS styles for all CINDERGRACE addons.

This module provides centralized CSS styling that can be injected
into any addon for consistent look and feel across the application.
"""

import gradio as gr


# Common CSS styles used across all addons
COMMON_CSS = """
/* ========================================
   LAYOUT STYLES
   ======================================== */

/* Full width layout for all addons */
.gradio-container {
    max-width: 100% !important;
}

/* ========================================
   ALERT/STATUS BOX STYLES
   ======================================== */

/* Warning box (orange/yellow) */
.warning-box {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #92400e;
}

/* Info box (blue) */
.info-box {
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #1e40af;
}

/* Warning banner (for inline warnings) */
.warning-banner {
    background: #fef3c7;
    border-left: 4px solid #f59e0b;
    padding: 8px 12px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
    color: #92400e;
}

/* Success box (green) */
.success-box {
    background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
    border: 1px solid #10b981;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #065f46;
}

/* Error box (red) */
.error-box {
    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
    border: 1px solid #ef4444;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #991b1b;
}

/* ========================================
   TEXT STYLES
   ======================================== */

/* Info text (subtle hint text) */
.info-text {
    font-size: 0.9em;
    color: #6b7280;
    font-style: italic;
}

/* Info hint (small helper text) */
.info-hint {
    font-size: 0.85em;
    color: #9ca3af;
    margin-top: 4px;
}

/* ========================================
   STORYBOARD EDITOR SPECIFIC
   ======================================== */

/* Shot List scrollable */
#shots_list {
    max-height: 350px;
    overflow-y: auto;
}

/* Setup accordion spacing */
#setup_accordion {
    margin-bottom: 10px;
}

/* Right pane border (two-column layouts) */
#right_pane {
    border-left: 2px solid #e0e0e0;
    padding-left: 15px;
}

/* ========================================
   BUTTON STYLES
   ======================================== */

/* Danger button hover effect */
.danger-btn:hover {
    background: #dc2626 !important;
}

/* ========================================
   TABLE/DATAFRAME STYLES
   ======================================== */

/* Compact table rows */
.compact-table table {
    font-size: 0.9em;
}

.compact-table tr {
    height: 32px;
}

/* ========================================
   ACCORDION STYLES
   ======================================== */

/* Collapsed accordion styling */
.collapsed-accordion .label-wrap {
    padding: 8px 12px !important;
}
"""


def get_common_css() -> str:
    """Get the common CSS styles as a string.

    Returns:
        CSS string that can be used in style tags
    """
    return COMMON_CSS


def inject_styles() -> gr.HTML:
    """Create a Gradio HTML component that injects the common CSS styles.

    Use this at the beginning of your addon's render() method:

    Example:
        def render(self) -> gr.Blocks:
            with gr.Blocks() as interface:
                inject_styles()  # Add common CSS
                # ... rest of your UI

    Returns:
        gr.HTML component with embedded CSS
    """
    return gr.HTML(f"<style>{COMMON_CSS}</style>")


__all__ = [
    "COMMON_CSS",
    "get_common_css",
    "inject_styles",
]
