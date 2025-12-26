"""Help UI Komponenten - Gradio Tooltip und Modal für Hilfetexte."""
import gradio as gr
from typing import Optional

from infrastructure.help_service import HelpService, get_help_service


def help_icon(tooltip: str) -> gr.HTML:
    """Erzeugt ein Info-Icon mit Hover-Tooltip.

    Args:
        tooltip: Der anzuzeigende Tooltip-Text

    Returns:
        Gradio HTML-Komponente mit Icon und Tooltip
    """
    if not tooltip:
        return gr.HTML("")

    # CSS-styled Info-Icon mit nativen Browser-Tooltip
    html = f"""
    <span class="help-icon" title="{tooltip}" style="
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background-color: var(--neutral-400);
        color: white;
        font-size: 12px;
        font-weight: bold;
        cursor: help;
        margin-left: 4px;
        user-select: none;
    ">?</span>
    """
    return gr.HTML(html, elem_classes=["help-tooltip"])


def help_button(
    label: str = "?",
    modal_title: str = "Hilfe",
    modal_content: str = "",
    size: str = "sm",
) -> tuple[gr.Button, gr.Column]:
    """Erzeugt einen Hilfe-Button mit ausklappbarem Bereich.

    Da Gradio keine echten Modals hat, nutzen wir einen Accordion/Collapsible.

    Args:
        label: Button-Beschriftung
        modal_title: Titel des Hilfe-Bereichs
        modal_content: Inhalt des Hilfe-Bereichs
        size: Button-Größe ('sm', 'lg')

    Returns:
        Tuple aus (Button, Column mit Inhalt)
    """
    with gr.Row():
        btn = gr.Button(
            label,
            size=size,
            variant="secondary",
            elem_classes=["help-button"],
            min_width=30,
        )

    # Versteckter Bereich für Hilfe-Inhalt
    with gr.Column(visible=False) as help_panel:
        gr.Markdown(f"### {modal_title}")
        gr.Markdown(modal_content)
        close_btn = gr.Button("Schließen", size="sm", variant="secondary")

    # Toggle-Logik
    btn.click(
        fn=lambda: gr.Column(visible=True),
        outputs=help_panel,
    )
    close_btn.click(
        fn=lambda: gr.Column(visible=False),
        outputs=help_panel,
    )

    return btn, help_panel


def help_accordion(
    title: str = "Hilfe",
    content: str = "",
    open_default: bool = False,
) -> gr.Accordion:
    """Erzeugt einen Accordion-Bereich für Hilfetexte.

    Args:
        title: Accordion-Titel
        content: Markdown-Inhalt
        open_default: Ob standardmäßig geöffnet

    Returns:
        Gradio Accordion-Komponente
    """
    with gr.Accordion(title, open=open_default) as accordion:
        gr.Markdown(content)
    return accordion


def field_with_help(
    component_fn,
    label: str,
    help_service: Optional[HelpService] = None,
    tab: str = "",
    field: str = "",
    **component_kwargs,
):
    """Erzeugt ein Eingabefeld mit integrierter Hilfe.

    Args:
        component_fn: Gradio-Komponenten-Funktion (z.B. gr.Textbox)
        label: Feld-Label
        help_service: HelpService-Instanz (Standard: Singleton)
        tab: Tab-Bezeichner für Hilfetext
        field: Feld-Bezeichner für Hilfetext
        **component_kwargs: Weitere Parameter für die Komponente

    Returns:
        Die erstellte Komponente
    """
    if help_service is None:
        help_service = get_help_service()

    tooltip = help_service.get_tooltip(tab, field)

    # Gradio unterstützt 'info' Parameter für Tooltips
    if tooltip and "info" not in component_kwargs:
        component_kwargs["info"] = tooltip

    return component_fn(label=label, **component_kwargs)


class HelpContext:
    """Kontext-Manager für Tab-spezifische Hilfetexte.

    Vereinfacht die Nutzung des HelpService innerhalb eines Tabs.

    Beispiel:
        help = HelpContext("keyframe_generator")
        gr.Textbox(label="Prompt", info=help.tooltip("prompt"))
    """

    def __init__(self, tab: str, help_service: Optional[HelpService] = None):
        """Initialisiert den HelpContext.

        Args:
            tab: Tab-Bezeichner
            help_service: HelpService-Instanz (Standard: Singleton)
        """
        self.tab = tab
        self.service = help_service or get_help_service()

    def tooltip(self, field: str) -> str:
        """Holt Tooltip für ein Feld.

        Args:
            field: Feld-Bezeichner

        Returns:
            Tooltip-Text
        """
        return self.service.get_tooltip(self.tab, field)

    def modal(self, field: str) -> str:
        """Holt Modal-Text für ein Feld.

        Args:
            field: Feld-Bezeichner

        Returns:
            Modal-Text
        """
        return self.service.get_modal(self.tab, field)

    def tab_info(self) -> dict:
        """Holt Tab-Informationen.

        Returns:
            Dict mit 'title' und 'description'
        """
        return self.service.get_tab_info(self.tab)

    def help_section(self, field: str, open_default: bool = False) -> gr.Accordion:
        """Erzeugt einen Hilfe-Accordion für ein Feld.

        Args:
            field: Feld-Bezeichner
            open_default: Ob standardmäßig geöffnet

        Returns:
            Gradio Accordion-Komponente
        """
        modal_text = self.modal(field)
        if not modal_text:
            return None
        return help_accordion(
            title=f"Hilfe: {field}",
            content=modal_text,
            open_default=open_default,
        )


def inject_help_css() -> gr.HTML:
    """Injiziert CSS für Hilfe-Komponenten.

    Returns:
        Gradio HTML-Komponente mit CSS
    """
    css = """
    <style>
    .help-tooltip {
        display: inline-block;
        vertical-align: middle;
    }

    .help-button {
        padding: 2px 8px !important;
        min-width: 28px !important;
        border-radius: 50% !important;
    }

    .help-icon:hover {
        background-color: var(--primary-500) !important;
        transform: scale(1.1);
    }

    .help-panel {
        background-color: var(--background-fill-secondary);
        border: 1px solid var(--border-color-primary);
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    }
    </style>
    """
    return gr.HTML(css, visible=False)
