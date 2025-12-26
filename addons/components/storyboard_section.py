"""Reusable storyboard section (accordion with info + reload)."""

from typing import NamedTuple
import gradio as gr


class StoryboardSection(NamedTuple):
    info_md: gr.Markdown
    reload_btn: gr.Button


def create_storyboard_section(
    accordion_title: str = "📁 Storyboard",
    info_md_value: str = "",
    reload_label: str = "🔄 Storyboard neu laden",
    reload_variant: str = "secondary",
    reload_size: str = "sm",
) -> StoryboardSection:
    """Create a storyboard accordion with info markdown and reload button."""
    with gr.Accordion(accordion_title, open=False):
        info_md = gr.Markdown(info_md_value)
        reload_btn = gr.Button(reload_label, variant=reload_variant, size=reload_size)

    return StoryboardSection(info_md=info_md, reload_btn=reload_btn)


__all__ = ["StoryboardSection", "create_storyboard_section"]
