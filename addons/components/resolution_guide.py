"""Resolution guide component for CINDERGRACE.

Provides a collapsible info panel showing resolution recommendations
for different workflows (Wan, Flux, SDXL) and VRAM configurations.
"""

from dataclasses import dataclass
from typing import Optional

import gradio as gr


@dataclass
class ResolutionGuideComponents:
    """Container for resolution guide UI elements."""
    accordion: gr.Accordion
    content: gr.Markdown


def get_resolution_guide_content() -> str:
    """Return the resolution guide markdown content."""
    return """### Wan 2.2 Video (gcv_wan_*)

| Auflösung | Format | VRAM | Empfehlung |
|-----------|--------|------|------------|
| **1280×720** | 16:9 | 12GB+ | ⭐ **Standard** |
| **720×1280** | 9:16 | 12GB+ | TikTok, Reels |
| **832×480** | 16:9 | 8GB+ | Schnelle Tests |
| **1920×1080** | 16:9 | 24GB+ | Beste Qualität |

⚠️ Wan unterstützt **nur** 16:9 / 9:16 Formate!

### LTX-Video (gcv_ltx_*) - Low VRAM Option

| Auflösung | Format | VRAM | Empfehlung |
|-----------|--------|------|------------|
| **768×512** | 3:2 | 6GB+ | ⭐ **Low VRAM** |
| **512×768** | 2:3 | 6GB+ | Portrait |
| **512×512** | 1:1 | 6GB+ | Quadrat möglich! |
| **1024×576** | 16:9 | 12GB+ | HD-ähnlich |

✅ LTX unterstützt **flexible Auflösungen** (teilbar durch 32)

### SDXL Keyframes (gcp_sdxl_*)

| Auflösung | VRAM | Hinweis |
|-----------|------|---------|
| **1024×1024** | 6GB+ | ⭐ Native SDXL |
| **512×512** | 4GB+ | Schnelle Tests |

### Flux Keyframes (gcp_flux_*)

| Auflösung | VRAM | Hinweis |
|-----------|------|---------|
| **1280×720** | 16GB+ | ⭐ Video-optimiert |
| **1024×1024** | 16GB+ | Nur Bilder |

### GPU-Empfehlungen

| VRAM | Keyframes | Videos |
|------|-----------|--------|
| **6-8GB** | SDXL 1024² | **LTX 768×512** |
| **12-16GB** | Flux 720p | Wan 720p |
| **24GB+** | Flux 1080p | Wan 1080p |
"""


def create_resolution_guide(
    open_by_default: bool = False,
    label: str = "📊 Auflösungs-Guide",
) -> ResolutionGuideComponents:
    """Create a collapsible resolution guide panel.

    Args:
        open_by_default: Whether the accordion starts open
        label: Label for the accordion

    Returns:
        ResolutionGuideComponents with accordion and content elements
    """
    with gr.Accordion(label=label, open=open_by_default) as accordion:
        content = gr.Markdown(get_resolution_guide_content())

    return ResolutionGuideComponents(
        accordion=accordion,
        content=content,
    )


__all__ = [
    "ResolutionGuideComponents",
    "create_resolution_guide",
    "get_resolution_guide_content",
]
